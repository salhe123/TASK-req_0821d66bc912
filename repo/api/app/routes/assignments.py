from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_session
from app.core.errors import Conflict, Forbidden, NotFound
from app.middleware.auth import get_auth
from app.models.cycle import Assignment, AssignmentState, EvaluationCycle
from app.schemas.cycles import (
    AssignmentFormResponse,
    AssignmentSummary,
    ReturnRequest,
    SaveDraftRequest,
    SubmitRequest,
)
from app.services.audit import write_audit
from app.services.business_days import effective_deadline
from app.services.rbac import AuthContext, ensure_permission
from app.services.state_machine import (
    AssignmentState as S,
    ensure_transition,
    expected_actor,
)
from app.services.submissions import persist_submission

router = APIRouter(prefix="/assignments", tags=["assignments"])


def _ensure_assigned_reviewer(a: Assignment, auth: AuthContext) -> None:
    """Reviewer actions require the actor to be the assigned reviewer,
    unless the actor holds a global admin wildcard permission."""
    if auth.has_permission("*", "*"):
        return
    if a.reviewer_user_id is None or str(a.reviewer_user_id) != auth.user_id:
        raise Forbidden(
            error="not_assigned_reviewer",
            message="only the assigned reviewer may perform this action",
        )


def _ensure_assignment_readable(a: Assignment, auth: AuthContext) -> None:
    """Assignment reads (detail + form) are allowed to: (a) admin wildcard,
    (b) the evaluator who owns the assignment, (c) the assigned reviewer.
    Holding cycle:review alone — without being the assigned reviewer — is no
    longer sufficient."""
    if auth.has_permission("*", "*"):
        return
    if str(a.evaluator_user_id) == auth.user_id:
        return
    if (
        a.reviewer_user_id is not None
        and str(a.reviewer_user_id) == auth.user_id
        and auth.has_permission("cycle", "review")
    ):
        return
    raise Forbidden(error="not_your_assignment", message="not your assignment")


def _serialize(a: Assignment) -> AssignmentSummary:
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


async def _get_assignment(db: AsyncSession, assignment_id: str) -> Assignment:
    try:
        aid = uuid.UUID(assignment_id)
    except ValueError:
        raise NotFound(message="assignment not found")
    assignment = (
        await db.execute(
            select(Assignment)
            .where(Assignment.id == aid)
            .options(selectinload(Assignment.cycle))
        )
    ).scalar_one_or_none()
    if assignment is None:
        raise NotFound(message="assignment not found")
    return assignment


