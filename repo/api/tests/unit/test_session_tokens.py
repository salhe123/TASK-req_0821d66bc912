import os
import time
from pathlib import Path

import pytest

from app.core.errors import Unauthorized
from app.core.settings import get_settings
from app.services import session_tokens as st


@pytest.fixture(autouse=True)
def _signing_key(tmp_path, monkeypatch):
    key_path = tmp_path / "signing_key"
    key_path.write_bytes(os.urandom(32))
    monkeypatch.setenv("SESSION_SIGNING_KEY_PATH", str(key_path))
    get_settings.cache_clear()
    st.reset_signing_key_cache()
    yield
    get_settings.cache_clear()
    st.reset_signing_key_cache()


def test_issue_and_verify_roundtrip():
    token = st.issue_token("sess-1", "user-1")
    p = st.verify_token(token)
    assert p.session_id == "sess-1"
    assert p.user_id == "user-1"
    assert abs(int(time.time()) - p.issued_at) < 5


def test_tampered_signature_rejected():
    token = st.issue_token("sess-1", "user-1")
    tampered = token[:-4] + "AAAA"
    with pytest.raises(Unauthorized) as ei:
        st.verify_token(tampered)
    assert ei.value.error in ("token_invalid_signature", "token_malformed")


def test_tampered_payload_rejected():
    token = st.issue_token("sess-1", "user-1")
    payload_part, sig = token.split(".")
    bad = payload_part[:-1] + "A.%s" % sig
    with pytest.raises(Unauthorized):
        st.verify_token(bad)


def test_future_token_rejected_beyond_skew():
    now = int(time.time())
    token = st.issue_token("sess-1", "user-1", now=now + 3600)
    with pytest.raises(Unauthorized) as ei:
        st.verify_token(token, now=now)
    assert ei.value.error == "token_skew_exceeded"


def test_future_token_within_skew_allowed():
    now = int(time.time())
    token = st.issue_token("sess-1", "user-1", now=now + 30)
    p = st.verify_token(token, now=now)
    assert p.session_id == "sess-1"


def test_malformed_token_rejected():
    with pytest.raises(Unauthorized):
        st.verify_token("not-a-valid-token")


def test_stale_token_rejected_past_max_age():
    """Post-audit anti-replay: tokens older than the session max age + skew
    must be rejected, even if the signature still verifies."""
    settings = get_settings()
    now = int(time.time())
    stale_at = now - settings.session_token_max_age_seconds - settings.session_token_skew_seconds - 10
    token = st.issue_token("sess-1", "user-1", now=stale_at)
    with pytest.raises(Unauthorized) as ei:
        st.verify_token(token, now=now)
    assert ei.value.error == "token_expired"


def test_nonce_round_trips():
    token = st.issue_token("sess-1", "user-1", nonce="abc-123")
    p = st.verify_token(token)
    assert p.nonce == "abc-123"


def test_missing_signing_key_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("SESSION_SIGNING_KEY_PATH", str(tmp_path / "absent"))
    get_settings.cache_clear()
    st.reset_signing_key_cache()
    with pytest.raises(RuntimeError):
        st.issue_token("s", "u")
