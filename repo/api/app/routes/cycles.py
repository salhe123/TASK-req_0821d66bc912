from __future__ import annotations

import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_session
from app.core.errors import Conflict, NotFound
from app.middleware.auth import get_auth
from app.models.cycle import Assignment, AssignmentState, EvaluationCycle, TemplateVersion
from app.models.scoring import RuleSetVersion
from app.models.user import User
from app.schemas.cycles import (
    AssignmentAddRequest,
    AssignmentListResponse,
    AssignmentSummary,
    CycleCreateRequest,
    CycleListResponse,
    CycleSummary,
    DigestResponse,
)
from app.services.audit import write_audit
from app.services.business_days import effective_deadline
from app.services.digest import build_digest
from app.services.rbac import AuthContext, ensure_permission

router = APIRouter(prefix="/cycles", tags=["cycles"])


def _to_summary(c: EvaluationCycle) -> CycleSummary:
    eff = effective_deadline(c.deadline_at, c.makeup_enabled, c.makeup_business_days, c.holidays)
    return CycleSummary(
        id=str(c.id),
        name=c.name,
        starts_on=c.starts_on.isoformat(),
        ends_on=c.ends_on.isoformat(),
        deadline_at=c.deadline_at.isoformat(),
        effective_deadline_at=eff.isoformat(),
        timezone=c.timezone,
        makeup_enabled=c.makeup_enabled,
        makeup_business_days=c.makeup_business_days,
        holidays=list(c.holidays or []),
        template_version_id=str(c.template_version_id),
        rule_set_version_id=str(c.rule_set_version_id),
    )


def _to_assignment(a: Assignment) -> AssignmentSummary:
    return AssignmentSummary(
        id=str(a.id),
        cycle_id=str(a.cycle_id),
        evaluator_user_id=str(a.evaluator_user_id),
        reviewer_user_id=str(a.reviewer_user_id) if a.reviewer_user_id else None,
        state=a.state,
        submitted_at=a.submitted_at.isoformat() if a.submitted_at else None,
        late_flag=a.late_flag,
        returned_reason=a.returned_reason,
        archived_at=a.archived_at.isoformat() if a.archived_at else None,
    )


