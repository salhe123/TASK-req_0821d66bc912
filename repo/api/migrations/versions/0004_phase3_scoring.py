"""phase 3 — scoring engine tables and cycle → rule_set binding

Revision ID: 0004_phase3_scoring
Revises: 0003_phase2_cycles
Create Date: 2026-04-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "0004_phase3_scoring"
down_revision: Union[str, None] = "0003_phase2_cycles"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TIMESTAMP = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "rule_sets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column("created_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "rule_set_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "rule_set_id",
            UUID(as_uuid=True),
            sa.ForeignKey("rule_sets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_no", sa.Integer, nullable=False),
        sa.Column("rules", JSONB, nullable=False),
        sa.Column("published_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("rule_set_id", "version_no", name="uq_rule_set_version_no"),
    )

    op.create_table(
        "submissions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("assignment_id", UUID(as_uuid=True), sa.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "template_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("template_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "rule_set_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("rule_set_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("actor_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("inputs_canonical", sa.Text, nullable=False),
        sa.Column("submitted_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_submissions_assignment_id", "submissions", ["assignment_id"])

    op.create_table(
        "grade_values",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("submission_id", UUID(as_uuid=True), sa.ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_key", sa.String(80), nullable=False),
        sa.Column("raw_value_encrypted", sa.LargeBinary, nullable=True),
        sa.Column("raw_present", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("submission_id", "item_key", name="uq_grade_values_submission_item"),
    )
    op.create_index("ix_grade_values_submission_id", "grade_values", ["submission_id"])
    op.create_index("ix_grade_values_item_key", "grade_values", ["item_key"])

    op.create_table(
        "calculation_traces",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("submission_id", UUID(as_uuid=True), sa.ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "template_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("template_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "rule_set_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("rule_set_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("trace_json", JSONB, nullable=False),
        sa.Column("trace_hash", sa.String(64), nullable=False),
        sa.Column("computed_at", TIMESTAMP, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("submission_id", name="uq_calculation_trace_submission"),
    )
    op.create_index("ix_calculation_traces_hash", "calculation_traces", ["trace_hash"])

    # Add rule_set_version_id to evaluation_cycles, nullable initially, backfill, then enforce.
    op.add_column(
        "evaluation_cycles",
        sa.Column("rule_set_version_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_evaluation_cycles_rule_set_version",
        source_table="evaluation_cycles",
        referent_table="rule_set_versions",
        local_cols=["rule_set_version_id"],
        remote_cols=["id"],
        ondelete="RESTRICT",
    )

    # Seed a default rule set with version 1.
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO rule_sets (name, description) "
            "VALUES ('Default', 'Default rule set: z-score outlier threshold 3.0')"
        )
    )
    conn.execute(
        sa.text(
            "INSERT INTO rule_set_versions (rule_set_id, version_no, rules) "
            "SELECT id, 1, CAST('{\"outlier_z_default\": \"3.0\"}' AS jsonb) "
            "FROM rule_sets WHERE name = 'Default'"
        )
    )
    # Backfill existing cycles.
    conn.execute(
        sa.text(
            "UPDATE evaluation_cycles SET rule_set_version_id = "
            "(SELECT v.id FROM rule_set_versions v "
            " JOIN rule_sets s ON s.id = v.rule_set_id "
            " WHERE s.name = 'Default' AND v.version_no = 1 LIMIT 1) "
            "WHERE rule_set_version_id IS NULL"
        )
    )
    op.alter_column("evaluation_cycles", "rule_set_version_id", nullable=False)


def downgrade() -> None:
    op.drop_constraint(
        "fk_evaluation_cycles_rule_set_version",
        "evaluation_cycles",
        type_="foreignkey",
    )
    op.drop_column("evaluation_cycles", "rule_set_version_id")
    op.drop_index("ix_calculation_traces_hash", table_name="calculation_traces")
    op.drop_table("calculation_traces")
    op.drop_index("ix_grade_values_item_key", table_name="grade_values")
    op.drop_index("ix_grade_values_submission_id", table_name="grade_values")
    op.drop_table("grade_values")
    op.drop_index("ix_submissions_assignment_id", table_name="submissions")
    op.drop_table("submissions")
    op.drop_table("rule_set_versions")
    op.drop_table("rule_sets")
