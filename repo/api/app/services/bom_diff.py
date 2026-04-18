"""Line-level BOM diff engine.

Matches lines between two versions by `line_identity_key` (not by row order /
`part_number`), so a part number rename is still recognized as the same line.

Change types (multiple may apply to one line):
  - ADDED              — present in target, absent in base
  - REMOVED            — present in base, absent in target
  - QUANTITY_CHANGED   — quantity differs (Decimal-aware)
  - PART_CHANGED       — part_number differs
  - NOTE_TAG_CHANGED   — notes or tags differ (tags compared as sorted set)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable, Mapping


@dataclass
class BomLineView:
    line_identity_key: str
    part_number: str
    description: str
    quantity: Decimal
    unit: str
    notes: str
    tags: list[str]

    @classmethod
    def from_mapping(cls, m: Mapping) -> "BomLineView":
        qty = m["quantity"]
        if not isinstance(qty, Decimal):
            qty = Decimal(str(qty))
        return cls(
            line_identity_key=str(m["line_identity_key"]),
            part_number=str(m["part_number"]),
            description=str(m.get("description", "")),
            quantity=qty,
            unit=str(m.get("unit", "ea")),
            notes=str(m.get("notes", "")),
            tags=list(m.get("tags", []) or []),
        )

    def to_dict(self) -> dict:
        return {
            "line_identity_key": self.line_identity_key,
            "part_number": self.part_number,
            "description": self.description,
            "quantity": str(self.quantity),
            "unit": self.unit,
            "notes": self.notes,
            "tags": list(self.tags),
        }


@dataclass
class DiffEntry:
    line_identity_key: str
    changes: list[str]
    base: BomLineView | None
    target: BomLineView | None

    def to_dict(self) -> dict:
        return {
            "line_identity_key": self.line_identity_key,
            "changes": sorted(self.changes),
            "base": self.base.to_dict() if self.base else None,
            "target": self.target.to_dict() if self.target else None,
        }


def _by_key(lines: Iterable[Mapping | BomLineView]) -> dict[str, BomLineView]:
    out: dict[str, BomLineView] = {}
    for line in lines:
        v = line if isinstance(line, BomLineView) else BomLineView.from_mapping(line)
        out[v.line_identity_key] = v
    return out


def diff(base_lines: Iterable, target_lines: Iterable) -> list[DiffEntry]:
    base = _by_key(base_lines)
    target = _by_key(target_lines)

    all_keys = sorted(set(base.keys()) | set(target.keys()))
    entries: list[DiffEntry] = []
    for key in all_keys:
        b = base.get(key)
        t = target.get(key)
        if b is None and t is not None:
            entries.append(DiffEntry(key, ["ADDED"], None, t))
            continue
        if b is not None and t is None:
            entries.append(DiffEntry(key, ["REMOVED"], b, None))
            continue
        assert b is not None and t is not None
        changes: list[str] = []
        if b.part_number != t.part_number:
            changes.append("PART_CHANGED")
        if b.quantity != t.quantity:
            changes.append("QUANTITY_CHANGED")
        if b.notes != t.notes or sorted(b.tags) != sorted(t.tags):
            changes.append("NOTE_TAG_CHANGED")
        if changes:
            entries.append(DiffEntry(key, sorted(changes), b, t))
        # identical → no entry emitted
    return entries