@router.get("", response_model=CycleListResponse)
async def list_cycles(
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> CycleListResponse:
    # Cycle listing is restricted to those who act on cycles directly. Any
    # non-participating role sees an empty list rather than leaking cycle
    # metadata.
    privileged = (
        auth.has_permission("cycle", "manage")
        or auth.has_permission("cycle", "review")
        or auth.has_permission("cycle", "participate")
    )
    if not privileged:
        return CycleListResponse(items=[])
    rows = (
        await db.execute(
            select(EvaluationCycle).order_by(EvaluationCycle.starts_on.desc())
        )
    ).scalars().all()
    return CycleListResponse(items=[_to_summary(c) for c in rows])


@router.post("", response_model=CycleSummary, status_code=201)
async def create_cycle(
    body: CycleCreateRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> CycleSummary:
    ensure_permission(auth, "cycle", "manage")
    try:
        tvid = uuid.UUID(body.template_version_id)
    except ValueError:
        raise NotFound(message="template version not found")
    tv = (
        await db.execute(select(TemplateVersion).where(TemplateVersion.id == tvid))
    ).scalar_one_or_none()
    if tv is None:
        raise NotFound(message="template version not found")

    if body.rule_set_version_id:
        try:
            rsvid = uuid.UUID(body.rule_set_version_id)
        except ValueError:
            raise NotFound(message="rule set version not found")
    else:
        rsvid = (
            await db.execute(
                select(RuleSetVersion.id).order_by(RuleSetVersion.published_at.asc()).limit(1)
            )
        ).scalar_one()
    rsv = (
        await db.execute(select(RuleSetVersion).where(RuleSetVersion.id == rsvid))
    ).scalar_one_or_none()
    if rsv is None:
        raise NotFound(message="rule set version not found")

    try:
        ZoneInfo(body.timezone)
    except Exception:
        raise Conflict(error="invalid_timezone", message="timezone not recognized")

    if body.ends_on < body.starts_on:
        raise Conflict(error="invalid_date_range", message="ends_on must be on/after starts_on")

    cycle = EvaluationCycle(
        name=body.name,
        starts_on=body.starts_on,
        ends_on=body.ends_on,
        deadline_at=body.deadline_at,
        timezone=body.timezone,
        makeup_enabled=body.makeup_enabled,
        makeup_business_days=body.makeup_business_days,
        holidays=body.holidays,
        template_version_id=tvid,
        rule_set_version_id=rsvid,
        created_by=uuid.UUID(auth.user_id),
    )
    db.add(cycle)
    await db.flush()
    await write_audit(
        db,
        action="CYCLE_CREATE",
        resource_type="cycle",
        resource_id=cycle.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={"name": cycle.name},
    )
    await db.commit()
    return _to_summary(cycle)


@router.get("/digest", response_model=DigestResponse)
async def get_digest(
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> DigestResponse:
    # Prefer the user's own timezone preference; fall back to a cycle
    # timezone (for legacy users who pre-date the preference column) and
    # finally UTC.
    user_tz = (
        await db.execute(
            select(User.timezone).where(User.id == uuid.UUID(auth.user_id))
        )
    ).scalar_one_or_none()
    if not user_tz:
        user_tz = "UTC"
    if user_tz == "UTC":
        row = (
            await db.execute(
                select(EvaluationCycle.timezone)
                .join(Assignment, Assignment.cycle_id == EvaluationCycle.id)
                .where(Assignment.evaluator_user_id == uuid.UUID(auth.user_id))
                .limit(1)
            )
        ).scalar_one_or_none()
        if row:
            user_tz = row
    payload = await build_digest(db, user_id=uuid.UUID(auth.user_id), tz_name=user_tz)
    await db.commit()
    return DigestResponse(**payload.to_dict())


@router.get("/{cycle_id}/assignments", response_model=AssignmentListResponse)
async def list_assignments(
    cycle_id: str,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> AssignmentListResponse:
    try:
        cid = uuid.UUID(cycle_id)
    except ValueError:
        raise NotFound(message="cycle not found")
    # Full-cycle listing is an administrative / reviewer concern. Evaluators
    # and reviewers without those permissions only see their own rows; callers
    # with no participation in the cycle at all get an empty list rather than
    # leaking participant identifiers.
    privileged = auth.has_permission("cycle", "manage") or auth.has_permission("cycle", "review")
    stmt = select(Assignment).where(Assignment.cycle_id == cid).order_by(Assignment.created_at)
    if not privileged:
        actor = uuid.UUID(auth.user_id)
        stmt = stmt.where(
            (Assignment.evaluator_user_id == actor)
            | (Assignment.reviewer_user_id == actor)
        )
    rows = (await db.execute(stmt)).scalars().all()
    return AssignmentListResponse(items=[_to_assignment(a) for a in rows])


@router.post("/{cycle_id}/assignments", response_model=AssignmentSummary, status_code=201)
async def add_assignment(
    cycle_id: str,
    body: AssignmentAddRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> AssignmentSummary:
    ensure_permission(auth, "cycle", "manage")
    try:
        cid = uuid.UUID(cycle_id)
        eid = uuid.UUID(body.evaluator_user_id)
    except ValueError:
        raise NotFound(message="cycle or evaluator not found")
    cycle = (await db.execute(select(EvaluationCycle).where(EvaluationCycle.id == cid))).scalar_one_or_none()
    if cycle is None:
        raise NotFound(message="cycle not found")
    evaluator = (await db.execute(select(User).where(User.id == eid))).scalar_one_or_none()
    if evaluator is None:
        raise NotFound(message="evaluator not found")

    existing = (
        await db.execute(
            select(Assignment).where(
                Assignment.cycle_id == cid, Assignment.evaluator_user_id == eid
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise Conflict(error="already_assigned", message="evaluator already assigned to this cycle")

    reviewer_id = None
    if body.reviewer_user_id:
        try:
            reviewer_id = uuid.UUID(body.reviewer_user_id)
        except ValueError:
            raise NotFound(message="reviewer not found")

    assignment = Assignment(
        cycle_id=cid,
        evaluator_user_id=eid,
        reviewer_user_id=reviewer_id,
    )
    db.add(assignment)
    await db.flush()
    await write_audit(
        db,
        action="PARTICIPANT_ADD_DROP",
        resource_type="assignment",
        resource_id=assignment.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={
            "op": "add",
            "cycle_id": str(cid),
            "evaluator_user_id": str(eid),
            "reviewer_user_id": str(reviewer_id) if reviewer_id else None,
        },
    )
    await db.commit()
    return _to_assignment(assignment)


@router.delete("/{cycle_id}/assignments/{assignment_id}", response_model=AssignmentSummary)
async def drop_assignment(
    cycle_id: str,
    assignment_id: str,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> AssignmentSummary:
    ensure_permission(auth, "cycle", "manage")
    try:
        aid = uuid.UUID(assignment_id)
    except ValueError:
        raise NotFound(message="assignment not found")
    assignment = (await db.execute(select(Assignment).where(Assignment.id == aid))).scalar_one_or_none()
    if assignment is None or str(assignment.cycle_id) != cycle_id:
        raise NotFound(message="assignment not found")
    if assignment.state != AssignmentState.NOT_STARTED.value:
        raise Conflict(
            error="cannot_drop_active_assignment",
            message="cannot drop an assignment that has started",
            details={"state": assignment.state},
        )
    snapshot = _to_assignment(assignment)
    await db.delete(assignment)
    await db.flush()
    await write_audit(
        db,
        action="PARTICIPANT_ADD_DROP",
        resource_type="assignment",
        resource_id=aid,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={"op": "drop", "cycle_id": cycle_id},
    )
    await db.commit()
    return snapshot
