from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FeedbackKind(str, enum.Enum):
    LIKE = "LIKE"
    NOT_INTERESTED = "NOT_INTERESTED"
    BLOCK = "BLOCK"


class FeedbackEvent(Base):
    __tablename__ = "feedback_events"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('LIKE','NOT_INTERESTED','BLOCK')",
            name="ck_feedback_kind",
        ),
        CheckConstraint(
            "arm IN ('A','B')",
            name="ck_feedback_arm",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
    )
    arm: Mapped[str] = mapped_column(String(1), nullable=False)
    subject_key: Mapped[str] = mapped_column(String(200), nullable=False)
    target_id: Mapped[str] = mapped_column(String(200), nullable=False)
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("model_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    ingest_enabled_at_time: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FeedbackSignal(Base):
    __tablename__ = "feedback_signals"
    __table_args__ = (
        UniqueConstraint(
            "experiment_id", "arm", "target_id", name="uq_feedback_signals_triple"
        ),
        CheckConstraint("arm IN ('A','B')", name="ck_feedback_signals_arm"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
    )
    arm: Mapped[str] = mapped_column(String(1), nullable=False)
    target_id: Mapped[str] = mapped_column(String(200), nullable=False)
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    not_interested_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SubjectBlock(Base):
    __tablename__ = "subject_blocks"
    __table_args__ = (
        UniqueConstraint("subject_key", "target_id", name="uq_subject_blocks_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    subject_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
