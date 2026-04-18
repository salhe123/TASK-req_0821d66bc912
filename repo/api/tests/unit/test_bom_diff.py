from decimal import Decimal

from app.services.bom_diff import BomLineView, diff


def _line(**kwargs) -> dict:
    base = {
        "line_identity_key": "K1",
        "part_number": "P-1",
        "description": "",
        "quantity": Decimal("1"),
        "unit": "ea",
        "notes": "",
        "tags": [],
    }
    base.update(kwargs)
    return base


def test_identical_produces_empty_diff():
    lines = [_line(line_identity_key="A", part_number="X"), _line(line_identity_key="B", part_number="Y")]
    assert diff(lines, lines) == []


def test_added_detected():
    entries = diff([], [_line(line_identity_key="A")])
    assert len(entries) == 1
    assert entries[0].changes == ["ADDED"]


def test_removed_detected():
    entries = diff([_line(line_identity_key="A")], [])
    assert len(entries) == 1
    assert entries[0].changes == ["REMOVED"]


def test_quantity_changed_only():
    base = [_line(line_identity_key="A", quantity=Decimal("1"))]
    target = [_line(line_identity_key="A", quantity=Decimal("2"))]
    entries = diff(base, target)
    assert entries[0].changes == ["QUANTITY_CHANGED"]


def test_part_changed_only():
    base = [_line(line_identity_key="A", part_number="OLD")]
    target = [_line(line_identity_key="A", part_number="NEW")]
    entries = diff(base, target)
    assert entries[0].changes == ["PART_CHANGED"]


def test_note_tag_changed():
    base = [_line(line_identity_key="A", notes="n1")]
    target = [_line(line_identity_key="A", notes="n2")]
    entries = diff(base, target)
    assert entries[0].changes == ["NOTE_TAG_CHANGED"]


def test_tags_sorted_comparison():
    base = [_line(line_identity_key="A", tags=["b", "a"])]
    target = [_line(line_identity_key="A", tags=["a", "b"])]
    assert diff(base, target) == []


def test_multiple_changes_combined_on_one_line():
    base = [_line(line_identity_key="A", part_number="OLD", quantity=Decimal("1"), notes="n1")]
    target = [_line(line_identity_key="A", part_number="NEW", quantity=Decimal("2"), notes="n2")]
    entries = diff(base, target)
    assert entries[0].changes == ["NOTE_TAG_CHANGED", "PART_CHANGED", "QUANTITY_CHANGED"]


def test_rename_held_stable_by_line_identity_key():
    """A part_number rename shows up as PART_CHANGED under the same identity, not as ADD+REMOVE."""
    base = [_line(line_identity_key="KEY", part_number="OLD")]
    target = [_line(line_identity_key="KEY", part_number="NEW")]
    entries = diff(base, target)
    assert len(entries) == 1
    assert entries[0].changes == ["PART_CHANGED"]
    assert entries[0].line_identity_key == "KEY"


def test_decimal_quantity_equality_normalizes():
    base = [_line(line_identity_key="A", quantity=Decimal("1.00"))]
    target = [_line(line_identity_key="A", quantity=Decimal("1"))]
    assert diff(base, target) == []


def test_diff_deterministic_order():
    base = [_line(line_identity_key="b"), _line(line_identity_key="a")]
    target = [_line(line_identity_key="c"), _line(line_identity_key="b", quantity=Decimal("2"))]
    entries = diff(base, target)
    keys = [e.line_identity_key for e in entries]
    assert keys == sorted(keys)
