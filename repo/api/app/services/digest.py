"""Per-user 09:00-local digest banner builder.

Contract:
- Returns the digest payload only if (a) current local time is ≥ 09:00, and
  (b) this user has not yet been shown a digest today. Both conditions combined
  mean the digest is "generated on first session action after 09:00 local time".
- Once returned, the user's digest_last_shown_date is stamped to today so the
  next call the same day returns an empty (non-surfacing) payload.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cycle import Assignment, AssignmentState, EvaluationCycle
from app.models.user import User
from app.services.business_days import effective_deadline


LOCAL_BANNER_HOUR = 9


@dataclass
class DigestItem:
    assignment_id: str
    cycle_id: str
    cycle_name: str
    state: str
    deadline_at: str
    effective_deadline_at: str
    late_eligible: bool


@dataclass
class DigestPayload:
    show: bool
    as_of_local: str
    items: list[DigestItem]

    def to_dict(self) -> dict:
        return {
            "show": self.show,
            "as_of_local": self.as_of_local,
            "items": [item.__dict__ for item in self.items],
        }


def _now_local(tz_name: str, now_utc: datetime | None = None) -> datetime:
    tz = ZoneInfo(tz_name) if tz_name else timezone.utc
    base = now_utc or datetime.now(timezone.utc)
    return base.astimezone(tz)


async def build_digest(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    tz_name: str = "UTC",
    now_utc: datetime | None = None,
) -> DigestPayload:
    local = _now_local(tz_name, now_utc)
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        return DigestPayload(show=False, as_of_local=local.isoformat(), items=[])

    today = local.date()
    already_shown = user.digest_last_shown_date == today
    before_nine = local.time() < time(LOCAL_BANNER_HOUR, 0, 0)

    if already_shown or before_nine:
        return DigestPayload(show=False, as_of_local=local.isoformat(), items=[])

    stmt = (
        select(Assignment, EvaluationCycle)
        .join(EvaluationCycle, Assignment.cycle_id == EvaluationCycle.id)
        .where(Assignment.evaluator_user_id == user_id)
        .where(Assignment.state.notin_([AssignmentState.ARCHIVED.value]))
        .order_by(EvaluationCycle.deadline_at.asc())
    )
    rows = (await db.execute(stmt)).all()
    items: list[DigestItem] = []
    for assignment, cycle in rows:
        eff = effective_deadline(
            cycle.deadline_at,
            cycle.makeup_enabled,
            cycle.makeup_business_days,
            cycle.holidays,
        )
        items.append(
            DigestItem(
                assignment_id=str(assignment.id),
                cycle_id=str(cycle.id),
                cycle_name=cycle.name,
                state=assignment.state,
                deadline_at=cycle.deadline_at.isoformat(),
                effective_deadline_at=eff.isoformat(),
                late_eligible=cycle.makeup_enabled,
            )
        )

    user.digest_last_shown_date = today
    await db.flush()

    return DigestPayload(show=True, as_of_local=local.isoformat(), items=items)
