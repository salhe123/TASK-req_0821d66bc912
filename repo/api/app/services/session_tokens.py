from __future__ import annotations

import base64
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from app.core.errors import Unauthorized
from app.core.settings import get_settings


@dataclass(frozen=True)
class TokenPayload:
    session_id: str
    user_id: str
    issued_at: int  # unix seconds
    nonce: str = ""


class SessionTokenError(Unauthorized):
    def __init__(self, error: str, message: str):
        super().__init__(error=error, message=message)


_signing_key_cache: bytes | None = None


def _load_signing_key() -> bytes:
    global _signing_key_cache
    if _signing_key_cache is not None:
        return _signing_key_cache
    path: Path = get_settings().session_signing_key_path
    if not path.exists():
        raise RuntimeError(f"session signing key missing at {path}")
    data = path.read_bytes()
    if len(data) < 32:
        raise RuntimeError("session signing key must be ≥ 32 bytes")
    _signing_key_cache = data
    return data


def reset_signing_key_cache() -> None:  # used by tests
    global _signing_key_cache
    _signing_key_cache = None


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def issue_token(
    session_id: str,
    user_id: str,
    now: int | None = None,
    nonce: str | None = None,
) -> str:
    iat = int(time.time()) if now is None else now
    nonce_value = nonce if nonce is not None else secrets.token_urlsafe(16)
    payload_json = json.dumps(
        {"sid": session_id, "uid": user_id, "iat": iat, "n": nonce_value},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    sig = hmac.new(_load_signing_key(), payload_json, sha256).digest()
    return f"{_b64url(payload_json)}.{_b64url(sig)}"


def verify_token(token: str, now: int | None = None) -> TokenPayload:
    settings = get_settings()
    skew = settings.session_token_skew_seconds
    current = int(time.time()) if now is None else now

    if not token or "." not in token:
        raise SessionTokenError("token_malformed", "session token is malformed")

    try:
        payload_part, sig_part = token.split(".", 1)
        payload_bytes = _b64url_decode(payload_part)
        sig = _b64url_decode(sig_part)
    except Exception:
        raise SessionTokenError("token_malformed", "session token is malformed")

    expected_sig = hmac.new(_load_signing_key(), payload_bytes, sha256).digest()
    if not hmac.compare_digest(sig, expected_sig):
        raise SessionTokenError("token_invalid_signature", "session token signature invalid")

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
        sid = str(payload["sid"])
        uid = str(payload["uid"])
        iat = int(payload["iat"])
        nonce = str(payload.get("n", ""))
    except (ValueError, KeyError, TypeError):
        raise SessionTokenError("token_malformed", "session token payload malformed")

    # Anti-replay / clock-skew guard: bounded acceptance window on both sides.
    # Reject tokens from the future beyond the skew allowance.
    if iat - current > skew:
        raise SessionTokenError("token_skew_exceeded", "session token clock skew exceeded")
    # Reject tokens older than the session max age + skew — replay of stale tokens.
    max_age = settings.session_token_max_age_seconds
    if current - iat > max_age + skew:
        raise SessionTokenError("token_expired", "session token is past max age")

    return TokenPayload(session_id=sid, user_id=uid, issued_at=iat, nonce=nonce)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)
