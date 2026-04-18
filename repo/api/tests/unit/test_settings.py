from app.core.settings import Settings


def test_settings_has_expected_defaults(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("KEK_PATH", raising=False)
    s = Settings()
    assert s.session_token_skew_seconds == 60
    assert s.login_lockout_threshold == 5
    assert s.login_lockout_window_seconds == 15 * 60
    assert s.password_min_length == 12


def test_settings_override_via_env(monkeypatch):
    monkeypatch.setenv("LOGIN_LOCKOUT_THRESHOLD", "7")
    monkeypatch.setenv("PASSWORD_MIN_LENGTH", "16")
    s = Settings()
    assert s.login_lockout_threshold == 7
    assert s.password_min_length == 16
