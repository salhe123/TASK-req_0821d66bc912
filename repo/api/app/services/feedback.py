"""Feedback service.

Invariants:
  - Events are ALWAYS recorded, even when experiment.ingest_enabled is False
    (the audit / replay surface needs them).
  - BLOCK events ALSO persist a SubjectBlock row independent of toggle state.
  - LIKE / NOT_INTERESTED update feedback_signals (per experiment/arm/target)
    only when ingest_enabled was True at record time.
  - Rate limit: at most 60 events per subject_key in the last 60 seconds
    (returns 429 `rate_limited` otherwise).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError, Conflict, NotFound
from app.models.feedback import FeedbackEvent, FeedbackKind, FeedbackSignal, SubjectBlock
from app.models.models import (
    Experiment,
    InferenceRouting,
    ModelVersion,
)


RATE_LIMIT_PER_MINUTE = 60


class RateLimited(ApiError):
    def __init__(self):
        super().__init__(
            error="rate_limited",
            message="too many feedback events for this subject; try again in a minute",
            status_code=429,
        )


@dataclass
class RecordedFeedback:
    event_id: str
    experiment_id: str
    arm: str
    subject_key: str
    target_id: str
    kind: str
    signal_updated: bool


async def _window_count(db: AsyncSession, subject_key: str, now: datetime) -> int:
    window_start = now - timedelta(seconds=60)
    stmt = select(func.count()).select_from(FeedbackEvent).where(
        FeedbackEvent.subject_key == subject_key,
        FeedbackEvent.created_at >= window_start,
    )
    return int((await db.execute(stmt)).scalar_one())


async def record_feedback(
    db: AsyncSession,
    *,
    experiment_id: str,
    subject_key: str,
    target_id: str,
    kind: str,
    arm: str | None = None,
    model_version_id: str | None = None,
    now: datetime | None = None,
) -> RecordedFeedback:
    if kind not in {k.value for k in FeedbackKind}:
        raise Conflict(
            error="invalid_feedback_kind",
            message="kind must be LIKE, NOT_INTERESTED, or BLOCK",
        )
    try:
        eid = uuid.UUID(experiment_id)
    except ValueError:
        raise NotFound(message="experiment not found")

    current = now or datetime.now(timezone.utc)

    # Rate limit per subject — BLOCKs count too (same abuse surface).
    if await _window_count(db, subject_key, current) >= RATE_LIMIT_PER_MINUTE:
        raise RateLimited()

    experiment = (
        await db.execute(select(Experiment).where(Experiment.id == eid))
    ).scalar_one_or_none()
    if experiment is None:
        raise NotFound(message="experiment not found")

    # Resolve and cross-check arm / model_version_id against the experiment's
    # current routing. Callers normally submit both when replaying a predict
    # response, but we must refuse combinations the router would never produce
    # — otherwise a stale client (or an attacker) could attribute signals to a
    # model the experiment isn't actually routing to.
    routing = (
        await db.execute(
            select(InferenceRouting).where(InferenceRouting.experiment_id == eid)
        )
    ).scalar_one()
    resolved_arm = arm or "A"
    if resolved_arm not in ("A", "B"):
        raise Conflict(error="invalid_arm", message="arm must be A or B")

    if resolved_arm == "B" and routing.model_b_id is None:
        raise Conflict(
            error="arm_not_routed",
            message="experiment has no B arm configured; cannot submit B feedback",
        )

    routed_mv_for_arm = (
        routing.model_a_id if resolved_arm == "A" else routing.model_b_id
    )

    if model_version_id is not None:
        try:
            mv_uuid = uuid.UUID(model_version_id)
        except ValueError:
            raise NotFound(message="model version not found")
        if mv_uuid != routed_mv_for_arm:
            other = (
                routing.model_b_id if resolved_arm == "A" else routing.model_a_id
            )
            if other is not None and mv_uuid == other:
                raise Conflict(
                    error="arm_model_mismatch",
                    message=(
                        "model_version_id does not match the experiment's "
                        f"routing for arm {resolved_arm}"
                    ),
                )
            raise Conflict(
                error="model_not_in_experiment",
                message="model_version_id is not routed by this experiment",
            )
    else:
        mv_uuid = routed_mv_for_arm

    mv = (
        await db.execute(select(ModelVersion).where(ModelVersion.id == mv_uuid))
    ).scalar_one_or_none()
    if mv is None:
        raise NotFound(message="model version not found")

    # Persist the event (always).
    event = FeedbackEvent(
        experiment_id=eid,
        arm=resolved_arm,
        subject_key=subject_key,
        target_id=target_id,
        model_version_id=mv_uuid,
        kind=kind,
        ingest_enabled_at_time=experiment.ingest_enabled,
    )
    db.add(event)
    await db.flush()

    # BLOCK is always applied regardless of toggle state.
    if kind == FeedbackKind.BLOCK.value:
        await db.execute(
            pg_insert(SubjectBlock)
            .values(subject_key=subject_key, target_id=target_id)
            .on_conflict_do_nothing(index_elements=["subject_key", "target_id"])
        )

    signal_updated = False
    if (
        kind in (FeedbackKind.LIKE.value, FeedbackKind.NOT_INTERESTED.value)
        and experiment.ingest_enabled
    ):
        await _upsert_signal(
            db,
            experiment_id=eid,
            arm=resolved_arm,
            target_id=target_id,
            kind=kind,
            now=current,
        )
        signal_updated = True

    return RecordedFeedback(
        event_id=str(event.id),
        experiment_id=str(eid),
        arm=resolved_arm,
        subject_key=subject_key,
        target_id=target_id,
        kind=kind,
        signal_updated=signal_updated,
    )


async def _upsert_signal(
    db: AsyncSession,
    *,
    experiment_id: uuid.UUID,
    arm: str,
    target_id: str,
    kind: str,
    now: datetime,
) -> None:
    like_delta = 1 if kind == FeedbackKind.LIKE.value else 0
    ni_delta = 1 if kind == FeedbackKind.NOT_INTERESTED.value else 0
    ins = pg_insert(FeedbackSignal).values(
        experiment_id=experiment_id,
        arm=arm,
        target_id=target_id,
        like_count=like_delta,
        not_interested_count=ni_delta,
        last_updated_at=now,
    )
    stmt = ins.on_conflict_do_update(
        index_elements=["experiment_id", "arm", "target_id"],
        set_={
            "like_count": FeedbackSignal.like_count + like_delta,
            "not_interested_count": FeedbackSignal.not_interested_count + ni_delta,
            "last_updated_at": now,
        },
    )
    await db.execute(stmt)


async def is_subject_blocked(
    db: AsyncSession, *, subject_key: str, target_id: str
) -> bool:
    stmt = select(SubjectBlock.id).where(
        SubjectBlock.subject_key == subject_key,
        SubjectBlock.target_id == target_id,
    )
    return (await db.execute(stmt)).scalar_one_or_none() is not None
