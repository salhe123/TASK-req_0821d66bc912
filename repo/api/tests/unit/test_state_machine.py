import pytest

from app.core.errors import Conflict
from app.models.cycle import AssignmentState as S
from app.services.state_machine import (
    ALLOWED_TRANSITIONS,
    can_transition,
    ensure_transition,
    expected_actor,
)


ALL = [s.value for s in S]


@pytest.mark.parametrize(
    "current,target",
    [
        (S.NOT_STARTED.value, S.IN_PROGRESS.value),
        (S.IN_PROGRESS.value, S.SUBMITTED.value),
        (S.SUBMITTED.value, S.RETURNED_FOR_REVISION.value),
        (S.SUBMITTED.value, S.ARCHIVED.value),
        (S.RETURNED_FOR_REVISION.value, S.IN_PROGRESS.value),
    ],
)
def test_allowed_transitions(current, target):
    assert can_transition(current, target)


@pytest.mark.parametrize("current", ALL)
def test_archived_is_terminal(current):
    if current == S.ARCHIVED.value:
        assert ALLOWED_TRANSITIONS[current] == set()


@pytest.mark.parametrize(
    "current,target",
    [
        (S.NOT_STARTED.value, S.SUBMITTED.value),
        (S.NOT_STARTED.value, S.ARCHIVED.value),
        (S.IN_PROGRESS.value, S.ARCHIVED.value),
        (S.IN_PROGRESS.value, S.RETURNED_FOR_REVISION.value),
        (S.SUBMITTED.value, S.IN_PROGRESS.value),
        (S.SUBMITTED.value, S.NOT_STARTED.value),
        (S.RETURNED_FOR_REVISION.value, S.SUBMITTED.value),
        (S.ARCHIVED.value, S.IN_PROGRESS.value),
    ],
)
def test_rejected_transitions_raise(current, target):
    assert not can_transition(current, target)
    with pytest.raises(Conflict) as ei:
        ensure_transition(current, target)
    assert ei.value.error == "invalid_transition"


def test_expected_actor():
    assert expected_actor(S.IN_PROGRESS.value, S.SUBMITTED.value) == "evaluator"
    assert expected_actor(S.SUBMITTED.value, S.ARCHIVED.value) == "reviewer"
    assert expected_actor("X", "Y") == "unknown"
