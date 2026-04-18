from app.services.masking import MASK, apply_mask, mask_list
from app.services.rbac import AuthContext


def _ctx(allowlist):
    return AuthContext(
        user_id="u",
        username="user",
        roles=("Tester",),
        permissions=frozenset(),
        field_view_allowlist=frozenset(allowlist),
        session_id="s",
        csrf_token="c",
    )


def test_masks_sensitive_fields_for_unauthorized_caller():
    row = {"id": "1", "notes": "secret"}
    out = apply_mask(row, ["notes"], _ctx([]))
    assert out == {"id": "1", "notes": MASK}


def test_unmasks_when_in_allowlist():
    row = {"id": "1", "notes": "secret"}
    out = apply_mask(row, ["notes"], _ctx(["notes"]))
    assert out == {"id": "1", "notes": "secret"}


def test_wildcard_allowlist_unmasks_everything():
    row = {"id": "1", "notes": "secret", "ssn": "111"}
    out = apply_mask(row, ["notes", "ssn"], _ctx(["*"]))
    assert out == {"id": "1", "notes": "secret", "ssn": "111"}


def test_mask_list_applies_to_every_row():
    rows = [{"n": "a"}, {"n": "b"}]
    out = mask_list(rows, ["n"], _ctx([]))
    assert out == [{"n": MASK}, {"n": MASK}]


def test_ignores_absent_field():
    out = apply_mask({"a": 1}, ["b"], _ctx([]))
    assert out == {"a": 1}


def test_none_auth_masks_all():
    out = apply_mask({"n": "x"}, ["n"], None)
    assert out == {"n": MASK}
