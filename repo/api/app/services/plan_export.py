"""Signed plan export bundle.

Layout:
  plan.json       — target version manifest (plan id, version, all BOM lines)
  diff.json       — structured diff vs parent (or [] when version 1)
  manifest.json   — {files: {name: sha256}}
  signature       — HMAC-SHA256 over canonical_json(manifest), hex-encoded

Verification: compute each file's sha256, canonicalize the manifest, HMAC with
the same KEK, and compare to the detached signature.
"""
from __future__ import annotations

import hashlib
import hmac
import io
import zipfile

from app.services.canonical import canonical_json
from app.services.kek import load_kek


SIGNATURE_FILENAME = "signature"
MANIFEST_FILENAME = "manifest.json"


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sign_bytes(message: bytes) -> str:
    return hmac.new(load_kek(), message, hashlib.sha256).hexdigest()


def verify_signature(message: bytes, signature_hex: str) -> bool:
    expected = sign_bytes(message)
    return hmac.compare_digest(expected.encode(), signature_hex.encode())


def build_bundle(*, plan_payload: dict, diff_payload: list[dict]) -> bytes:
    plan_bytes = canonical_json(plan_payload).encode("utf-8")
    diff_bytes = canonical_json(diff_payload).encode("utf-8")

    manifest = {
        "files": {
            "plan.json": _sha256_hex(plan_bytes),
            "diff.json": _sha256_hex(diff_bytes),
        }
    }
    manifest_bytes = canonical_json(manifest).encode("utf-8")
    signature_hex = sign_bytes(manifest_bytes)

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("plan.json", plan_bytes)
        zf.writestr("diff.json", diff_bytes)
        zf.writestr(MANIFEST_FILENAME, manifest_bytes)
        zf.writestr(SIGNATURE_FILENAME, signature_hex)
    return out.getvalue()


def verify_bundle(bundle_bytes: bytes) -> bool:
    with zipfile.ZipFile(io.BytesIO(bundle_bytes)) as zf:
        plan_bytes = zf.read("plan.json")
        diff_bytes = zf.read("diff.json")
        manifest_bytes = zf.read(MANIFEST_FILENAME)
        signature_hex = zf.read(SIGNATURE_FILENAME).decode("utf-8")

    import json as _json
    manifest = _json.loads(manifest_bytes)
    files = manifest.get("files", {})
    if files.get("plan.json") != _sha256_hex(plan_bytes):
        return False
    if files.get("diff.json") != _sha256_hex(diff_bytes):
        return False
    return verify_signature(manifest_bytes, signature_hex)
