"""Rule-set management endpoints.

Rule sets parameterise outlier / threshold behaviour for scoring. Versions are
immutable once published and referenced by evaluation cycles; new rule logic
ships as a new version_no, never by mutating a prior version.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_session
from app.core.errors import Conflict, NotFound
from app.middleware.auth import get_auth
from app.models.scoring import RuleSet, RuleSetVersion
from app.schemas.rule_sets import (
    RuleSetCreateRequest,
    RuleSetListResponse,
    RuleSetSummary,
    RuleSetVersionCreateRequest,
    RuleSetVersionSummary,
)
from app.services.audit import write_audit
from app.services.rbac import AuthContext, ensure_permission

router = APIRouter(prefix="/rule_sets", tags=["rule_sets"])


def _version_summary(v: RuleSetVersion) -> RuleSetVersionSummary:
    return RuleSetVersionSummary(
        id=str(v.id),
        rule_set_id=str(v.rule_set_id),
        version_no=v.version_no,
        rules=dict(v.rules or {}),
        published_at=v.published_at.isoformat(),
    )


def _summary(r: RuleSet) -> RuleSetSummary:
    versions = sorted(r.versions, key=lambda v: v.version_no)
    latest = versions[-1]
    return RuleSetSummary(
        id=str(r.id),
        name=r.name,
        description=r.description,
        latest_version_id=str(latest.id),
        latest_version_no=latest.version_no,
        rules=dict(latest.rules or {}),
        versions=[_version_summary(v) for v in versions],
    )


@router.get("", response_model=RuleSetListResponse)
async def list_rule_sets(
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> RuleSetListResponse:
    ensure_permission(auth, "rule_set", "manage")
    rows = (
        await db.execute(
            select(RuleSet)
            .options(selectinload(RuleSet.versions))
            .order_by(RuleSet.name)
        )
    ).scalars().all()
    return RuleSetListResponse(items=[_summary(r) for r in rows])


@router.post("", response_model=RuleSetSummary, status_code=201)
async def create_rule_set(
    body: RuleSetCreateRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> RuleSetSummary:
    ensure_permission(auth, "rule_set", "manage")
    exists = (
        await db.execute(select(RuleSet).where(RuleSet.name == body.name))
    ).scalar_one_or_none()
    if exists is not None:
        raise Conflict(error="rule_set_name_taken", message="rule set name already exists")
    rs = RuleSet(name=body.name, description=body.description)
    db.add(rs)
    await db.flush()
    version = RuleSetVersion(rule_set_id=rs.id, version_no=1, rules=body.rules)
    db.add(version)
    await db.flush()
    await write_audit(
        db,
        action="RULE_SET_CREATE",
        resource_type="rule_set",
        resource_id=rs.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={"name": rs.name, "initial_version_id": str(version.id)},
    )
    await db.commit()
    rs = (
        await db.execute(
            select(RuleSet)
            .where(RuleSet.id == rs.id)
            .options(selectinload(RuleSet.versions))
        )
    ).scalar_one()
    return _summary(rs)


@router.post(
    "/{rule_set_id}/versions",
    response_model=RuleSetVersionSummary,
    status_code=201,
)
async def publish_version(
    rule_set_id: str,
    body: RuleSetVersionCreateRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> RuleSetVersionSummary:
    ensure_permission(auth, "rule_set", "manage")
    try:
        rid = uuid.UUID(rule_set_id)
    except ValueError:
        raise NotFound(message="rule set not found")
    rs = (
        await db.execute(
            select(RuleSet)
            .where(RuleSet.id == rid)
            .options(selectinload(RuleSet.versions))
        )
    ).scalar_one_or_none()
    if rs is None:
        raise NotFound(message="rule set not found")
    next_no = max((v.version_no for v in rs.versions), default=0) + 1
    version = RuleSetVersion(rule_set_id=rs.id, version_no=next_no, rules=body.rules)
    db.add(version)
    await db.flush()
    await write_audit(
        db,
        action="RULE_SET_VERSION_PUBLISH",
        resource_type="rule_set",
        resource_id=rs.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={"version_no": next_no, "version_id": str(version.id)},
    )
    await db.commit()
    return _version_summary(version)
