from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import Forbidden, NotFound
from app.middleware.auth import get_auth
from app.models.feedback import FeedbackSignal, SubjectBlock
from app.schemas.feedback import (
    BlockOut,
    BlocksResponse,
    FeedbackRequest,
    FeedbackResponse,
    SignalOut,
    SignalsResponse,
)
from app.services import metrics
from app.services.audit import write_audit
from app.services.feedback import record_feedback
from app.services.rbac import AuthContext, ensure_permission

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse, status_code=201)
async def submit_feedback(
    body: FeedbackRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> FeedbackResponse:
    ensure_permission(auth, "feedback", "submit")
    # Bind the event to the authenticated identity. A caller can only submit
    # feedback for their own subject_key unless they hold an admin wildcard
    # (operator override). Override submissions are audited so governance can
    # reconstruct who acted on whose behalf.
    is_override = False
    if body.subject_key != auth.user_id:
        if not auth.has_permission("*", "*"):
            raise Forbidden(
                error="subject_impersonation_forbidden",
                message="subject_key must match the authenticated user",
            )
        is_override = True
    result = await record_feedback(
        db,
        experiment_id=body.experiment_id,
        subject_key=body.subject_key,
        target_id=body.target_id,
        kind=body.kind,
        arm=body.arm,
        model_version_id=body.model_version_id,
    )
    metrics.record_feedback_event()
    if is_override:
        await write_audit(
            db,
            action="FEEDBACK_SUBJECT_OVERRIDE",
            resource_type="experiment",
            resource_id=uuid.UUID(body.experiment_id),
            actor_user_id=uuid.UUID(auth.user_id),
            payload={
                "subject_key": body.subject_key,
                "target_id": body.target_id,
                "kind": body.kind,
                "arm": body.arm,
            },
        )
    await db.commit()
    return FeedbackResponse(
        event_id=result.event_id,
        experiment_id=result.experiment_id,
        arm=result.arm,
        subject_key=result.subject_key,
        target_id=result.target_id,
        kind=result.kind,
        signal_updated=result.signal_updated,
    )


@router.get("/signals/{experiment_id}", response_model=SignalsResponse)
async def get_signals(
    experiment_id: str,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> SignalsResponse:
    ensure_permission(auth, "experiment", "manage")
    try:
        eid = uuid.UUID(experiment_id)
    except ValueError:
        raise NotFound(message="experiment not found")
    rows = (
        await db.execute(
            select(FeedbackSignal)
            .where(FeedbackSignal.experiment_id == eid)
            .order_by(FeedbackSignal.arm, FeedbackSignal.target_id)
        )
    ).scalars().all()
    return SignalsResponse(
        items=[
            SignalOut(
                experiment_id=str(r.experiment_id),
                arm=r.arm,
                target_id=r.target_id,
                like_count=r.like_count,
                not_interested_count=r.not_interested_count,
                last_updated_at=r.last_updated_at.isoformat(),
            )
            for r in rows
        ]
    )


@router.get("/blocks/{subject_key}", response_model=BlocksResponse)
async def get_blocks(
    subject_key: str,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> BlocksResponse:
    # Own-subject reads require feedback:submit; cross-subject enumeration
    # requires experiment:manage (a privileged surface).
    if subject_key == auth.user_id:
        ensure_permission(auth, "feedback", "submit")
    else:
        if not auth.has_permission("experiment", "manage") and not auth.has_permission("*", "*"):
            raise Forbidden(
                error="subject_scope_denied",
                message="cannot read blocks for another subject",
            )
    rows = (
        await db.execute(
            select(SubjectBlock)
            .where(SubjectBlock.subject_key == subject_key)
            .order_by(SubjectBlock.target_id)
        )
    ).scalars().all()
    return BlocksResponse(
        subject_key=subject_key,
        items=[BlockOut(target_id=r.target_id, created_at=r.created_at.isoformat()) for r in rows],
    )
