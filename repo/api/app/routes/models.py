from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_session
from app.core.errors import Conflict, NotFound
from app.middleware.auth import get_auth
from app.models.models import (
    ModelRun,
    ModelRunKind,
    ModelRunStatus,
    ModelVersion,
    ModelVersionStatus,
    RegisteredModel,
)
from app.schemas.models import (
    ModelCreateRequest,
    ModelListResponse,
    ModelRunCompleteRequest,
    ModelRunListResponse,
    ModelRunStartRequest,
    ModelRunSummary,
    ModelSummary,
    ModelVersionCreateRequest,
    ModelVersionSummary,
)
from app.services.audit import write_audit
from app.services.inference import warm as warm_artifact
from app.services.model_schema import diff_schemas, feature_schema_hash
from app.services.rbac import AuthContext, ensure_permission

router = APIRouter(prefix="/models", tags=["models"])


def _version_summary(v: ModelVersion) -> ModelVersionSummary:
    return ModelVersionSummary(
        id=str(v.id),
        model_id=str(v.model_id),
        version_no=v.version_no,
        status=v.status,
        feature_schema_hash=v.feature_schema_hash,
        artifact_uri=v.artifact_uri,
        created_at=v.created_at.isoformat(),
        approved_at=v.approved_at.isoformat() if v.approved_at else None,
    )


def _model_summary(m: RegisteredModel) -> ModelSummary:
    return ModelSummary(
        id=str(m.id),
        name=m.name,
        description=m.description,
        live_schema_hash=m.live_schema_hash,
        versions=[_version_summary(v) for v in m.versions],
    )


async def _load_model(db: AsyncSession, model_id: str) -> RegisteredModel:
    try:
        mid = uuid.UUID(model_id)
    except ValueError:
        raise NotFound(message="model not found")
    m = (
        await db.execute(
            select(RegisteredModel)
            .where(RegisteredModel.id == mid)
            .options(selectinload(RegisteredModel.versions))
        )
    ).scalar_one_or_none()
    if m is None:
        raise NotFound(message="model not found")
    return m


