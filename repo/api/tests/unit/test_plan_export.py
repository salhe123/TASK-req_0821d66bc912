import os
import zipfile
from io import BytesIO

import pytest

from app.core.settings import get_settings
from app.services import kek as kek_module
from app.services.plan_export import build_bundle, verify_bundle, verify_signature, sign_bytes


@pytest.fixture(autouse=True)
def _with_kek(tmp_path, monkeypatch):
    kek_path = tmp_path / "kek"
    kek_path.write_bytes(os.urandom(32))
    monkeypatch.setenv("KEK_PATH", str(kek_path))
    get_settings.cache_clear()
    kek_module.reset_kek_cache()
    yield
    get_settings.cache_clear()
    kek_module.reset_kek_cache()


def test_bundle_roundtrip_verifies():
    bundle = build_bundle(
        plan_payload={"plan_id": "p", "version_no": 1, "lines": []},
        diff_payload=[],
    )
    assert verify_bundle(bundle) is True


def test_tampered_plan_json_breaks_signature():
    bundle = build_bundle(
        plan_payload={"plan_id": "p", "version_no": 1, "lines": [{"x": 1}]},
        diff_payload=[],
    )
    # Tamper by replacing plan.json inside the archive
    buf = BytesIO(bundle)
    with zipfile.ZipFile(buf, "r") as zin:
        entries = {name: zin.read(name) for name in zin.namelist()}
    entries["plan.json"] = b"{\"evil\":true}"
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in entries.items():
            zout.writestr(name, data)
    tampered = out.getvalue()
    assert verify_bundle(tampered) is False


def test_tampered_signature_rejected():
    bundle = build_bundle(
        plan_payload={"plan_id": "p", "version_no": 1},
        diff_payload=[],
    )
    buf = BytesIO(bundle)
    with zipfile.ZipFile(buf, "r") as zin:
        entries = {name: zin.read(name) for name in zin.namelist()}
    entries["signature"] = b"0" * 64
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in entries.items():
            zout.writestr(name, data)
    assert verify_bundle(out.getvalue()) is False


def test_sign_verify_matches():
    msg = b"hello"
    sig = sign_bytes(msg)
    assert verify_signature(msg, sig)
    assert not verify_signature(b"not hello", sig)
