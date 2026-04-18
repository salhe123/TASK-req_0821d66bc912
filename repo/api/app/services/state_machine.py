"""Assignment state machine.

Allowed transitions (see plan §Phase 2):
    NOT_STARTED              -> IN_PROGRESS            (evaluator first save)
    IN_PROGRESS              -> SUBMITTED              (evaluator submit)
    SUBMITTED                -> RETURNED_FOR_REVISION  (reviewer return + reason)
    SUBMITTED                -> ARCHIVED               (reviewer approve)
    RETURNED_FOR_REVISION    -> IN_PROGRESS            (evaluator resumes)

ARCHIVED is terminal.
"""
from __future__ import annotations

from app.core.errors import Conflict
from app.models.cycle import AssignmentState


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    AssignmentState.NOT_STARTED.value: {AssignmentState.IN_PROGRESS.value},
    AssignmentState.IN_PROGRESS.value: {AssignmentState.SUBMITTED.value},
    AssignmentState.SUBMITTED.value: {
        AssignmentState.RETURNED_FOR_REVISION.value,
        AssignmentState.ARCHIVED.value,
    },
    AssignmentState.RETURNED_FOR_REVISION.value: {AssignmentState.IN_PROGRESS.value},
    AssignmentState.ARCHIVED.value: set(),
}


TRANSITION_ACTOR: dict[tuple[str, str], str] = {
    (AssignmentState.NOT_STARTED.value, AssignmentState.IN_PROGRESS.value): "evaluator",
    (AssignmentState.IN_PROGRESS.value, AssignmentState.SUBMITTED.value): "evaluator",
    (AssignmentState.RETURNED_FOR_REVISION.value, AssignmentState.IN_PROGRESS.value): "evaluator",
    (AssignmentState.SUBMITTED.value, AssignmentState.RETURNED_FOR_REVISION.value): "reviewer",
    (AssignmentState.SUBMITTED.value, AssignmentState.ARCHIVED.value): "reviewer",
}


def can_transition(current: str, target: str) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, set())


def ensure_transition(current: str, target: str) -> None:
    if not can_transition(current, target):
        raise Conflict(
            error="invalid_transition",
            message=f"cannot move from {current} to {target}",
            details={"current": current, "target": target},
        )


def expected_actor(current: str, target: str) -> str:
    return TRANSITION_ACTOR.get((current, target), "unknown")