@router.get("", response_model=ModelListResponse)
async def list_models(
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> ModelListResponse:
    # Registry metadata is governance-scoped. Any of model:register,
    # model:promote, model:route, or model:run grants read access; others see
    # an empty list.
    if not any(
        auth.has_permission("model", a)
        for a in ("register", "promote", "route", "rollback", "run")
    ) and not auth.has_permission("*", "*"):
        return ModelListResponse(items=[])
    rows = (
        await db.execute(
            select(RegisteredModel)
            .options(selectinload(RegisteredModel.versions))
            .order_by(RegisteredModel.name)
        )
    ).scalars().all()
    return ModelListResponse(items=[_model_summary(m) for m in rows])


@router.post("", response_model=ModelSummary, status_code=201)
async def create_model(
    body: ModelCreateRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> ModelSummary:
    ensure_permission(auth, "model", "register")
    exists = (
        await db.execute(select(RegisteredModel).where(RegisteredModel.name == body.name))
    ).scalar_one_or_none()
    if exists is not None:
        raise Conflict(error="model_name_taken", message="model name already exists")
    m = RegisteredModel(
        name=body.name,
        description=body.description,
        created_by=uuid.UUID(auth.user_id),
    )
    db.add(m)
    await db.flush()
    await write_audit(
        db,
        action="MODEL_CREATE",
        resource_type="model",
        resource_id=m.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={"name": body.name},
    )
    await db.commit()
    m = await _load_model(db, str(m.id))
    return _model_summary(m)


@router.post("/{model_id}/versions", response_model=ModelVersionSummary, status_code=201)
async def register_version(
    model_id: str,
    body: ModelVersionCreateRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> ModelVersionSummary:
    ensure_permission(auth, "model", "register")
    m = await _load_model(db, model_id)
    schema = [fd.model_dump() for fd in body.feature_schema]
    h = feature_schema_hash(schema)
    next_no = max((v.version_no for v in m.versions), default=0) + 1
    v = ModelVersion(
        model_id=m.id,
        version_no=next_no,
        status=ModelVersionStatus.DRAFT.value,
        feature_schema=schema,
        feature_schema_hash=h,
        artifact_uri=body.artifact_uri,
        artifact_params=body.artifact_params,
    )
    db.add(v)
    await db.flush()
    await write_audit(
        db,
        action="MODEL_VERSION_REGISTER",
        resource_type="model",
        resource_id=m.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={"version_no": next_no, "feature_schema_hash": h},
    )
    await db.commit()
    warm_artifact(str(v.id), body.artifact_params)
    return _version_summary(v)


def _run_summary(r: ModelRun) -> ModelRunSummary:
    return ModelRunSummary(
        id=str(r.id),
        model_version_id=str(r.model_version_id),
        kind=r.kind,
        status=r.status,
        dataset_ref=r.dataset_ref,
        metrics=dict(r.metrics or {}),
        notes=r.notes,
        started_by=str(r.started_by) if r.started_by else None,
        started_at=r.started_at.isoformat(),
        completed_at=r.completed_at.isoformat() if r.completed_at else None,
    )


async def _resolve_version(
    db: AsyncSession, model_id: str, version_id: str
) -> tuple[RegisteredModel, ModelVersion]:
    m = await _load_model(db, model_id)
    try:
        vid = uuid.UUID(version_id)
    except ValueError:
        raise NotFound(message="model version not found")
    v = next((x for x in m.versions if x.id == vid), None)
    if v is None:
        raise NotFound(message="model version not found")
    return m, v


@router.post(
    "/{model_id}/versions/{version_id}/runs",
    response_model=ModelRunSummary,
    status_code=201,
)
async def start_run(
    model_id: str,
    version_id: str,
    body: ModelRunStartRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> ModelRunSummary:
    ensure_permission(auth, "model", "run")
    m, v = await _resolve_version(db, model_id, version_id)
    run = ModelRun(
        model_version_id=v.id,
        kind=body.kind,
        status=ModelRunStatus.RUNNING.value,
        dataset_ref=body.dataset_ref,
        notes=body.notes,
        started_by=uuid.UUID(auth.user_id),
    )
    db.add(run)
    await db.flush()
    await write_audit(
        db,
        action="MODEL_RUN_START",
        resource_type="model_version",
        resource_id=v.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={"run_id": str(run.id), "kind": body.kind},
    )
    await db.commit()
    return _run_summary(run)


@router.post(
    "/{model_id}/versions/{version_id}/runs/{run_id}/complete",
    response_model=ModelRunSummary,
)
async def complete_run(
    model_id: str,
    version_id: str,
    run_id: str,
    body: ModelRunCompleteRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> ModelRunSummary:
    ensure_permission(auth, "model", "run")
    m, v = await _resolve_version(db, model_id, version_id)
    try:
        rid = uuid.UUID(run_id)
    except ValueError:
        raise NotFound(message="run not found")
    run = (
        await db.execute(select(ModelRun).where(ModelRun.id == rid))
    ).scalar_one_or_none()
    if run is None or run.model_version_id != v.id:
        raise NotFound(message="run not found")
    if run.status in (ModelRunStatus.SUCCEEDED.value, ModelRunStatus.FAILED.value):
        raise Conflict(
            error="run_already_completed",
            message="run has already been completed",
        )
    run.status = body.status
    run.metrics = body.metrics
    if body.notes:
        run.notes = body.notes
    run.completed_at = datetime.now(timezone.utc)
    await db.flush()
    await write_audit(
        db,
        action="MODEL_RUN_COMPLETE",
        resource_type="model_version",
        resource_id=v.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={"run_id": str(run.id), "status": body.status},
    )
    await db.commit()
    return _run_summary(run)


@router.get(
    "/{model_id}/versions/{version_id}/runs",
    response_model=ModelRunListResponse,
)
async def list_runs(
    model_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> ModelRunListResponse:
    ensure_permission(auth, "model", "run")
    m, v = await _resolve_version(db, model_id, version_id)
    rows = (
        await db.execute(
            select(ModelRun)
            .where(ModelRun.model_version_id == v.id)
            .order_by(ModelRun.started_at.desc())
        )
    ).scalars().all()
    return ModelRunListResponse(items=[_run_summary(r) for r in rows])


@router.post("/{model_id}/versions/{version_id}/promote", response_model=ModelVersionSummary)
async def promote_version(
    model_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> ModelVersionSummary:
    ensure_permission(auth, "model", "promote")
    m = await _load_model(db, model_id)
    try:
        vid = uuid.UUID(version_id)
    except ValueError:
        raise NotFound(message="model version not found")
    v = next((x for x in m.versions if x.id == vid), None)
    if v is None:
        raise NotFound(message="model version not found")

    # Promotion gate: require at least one SUCCEEDED evaluation run on this version.
    successful_eval = (
        await db.execute(
            select(ModelRun.id).where(
                ModelRun.model_version_id == v.id,
                ModelRun.kind == ModelRunKind.EVALUATION.value,
                ModelRun.status == ModelRunStatus.SUCCEEDED.value,
            )
        )
    ).first()
    if successful_eval is None:
        raise Conflict(
            error="evaluation_run_required",
            message="a successful evaluation run is required before promotion",
        )

    # First promotion pins the live schema hash; subsequent must match it.
    if m.live_schema_hash is None:
        m.live_schema_hash = v.feature_schema_hash
    elif m.live_schema_hash != v.feature_schema_hash:
        approved_version = next(
            (x for x in m.versions if x.status == ModelVersionStatus.APPROVED.value), None
        )
        expected_schema = approved_version.feature_schema if approved_version else []
        missing, extra = diff_schemas(expected_schema, v.feature_schema)
        raise Conflict(
            error="feature_schema_mismatch",
            message="version feature schema does not match inference service",
            details={
                "expected_hash": m.live_schema_hash,
                "got_hash": v.feature_schema_hash,
                "missing_in_got": missing,
                "extra_in_got": extra,
            },
        )
    v.status = ModelVersionStatus.APPROVED.value
    v.approved_at = datetime.now(timezone.utc)
    await db.flush()
    await write_audit(
        db,
        action="MODEL_PROMOTION",
        resource_type="model",
        resource_id=m.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={"version_id": str(v.id), "feature_schema_hash": v.feature_schema_hash},
    )
    await db.commit()
    warm_artifact(str(v.id), v.artifact_params)
    return _version_summary(v)