@router.get("/{assignment_id}", response_model=AssignmentSummary)
async def get_assignment(
    assignment_id: str,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> AssignmentSummary:
    a = await _get_assignment(db, assignment_id)
    _ensure_assignment_readable(a, auth)
    return _serialize(a)


@router.get("/{assignment_id}/form", response_model=AssignmentFormResponse)
async def get_assignment_form(
    assignment_id: str,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> AssignmentFormResponse:
    a = await _get_assignment(db, assignment_id)
    _ensure_assignment_readable(a, auth)
    cycle = a.cycle
    template_version = cycle.template_version
    return AssignmentFormResponse(
        assignment=_serialize(a),
        cycle_name=cycle.name,
        deadline_at=cycle.deadline_at.isoformat(),
        template_version_id=str(template_version.id),
        items=list(template_version.items or []),
        draft_values=dict(a.draft_values or {}),
    )


@router.post("/{assignment_id}/save", response_model=AssignmentSummary)
async def save_draft(
    assignment_id: str,
    body: SaveDraftRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> AssignmentSummary:
    a = await _get_assignment(db, assignment_id)
    if str(a.evaluator_user_id) != auth.user_id:
        raise Forbidden(error="not_your_assignment", message="not your assignment")

    if a.state == S.NOT_STARTED.value:
        ensure_transition(a.state, S.IN_PROGRESS.value)
        a.state = S.IN_PROGRESS.value
    elif a.state not in (S.IN_PROGRESS.value, S.RETURNED_FOR_REVISION.value):
        raise Conflict(
            error="invalid_transition",
            message=f"cannot save in state {a.state}",
            details={"current": a.state},
        )
    elif a.state == S.RETURNED_FOR_REVISION.value:
        ensure_transition(a.state, S.IN_PROGRESS.value)
        a.state = S.IN_PROGRESS.value

    a.draft_values = body.values
    await db.flush()
    await db.commit()
    return _serialize(a)


@router.post("/{assignment_id}/submit", response_model=AssignmentSummary)
async def submit(
    assignment_id: str,
    body: SubmitRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> AssignmentSummary:
    a = await _get_assignment(db, assignment_id)
    if str(a.evaluator_user_id) != auth.user_id:
        raise Forbidden(error="not_your_assignment", message="not your assignment")

    if a.state == S.NOT_STARTED.value:
        a.state = S.IN_PROGRESS.value
    ensure_transition(a.state, S.SUBMITTED.value)

    cycle = a.cycle
    now = datetime.now(timezone.utc)
    is_late = now > cycle.deadline_at
    if is_late:
        if not cycle.makeup_enabled:
            raise Conflict(
                error="deadline_passed_no_makeup",
                message="submission deadline has passed",
                details={"deadline_at": cycle.deadline_at.isoformat()},
            )
        eff = effective_deadline(
            cycle.deadline_at,
            cycle.makeup_enabled,
            cycle.makeup_business_days,
            cycle.holidays,
        )
        if now > eff:
            raise Conflict(
                error="deadline_passed_no_makeup",
                message="makeup window has closed",
                details={"effective_deadline_at": eff.isoformat()},
            )

    a.draft_values = body.values
    a.state = S.SUBMITTED.value
    a.submitted_at = now
    a.late_flag = is_late
    await db.flush()

    submission, calc = await persist_submission(
        db,
        assignment=a,
        cycle=cycle,
        inputs=body.values,
        actor_user_id=uuid.UUID(auth.user_id),
    )

    await write_audit(
        db,
        action="SUBMISSION",
        resource_type="assignment",
        resource_id=a.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={
            "late": is_late,
            "submitted_at": now.isoformat(),
            "submission_id": str(submission.id),
            "trace_hash": calc.trace_hash,
        },
    )
    await db.commit()
    return _serialize(a)


@router.post("/{assignment_id}/return", response_model=AssignmentSummary)
async def return_for_revision(
    assignment_id: str,
    body: ReturnRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> AssignmentSummary:
    ensure_permission(auth, "cycle", "review")
    a = await _get_assignment(db, assignment_id)
    _ensure_assigned_reviewer(a, auth)
    ensure_transition(a.state, S.RETURNED_FOR_REVISION.value)
    a.state = S.RETURNED_FOR_REVISION.value
    a.returned_reason = body.reason
    await db.flush()
    await write_audit(
        db,
        action="SUBMISSION_RETURNED",
        resource_type="assignment",
        resource_id=a.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={"reason": body.reason},
    )
    await db.commit()
    return _serialize(a)


@router.post("/{assignment_id}/approve", response_model=AssignmentSummary)
async def approve(
    assignment_id: str,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> AssignmentSummary:
    ensure_permission(auth, "cycle", "review")
    a = await _get_assignment(db, assignment_id)
    _ensure_assigned_reviewer(a, auth)
    ensure_transition(a.state, S.ARCHIVED.value)
    a.state = S.ARCHIVED.value
    a.archived_at = datetime.now(timezone.utc)
    await db.flush()
    await write_audit(
        db,
        action="SUBMISSION_ARCHIVED",
        resource_type="assignment",
        resource_id=a.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={"archived_at": a.archived_at.isoformat()},
    )
    await db.commit()
    return _serialize(a)


@router.get("/mine/active", response_model=list[AssignmentSummary])
async def my_active(
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> list[AssignmentSummary]:
    rows = (
        await db.execute(
            select(Assignment)
            .where(Assignment.evaluator_user_id == uuid.UUID(auth.user_id))
            .where(Assignment.state != S.ARCHIVED.value)
            .order_by(Assignment.created_at.desc())
        )
    ).scalars().all()
    return [_serialize(a) for a in rows]
