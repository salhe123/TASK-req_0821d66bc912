"""One-shot CLI that seeds the first Administrator user.

Usage (from inside the api container):
    python -m app.scripts.seed_admin --username admin

Reads the password from stdin (or the SEED_ADMIN_PASSWORD env var), verifies the
KEK is mounted, and writes a single AuditLog row for the creation.
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session_maker
from app.models.rbac import Role
from app.models.user import User
from app.services.audit import write_audit
from app.services.kek import load_kek
from app.services.passwords import hash_password


async def seed(username: str, password: str) -> int:
    load_kek()  # fails fast if missing
    maker = get_session_maker()
    async with maker() as db:  # type: AsyncSession
        existing = (
            await db.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()
        if existing is not None:
            print(f"user '{username}' already exists (id={existing.id})", file=sys.stderr)
            return 2

        admin_role = (
            await db.execute(select(Role).where(Role.name == "Administrator"))
        ).scalar_one_or_none()
        if admin_role is None:
            print("Administrator role not seeded — did migrations run?", file=sys.stderr)
            return 3

        user = User(
            username=username,
            display_name="Administrator",
            password_hash=hash_password(password),
            is_active=True,
        )
        user.roles = [admin_role]
        db.add(user)
        await db.flush()
        await write_audit(
            db,
            action="USER_CREATE",
            resource_type="user",
            resource_id=user.id,
            actor_user_id=user.id,
            payload={"username": username, "seeded": True},
        )
        await db.commit()
        print(f"seeded administrator: {username} ({user.id})")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    args = parser.parse_args()
    password = os.environ.get("SEED_ADMIN_PASSWORD")
    if not password:
        password = getpass.getpass("new admin password (≥12 chars): ")
    if len(password) < 12:
        print("password must be ≥ 12 characters", file=sys.stderr)
        return 1
    return asyncio.run(seed(args.username, password))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
