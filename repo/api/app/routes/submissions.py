from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_session
from app.core.errors import Conflict, Forbidden, NotFound
from app.middleware.auth import get_auth
from app.models.cycle import Assignment, AssignmentState
from app.models.scoring import CalculationTrace, GradeValue, Submission
from app.services.audit import write_audit
from app.services.canonical import canonical_json
from app.services.masking import apply_mask
from app.services.rbac import AuthContext, ensure_permission
from app.services.submissions import decrypt_grade_value

# Fields on a submission response whose raw values are considered sensitive;
# surfaces must have a matching entry in the caller's field_view_allowlist to
# see the real value, else they get MASK.
SUBMISSION_SENSITIVE = ("actor_user_id",)

router = APIRouter(prefix="/submissions", tags=["submissions"])


async def _load_submission(db: AsyncSession, submission_id: str) -> Submission:
    try:
        sid = uuid.UUID(submission_id)
    except ValueError:
        raise NotFound(message="submission not found")
    submission = (
        await db.execute(select(Submission).where(Submission.id == sid))
    ).scalar_one_or_none()
    if submission is None:
        raise NotFound(message="submission not found")
    return submission


async def _ensure_submission_access(
    db: AsyncSession, submission: Submission, auth: AuthContext
) -> None:
    """Only the submission's evaluator, the assignment's reviewer, or users
    with admin/review permission may read a submission and its trace."""
    if auth.has_permission("*", "*"):
        return
    if str(submission.actor_user_id) == auth.user_id:
        return
    assignment = (
        await db.execute(
            select(Assignment).where(Assignment.id == submission.assignment_id)
        )
    ).scalar_one_or_none()
    if assignment is not None:
        if str(assignment.evaluator_user_id) == auth.user_id:
            return
        if (
            assignment.reviewer_user_id is not None
            and str(assignment.reviewer_user_id) == auth.user_id
            and auth.has_permission("cycle", "review")
        ):
            return
    raise Forbidden(
        error="not_your_submission",
        message="not your submission",
    )


@router.get("/{submission_id}")
async def get_submission(
    submission_id: str,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> dict:
    s = await _load_submission(db, submission_id)
    await _ensure_submission_access(db, s, auth)
    return apply_mask(
        {
            "id": str(s.id),
            "assignment_id": str(s.assignment_id),
            "template_version_id": str(s.template_version_id),
            "rule_set_version_id": str(s.rule_set_version_id),
            "actor_user_id": str(s.actor_user_id),
            "submitted_at": s.submitted_at.isoformat(),
        },
        SUBMISSION_SENSITIVE,
        auth,
    )


@router.get("/{submission_id}/trace")
async def get_trace(
    submission_id: str,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> dict:
    s = await _load_submission(db, submission_id)
    await _ensure_submission_access(db, s, auth)
    trace = (
        await db.execute(select(CalculationTrace).where(CalculationTrace.submission_id == s.id))
    ).scalar_one_or_none()
    if trace is None:
        raise NotFound(message="trace not found")
    return {
        "submission_id": str(s.id),
        "template_version_id": str(trace.template_version_id),
        "rule_set_version_id": str(trace.rule_set_version_id),
        "trace": trace.trace_json,
        "trace_hash": trace.trace_hash,
        "computed_at": trace.computed_at.isoformat(),
    }


@router.post("/{submission_id}/grades/{item_key}")
async def edit_grade(
    submission_id: str,
    item_key: str,
    body: dict,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> dict:
    ensure_permission(auth, "cycle", "review")
    s = await _load_submission(db, submission_id)

    if not auth.has_permission("*", "*"):
        assignment = (
            await db.execute(
                select(Assignment).where(Assignment.id == s.assignment_id)
            )
        ).scalar_one_or_none()
        if (
            assignment is None
            or assignment.reviewer_user_id is None
            or str(assignment.reviewer_user_id) != auth.user_id
        ):
            raise Forbidden(
                error="not_assigned_reviewer",
                message="only the assigned reviewer may edit grades",
            )

    row = (
        await db.execute(
            select(GradeValue).where(
                GradeValue.submission_id == s.id, GradeValue.item_key == item_key
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFound(message="grade value not found")

    new_value = body.get("value", None)
    plaintext = canonical_json({"value": new_value})
    content_hash = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()

    from sqlalchemy import text
    from app.services.kek import load_kek

    kek_passphrase = load_kek().hex()
    if new_value is None:
        await db.execute(
            text(
                "UPDATE grade_values SET raw_value_encrypted = NULL, raw_present = FALSE, "
                "content_hash = :h WHERE id = :id"
            ),
            {"h": content_hash, "id": str(row.id)},
        )
    else:
        await db.execute(
            text(
                "UPDATE grade_values SET raw_value_encrypted = pgp_sym_encrypt(:pt, :pw), "
                "raw_present = TRUE, content_hash = :h WHERE id = :id"
            ),
            {"pt": plaintext, "pw": kek_passphrase, "h": content_hash, "id": str(row.id)},
        )

    await write_audit(
        db,
        action="GRADE_EDIT",
        resource_type="submission",
        resource_id=s.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={"item_key": item_key, "content_hash": content_hash},
    )
    await db.commit()
    return {
        "submission_id": str(s.id),
        "item_key": item_key,
        "content_hash": content_hash,
    }
