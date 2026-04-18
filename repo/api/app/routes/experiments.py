from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import Conflict, NotFound
from app.middleware.auth import get_auth
from app.models.models import (
    Experiment,
    InferenceRouting,
    ModelVersion,
    ModelVersionStatus,
    RollbackEvent,
)
from app.schemas.models import (
    ExperimentCreateRequest,
    ExperimentListResponse,
    ExperimentSummary,
    ExperimentToggleRequest,
    RollbackRequest,
    RoutingUpdateRequest,
)
from app.services import metrics
from app.services.audit import write_audit
from app.services.rbac import AuthContext, ensure_permission

router = APIRouter(prefix="/experiments", tags=["experiments"])


async def _load_exp(db: AsyncSession, exp_id: str) -> tuple[Experiment, InferenceRouting]:
    try:
        eid = uuid.UUID(exp_id)
    except ValueError:
        raise NotFound(message="experiment not found")
    exp = (
        await db.execute(select(Experiment).where(Experiment.id == eid))
    ).scalar_one_or_none()
    if exp is None:
        raise NotFound(message="experiment not found")
    routing = (
        await db.execute(select(InferenceRouting).where(InferenceRouting.experiment_id == eid))
    ).scalar_one_or_none()
    if routing is None:
        raise NotFound(message="routing not found for experiment")
    return exp, routing


def _summary(exp: Experiment, routing: InferenceRouting) -> ExperimentSummary:
    return ExperimentSummary(
        id=str(exp.id),
        name=exp.name,
        description=exp.description,
        ingest_enabled=exp.ingest_enabled,
        apply_enabled=exp.apply_enabled,
        model_a_id=str(routing.model_a_id),
        model_b_id=str(routing.model_b_id) if routing.model_b_id else None,
        weight_a=routing.weight_a,
        weight_b=routing.weight_b,
    )


