import hashlib
import os

import pytest

from app.core.settings import get_settings
from app.services import kek as kek_module
from app.services.backup_archive import (
    BackupDecryptError,
    decrypt_payload,
    encrypt_payload,
    manifest_hash_for_bytes,
    verify_kek_fingerprint,
)


@pytest.fixture(autouse=True)
def _with_kek(tmp_path, monkeypatch):
    kek_path = tmp_path / "kek"
    kek_path.write_bytes(os.urandom(32))
    monkeypatch.setenv("KEK_PATH", str(kek_path))
    monkeypatch.setenv("BACKUP_VOLUME", str(tmp_path / "backups"))
    get_settings.cache_clear()
    kek_module.reset_kek_cache()
    yield
    get_settings.cache_clear()
    kek_module.reset_kek_cache()


def test_manifest_hash_is_sha256_hex():
    h = manifest_hash_for_bytes(b"abc")
    assert h == hashlib.sha256(b"abc").hexdigest()
    assert len(h) == 64


def test_manifest_hash_stable():
    assert manifest_hash_for_bytes(b"payload") == manifest_hash_for_bytes(b"payload")


def test_encrypt_payload_round_trip_authenticated():
    data = b"hello"
    out = encrypt_payload(data)
    # Framing: MAGIC(4) + VERSION(1) + NONCE(12) + ciphertext+tag
    # Ciphertext is never equal to plaintext (confidentiality is real now).
    assert out[:4] == b"MGEW"
    assert out[4] == 0x01
    assert data not in out
    assert decrypt_payload(out) == data


def test_decrypt_payload_rejects_tamper():
    data = b"sensitive"
    out = bytearray(encrypt_payload(data))
    # Flip a byte in the ciphertext region — AES-GCM auth tag must reject.
    out[-5] ^= 0x01
    with pytest.raises(BackupDecryptError):
        decrypt_payload(bytes(out))


def test_decrypt_payload_rejects_bad_magic():
    with pytest.raises(BackupDecryptError):
        decrypt_payload(b"XXXX" + b"\x01" + b"\x00" * 28)


def test_verify_kek_fingerprint_matches_current():
    from app.services.kek import kek_fingerprint
    assert verify_kek_fingerprint(kek_fingerprint()) is True
    assert verify_kek_fingerprint("0" * 64) is False
