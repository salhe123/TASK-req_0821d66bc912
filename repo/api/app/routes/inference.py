from __future__ import annotations

import uuid

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
)
from app.schemas.models import PredictRequest, PredictResponse
from app.services import inference, metrics
from app.services.rbac import AuthContext, ensure_permission
from app.services.routing import pick_arm

router = APIRouter(prefix="/inference", tags=["inference"])


@router.post("/predict", response_model=PredictResponse)
async def predict(
    body: PredictRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> PredictResponse:
    # Inference is an end-user surface tied to the feedback loop; callers
    # must hold feedback:submit (also held by Administrator wildcard).
    ensure_permission(auth, "feedback", "submit")
    try:
        eid = uuid.UUID(body.experiment_id)
    except ValueError:
        raise NotFound(message="experiment not found")

    exp = (
        await db.execute(select(Experiment).where(Experiment.id == eid))
    ).scalar_one_or_none()
    if exp is None:
        raise NotFound(message="experiment not found")
    if not exp.apply_enabled:
        raise Conflict(
            error="experiment_apply_disabled",
            message="experiment apply toggle is off",
        )

    routing = (
        await db.execute(
            select(InferenceRouting).where(InferenceRouting.experiment_id == eid)
        )
    ).scalar_one_or_none()
    if routing is None:
        raise NotFound(message="routing not found")

    arm = pick_arm(body.subject_key, routing.weight_a)
    mv_id = routing.model_a_id if arm == "A" else (routing.model_b_id or routing.model_a_id)
    if mv_id is None:
        raise Conflict(error="no_arm_configured", message="no model version configured for arm")

    mv = (await db.execute(select(ModelVersion).where(ModelVersion.id == mv_id))).scalar_one()
    result = inference.predict(
        subject_key=body.subject_key,
        experiment_id=exp.id,
        model_version_id=mv.id,
        artifact_params=mv.artifact_params or {},
        features=body.features,
        arm=arm,
    )
    return PredictResponse(
        subject_key=result.subject_key,
        experiment_id=result.experiment_id,
        arm=result.arm,
        model_version_id=result.model_version_id,
        score=result.score,
        latency_ms=result.latency_ms,
    )
