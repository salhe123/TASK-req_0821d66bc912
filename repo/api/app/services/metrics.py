"""In-process metrics registry.

Not a general-purpose metrics system — just enough to fulfill the plan:
  - requestsTotal, errorsTotal counters
  - inferenceP95Ms gauge + inferenceP95ViolationsTotal counter
  - activeSessions gauge
  - feedbackEventsPerMinute rolling gauge

All state is process-local and cleared on restart. Thread-safe via a single lock.
"""
from __future__ import annotations

import time
from bisect import insort
from collections import deque
from dataclasses import dataclass, field
from threading import Lock

P95_BUDGET_MS = 150.0
LATENCY_WINDOW = 512


@dataclass
class _State:
    requests_total: int = 0
    errors_total: int = 0
    inference_p95_violations_total: int = 0
    latencies_ms: deque = field(default_factory=lambda: deque(maxlen=LATENCY_WINDOW))
    active_sessions: int = 0
    feedback_events: deque = field(default_factory=lambda: deque(maxlen=2048))


_state = _State()
_lock = Lock()


def inc_request() -> None:
    with _lock:
        _state.requests_total += 1


def inc_error() -> None:
    with _lock:
        _state.errors_total += 1


def record_inference_latency_ms(latency_ms: float) -> None:
    with _lock:
        _state.latencies_ms.append(latency_ms)
        if latency_ms > P95_BUDGET_MS:
            _state.inference_p95_violations_total += 1


def set_active_sessions(n: int) -> None:
    with _lock:
        _state.active_sessions = n


def record_feedback_event(now: float | None = None) -> None:
    with _lock:
        _state.feedback_events.append(now or time.time())


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered: list[float] = []
    for v in values:
        insort(ordered, v)
    idx = int(round(0.95 * (len(ordered) - 1)))
    return ordered[idx]


def snapshot() -> dict:
    with _lock:
        now = time.time()
        one_min_ago = now - 60
        feedback_per_minute = sum(1 for t in _state.feedback_events if t >= one_min_ago)
        return {
            "requestsTotal": _state.requests_total,
            "errorsTotal": _state.errors_total,
            "inferenceP95Ms": round(_p95(list(_state.latencies_ms)), 3),
            "inferenceP95ViolationsTotal": _state.inference_p95_violations_total,
            "activeSessions": _state.active_sessions,
            "feedbackEventsPerMinute": feedback_per_minute,
            "p95BudgetMs": P95_BUDGET_MS,
        }


def reset_for_tests() -> None:
    with _lock:
        _state.requests_total = 0
        _state.errors_total = 0
        _state.inference_p95_violations_total = 0
        _state.latencies_ms.clear()
        _state.active_sessions = 0
        _state.feedback_events.clear()
