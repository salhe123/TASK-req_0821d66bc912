"""Persistence layer for submissions + calculation traces + encrypted grades."""
from __future__ import annotations

import hashlib
import uuid
from decimal import Decimal
from typing import Mapping

from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cycle import Assignment, EvaluationCycle
from app.models.scoring import (
    CalculationTrace,
    GradeValue,
    RuleSetVersion,
    Submission,
)
from app.services.canonical import canonical_json
from app.services.kek import load_kek
from app.services.scoring import ScoringContext, score_submission, trace_hash


def _content_hash(raw_canonical: str) -> str:
    return hashlib.sha256(raw_canonical.encode("utf-8")).hexdigest()


async def _prior_values_by_item(
    db: AsyncSession, template_version_id: uuid.UUID
) -> dict[str, list[Decimal]]:
    """Pull all prior trace step values for each item on the same template version.

    We read them from the trace_json (plaintext canonical values), which preserves
    decimal precision without needing to decrypt grade_values.
    """
    rows = (
        await db.execute(
            select(CalculationTrace.trace_json).where(
                CalculationTrace.template_version_id == template_version_id
            )
        )
    ).scalars().all()
    by_item: dict[str, list[Decimal]] = {}
    for trace in rows:
        for step in trace.get("steps", []):
            if not step.get("raw_present"):
                continue
            raw = step.get("raw_value")
            if raw is None:
                continue
            try:
                by_item.setdefault(step["item_key"], []).append(Decimal(str(raw)))
            except Exception:
                continue
    return by_item


async def persist_submission(
    db: AsyncSession,
    *,
    assignment: Assignment,
    cycle: EvaluationCycle,
    inputs: Mapping[str, object],
    actor_user_id: uuid.UUID,
) -> tuple[Submission, CalculationTrace]:
    template_version = assignment.cycle.template_version
    rule_version = (
        await db.execute(
            select(RuleSetVersion).where(RuleSetVersion.id == cycle.rule_set_version_id)
        )
    ).scalar_one()
    rules = rule_version.rules or {}
    outlier_z_default = Decimal(str(rules.get("outlier_z_default", "3.0")))

    priors = await _prior_values_by_item(db, template_version.id)

    ctx = ScoringContext(
        template_version_id=str(template_version.id),
        rule_set_version_id=str(rule_version.id),
        outlier_z_default=outlier_z_default,
    )
    trace = score_submission(
        template_items=list(template_version.items),
        inputs=inputs,
        ctx=ctx,
        prior_values_by_item=priors,
    )
    trace_json_str = canonical_json(trace)
    # Re-parse so JSONB receives a dict with canonical strings (not Decimal objects).
    import json as _json
    trace_jsonable = _json.loads(trace_json_str)

    inputs_canonical = canonical_json(inputs)

    submission = Submission(
        assignment_id=assignment.id,
        template_version_id=template_version.id,
        rule_set_version_id=rule_version.id,
        actor_user_id=actor_user_id,
        inputs_canonical=inputs_canonical,
    )
    db.add(submission)
    await db.flush()

    # Persist encrypted grade values.
    kek_passphrase = load_kek().hex()
    for step in trace["steps"]:
        item_key = step["item_key"]
        raw_present = step["raw_present"]
        raw_value = step["raw_value"] if raw_present else None
        raw_str = canonical_json({"item_key": item_key, "value": raw_value})
        row = GradeValue(
            submission_id=submission.id,
            item_key=item_key,
            raw_present=raw_present,
            content_hash=_content_hash(raw_str),
        )
        if raw_present:
            row.raw_value_encrypted = None  # filled via UPDATE below to avoid adapter issues
        db.add(row)
    await db.flush()

    for step in trace["steps"]:
        if not step["raw_present"]:
            continue
        plaintext = canonical_json({"value": step["raw_value"]})
        await db.execute(
            text(
                "UPDATE grade_values SET raw_value_encrypted = pgp_sym_encrypt(:pt, :pw) "
                "WHERE submission_id = :sid AND item_key = :ik"
            ),
            {"pt": plaintext, "pw": kek_passphrase, "sid": str(submission.id), "ik": step["item_key"]},
        )

    calc = CalculationTrace(
        submission_id=submission.id,
        template_version_id=template_version.id,
        rule_set_version_id=rule_version.id,
        trace_json=trace_jsonable,
        trace_hash=trace_hash(trace),
    )
    db.add(calc)
    await db.flush()
    return submission, calc


async def decrypt_grade_value(
    db: AsyncSession, *, submission_id: uuid.UUID, item_key: str
) -> str | None:
    """Return the decrypted plaintext canonical value for a stored grade, or None
    if the grade is marked absent."""
    kek_passphrase = load_kek().hex()
    row = (
        await db.execute(
            text(
                "SELECT raw_present, "
                "CASE WHEN raw_value_encrypted IS NULL THEN NULL "
                "ELSE pgp_sym_decrypt(raw_value_encrypted, :pw)::text END AS pt "
                "FROM grade_values WHERE submission_id = :sid AND item_key = :ik"
            ),
            {"pw": kek_passphrase, "sid": str(submission_id), "ik": item_key},
        )
    ).one_or_none()
    if row is None:
        return None
    return row.pt
