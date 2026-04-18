from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from app.core.settings import get_settings

_kek_cache: bytes | None = None


def load_kek() -> bytes:
    global _kek_cache
    if _kek_cache is not None:
        return _kek_cache
    path: Path = get_settings().kek_path
    if not path.exists():
        raise RuntimeError(f"KEK missing at {path}")
    data = path.read_bytes()
    if len(data) < 32:
        raise RuntimeError("KEK must be ≥ 32 bytes")
    _kek_cache = data
    return data


def reset_kek_cache() -> None:
    global _kek_cache
    _kek_cache = None


def kek_fingerprint() -> str:
    """SHA-256 hex of the KEK — safe to log/audit."""
    return sha256(load_kek()).hexdigest()


def kek_is_present() -> bool:
    return get_settings().kek_path.exists()