@router.get("", response_model=ExperimentListResponse)
async def list_experiments(
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> ExperimentListResponse:
    # Any model/experiment action grants the right to see the experiment
    # roster; feedback submitters also see it so they can pick one. Otherwise
    # return an empty list rather than leaking experiment metadata.
    if not (
        auth.has_permission("*", "*")
        or auth.has_permission("experiment", "manage")
        or auth.has_permission("model", "route")
        or auth.has_permission("model", "rollback")
        or auth.has_permission("feedback", "submit")
    ):
        return ExperimentListResponse(items=[])
    rows = (await db.execute(select(Experiment).order_by(Experiment.name))).scalars().all()
    routings = {
        r.experiment_id: r
        for r in (await db.execute(select(InferenceRouting))).scalars().all()
    }
    items = [
        _summary(e, routings[e.id]) for e in rows if e.id in routings
    ]
    return ExperimentListResponse(items=items)


@router.post("", response_model=ExperimentSummary, status_code=201)
async def create_experiment(
    body: ExperimentCreateRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> ExperimentSummary:
    ensure_permission(auth, "experiment", "manage")
    exists = (
        await db.execute(select(Experiment).where(Experiment.name == body.name))
    ).scalar_one_or_none()
    if exists is not None:
        raise Conflict(error="experiment_name_taken", message="experiment name already exists")
    try:
        a_id = uuid.UUID(body.model_a_version_id)
    except ValueError:
        raise NotFound(message="model A version not found")
    model_a = (
        await db.execute(select(ModelVersion).where(ModelVersion.id == a_id))
    ).scalar_one_or_none()
    if model_a is None or model_a.status != ModelVersionStatus.APPROVED.value:
        raise Conflict(
            error="model_a_not_approved",
            message="model A must be an APPROVED version",
        )
    b_id: uuid.UUID | None = None
    if body.model_b_version_id:
        try:
            b_id = uuid.UUID(body.model_b_version_id)
        except ValueError:
            raise NotFound(message="model B version not found")
        model_b = (
            await db.execute(select(ModelVersion).where(ModelVersion.id == b_id))
        ).scalar_one_or_none()
        if model_b is None:
            raise NotFound(message="model B version not found")
        if model_b.feature_schema_hash != model_a.feature_schema_hash:
            raise Conflict(
                error="feature_schema_mismatch",
                message="arms must share a feature schema",
            )

    exp = Experiment(
        name=body.name,
        description=body.description,
        ingest_enabled=True,
        apply_enabled=True,
    )
    db.add(exp)
    await db.flush()
    routing = InferenceRouting(
        experiment_id=exp.id,
        model_a_id=a_id,
        model_b_id=b_id,
        weight_a=body.weight_a,
        weight_b=100 - body.weight_a,
    )
    db.add(routing)
    await db.flush()
    await write_audit(
        db,
        action="EXPERIMENT_CREATE",
        resource_type="experiment",
        resource_id=exp.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={"name": exp.name, "weight_a": routing.weight_a},
    )
    await db.commit()
    return _summary(exp, routing)


@router.post("/{experiment_id}/toggle", response_model=ExperimentSummary)
async def toggle(
    experiment_id: str,
    body: ExperimentToggleRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> ExperimentSummary:
    ensure_permission(auth, "experiment", "manage")
    exp, routing = await _load_exp(db, experiment_id)
    before = (exp.ingest_enabled, exp.apply_enabled)
    if body.ingest_enabled is not None:
        exp.ingest_enabled = body.ingest_enabled
    if body.apply_enabled is not None:
        exp.apply_enabled = body.apply_enabled
    await db.flush()
    await write_audit(
        db,
        action="EXPERIMENT_TOGGLE",
        resource_type="experiment",
        resource_id=exp.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={
            "before": {"ingest": before[0], "apply": before[1]},
            "after": {"ingest": exp.ingest_enabled, "apply": exp.apply_enabled},
        },
    )
    await db.commit()
    return _summary(exp, routing)


@router.post("/{experiment_id}/routing", response_model=ExperimentSummary)
async def update_routing(
    experiment_id: str,
    body: RoutingUpdateRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> ExperimentSummary:
    ensure_permission(auth, "model", "route")
    exp, routing = await _load_exp(db, experiment_id)
    old = (routing.weight_a, routing.weight_b)
    routing.weight_a = body.weight_a
    routing.weight_b = 100 - body.weight_a
    await db.flush()
    await write_audit(
        db,
        action="ROUTING_CHANGE",
        resource_type="experiment",
        resource_id=exp.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={
            "from": {"weight_a": old[0], "weight_b": old[1]},
            "to": {"weight_a": routing.weight_a, "weight_b": routing.weight_b},
        },
    )
    await db.commit()
    return _summary(exp, routing)


@router.post("/{experiment_id}/rollback", response_model=ExperimentSummary)
async def rollback(
    experiment_id: str,
    body: RollbackRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> ExperimentSummary:
    ensure_permission(auth, "model", "rollback")
    if body.trigger not in ("manual", "metric"):
        raise Conflict(error="invalid_trigger", message="trigger must be manual or metric")
    exp, routing = await _load_exp(db, experiment_id)
    # Atomic flip to (100, 0) — restore champion entirely.
    routing.weight_a = 100
    routing.weight_b = 0
    # Gate the rollback arm: halt further ingest + apply on this experiment so a
    # subsequent challenger cannot silently re-contaminate signals.
    exp.ingest_enabled = False
    exp.apply_enabled = False
    rb = RollbackEvent(
        experiment_id=exp.id,
        trigger=body.trigger,
        triggered_by=uuid.UUID(auth.user_id),
        reason=body.reason,
        metrics_snapshot=metrics.snapshot(),
    )
    db.add(rb)
    await db.flush()
    await write_audit(
        db,
        action="MODEL_ROLLBACK",
        resource_type="experiment",
        resource_id=exp.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={"trigger": body.trigger, "rollback_event_id": str(rb.id)},
    )
    await db.commit()
    return _summary(exp, routing)
