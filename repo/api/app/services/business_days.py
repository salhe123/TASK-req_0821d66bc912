"""Business-day calendar: Mon–Fri minus explicit holiday dates."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Iterable


def _to_date(value: str | date) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(value)


def _holiday_set(holidays: Iterable[str | date] | None) -> set[date]:
    if not holidays:
        return set()
    return {_to_date(h) for h in holidays}


def is_business_day(d: date, holidays: Iterable[str | date] | None = None) -> bool:
    if d.weekday() >= 5:  # Sat=5, Sun=6
        return False
    if d in _holiday_set(holidays):
        return False
    return True


def add_business_days(
    start: date, n: int, holidays: Iterable[str | date] | None = None
) -> date:
    """Return the calendar date that is `n` business days after `start`.

    `n=0` returns the next business day on or after `start`.
    """
    if n < 0:
        raise ValueError("n must be >= 0")
    hol = _holiday_set(holidays)
    current = start
    remaining = n
    # First advance to the next business day (inclusive of start).
    while not (current.weekday() < 5 and current not in hol):
        current += timedelta(days=1)
    while remaining > 0:
        current += timedelta(days=1)
        while not (current.weekday() < 5 and current not in hol):
            current += timedelta(days=1)
        remaining -= 1
    return current


def business_days_between(start: date, end: date, holidays: Iterable[str | date] | None = None) -> int:
    """Count business days strictly between start (exclusive) and end (inclusive),
    returning 0 if end <= start. Negative if end < start."""
    if end <= start:
        return 0
    hol = _holiday_set(holidays)
    count = 0
    cursor = start
    while cursor < end:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5 and cursor not in hol:
            count += 1
    return count


def effective_deadline(
    deadline_at: datetime,
    makeup_enabled: bool,
    makeup_business_days: int,
    holidays: Iterable[str | date] | None,
) -> datetime:
    """End-of-day (23:59:59 in deadline_at's tz) of the Nth business day after
    the deadline, or the original deadline if makeup is disabled."""
    if not makeup_enabled or makeup_business_days <= 0:
        return deadline_at
    base_date = deadline_at.date()
    makeup_date = add_business_days(base_date + timedelta(days=1), makeup_business_days - 1, holidays)
    return datetime(
        makeup_date.year,
        makeup_date.month,
        makeup_date.day,
        23,
        59,
        59,
        tzinfo=deadline_at.tzinfo or timezone.utc,
    )
