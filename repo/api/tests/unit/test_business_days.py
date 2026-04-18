from datetime import date, datetime, timezone

import pytest

from app.services.business_days import (
    add_business_days,
    business_days_between,
    effective_deadline,
    is_business_day,
)


def test_is_business_day_weekday():
    assert is_business_day(date(2026, 4, 20))  # Mon
    assert is_business_day(date(2026, 4, 24))  # Fri


def test_is_business_day_weekend():
    assert not is_business_day(date(2026, 4, 25))  # Sat
    assert not is_business_day(date(2026, 4, 26))  # Sun


def test_is_business_day_honors_holiday():
    assert not is_business_day(date(2026, 5, 25), holidays=["2026-05-25"])


def test_add_business_days_skips_weekend():
    # Fri + 1 business day = next Mon
    assert add_business_days(date(2026, 4, 24), 1) == date(2026, 4, 27)


def test_add_business_days_skips_holiday_over_weekend():
    # Fri + 1 business day, next Mon is holiday → Tue
    result = add_business_days(date(2026, 4, 24), 1, holidays=["2026-04-27"])
    assert result == date(2026, 4, 28)


def test_add_business_days_advances_to_next_business_day_when_start_is_weekend():
    assert add_business_days(date(2026, 4, 25), 0) == date(2026, 4, 27)  # Sat → Mon
    assert add_business_days(date(2026, 4, 25), 1) == date(2026, 4, 28)  # Sat + 1 → Tue


def test_add_business_days_rejects_negative():
    with pytest.raises(ValueError):
        add_business_days(date(2026, 4, 20), -1)


def test_business_days_between_zero_when_same_day():
    assert business_days_between(date(2026, 4, 20), date(2026, 4, 20)) == 0


def test_business_days_between_five():
    assert business_days_between(date(2026, 4, 20), date(2026, 4, 27)) == 5


def test_business_days_between_respects_holidays():
    assert (
        business_days_between(
            date(2026, 4, 20), date(2026, 4, 27), holidays=["2026-04-22"]
        )
        == 4
    )


def test_effective_deadline_disabled():
    dl = datetime(2026, 4, 24, 17, 0, 0, tzinfo=timezone.utc)
    assert effective_deadline(dl, makeup_enabled=False, makeup_business_days=5, holidays=[]) == dl


def test_effective_deadline_enabled_five_days():
    dl = datetime(2026, 4, 24, 17, 0, 0, tzinfo=timezone.utc)  # Fri
    eff = effective_deadline(dl, makeup_enabled=True, makeup_business_days=5, holidays=[])
    # Fri + 5 business days = Fri of next week (Apr 24 + Mon–Fri = May 1)
    assert eff.date() == date(2026, 5, 1)
    assert (eff.hour, eff.minute, eff.second) == (23, 59, 59)


def test_effective_deadline_respects_holiday_inside_makeup():
    dl = datetime(2026, 4, 24, 17, 0, 0, tzinfo=timezone.utc)  # Fri
    eff = effective_deadline(
        dl, makeup_enabled=True, makeup_business_days=5, holidays=["2026-04-28"]
    )
    # Holiday on Tue bumps by one day → Mon May 4
    assert eff.date() == date(2026, 5, 4)
