"""In-process maintenance flag used during a two-phase restore.

When a restore is staged, the API enters maintenance mode:
  - Non-admin requests receive 503 `maintenance`
  - Admin requests continue through so they can commit or abort

This is module-level state because the compose stack runs a single API worker
inside the air-gapped host. In a multi-worker deployment the flag would need to
live in the DB; that's out of scope for the phased plan.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _State:
    active: bool = False
    reason: str = ""
    archive_id: str | None = None
    started_by: str | None = None


_state = _State()


def is_active() -> bool:
    return _state.active


def enter(archive_id: str, started_by: str, reason: str = "restore staging") -> None:
    _state.active = True
    _state.archive_id = archive_id
    _state.started_by = started_by
    _state.reason = reason


def exit_() -> None:
    _state.active = False
    _state.archive_id = None
    _state.started_by = None
    _state.reason = ""


def snapshot() -> dict:
    return {
        "active": _state.active,
        "reason": _state.reason,
        "archive_id": _state.archive_id,
        "started_by": _state.started_by,
    }
