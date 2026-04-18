"""pgcrypto helpers for encrypting/decrypting sensitive column values.

We use symmetric PGP encryption (`pgp_sym_encrypt`) keyed by the operator-mounted
KEK. Callers get SQL expressions they bind into INSERT / SELECT statements so the
key material never leaves the DB process's short-lived query parameters.
"""
from __future__ import annotations

from sqlalchemy import bindparam, func, literal

from app.services.kek import load_kek


def _kek_literal() -> str:
    # pgcrypto accepts bytea or text passphrases. We pass the raw KEK bytes as
    # hex text to avoid escaping issues; pgp_sym_encrypt treats any text as a
    # passphrase.
    return load_kek().hex()


def encrypt_expr(plaintext):
    """SQL expression: encrypt plaintext with the KEK."""
    return func.pgp_sym_encrypt(plaintext, literal(_kek_literal()))


def decrypt_expr(column):
    """SQL expression: decrypt column with the KEK, returning TEXT."""
    return func.pgp_sym_decrypt(column, literal(_kek_literal()))


async def encrypt_value(db, plaintext: str) -> bytes:
    from sqlalchemy import select

    result = await db.execute(select(encrypt_expr(bindparam("p", plaintext))))
    return result.scalar_one()


async def decrypt_value(db, ciphertext: bytes) -> str:
    from sqlalchemy import select

    result = await db.execute(select(decrypt_expr(bindparam("c", ciphertext))))
    return result.scalar_one()
