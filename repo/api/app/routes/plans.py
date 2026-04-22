from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_session
from app.core.errors import Conflict, NotFound
from app.middleware.auth import get_auth
from app.models.plans import BomLine, Plan, PlanShareLink, PlanVersion
from app.schemas.plans import (
    BomLineOut,
    DiffLineOut,
    DiffResponse,
    PlanCreateRequest,
    PlanListResponse,
    PlanSummary,
    PlanVersionCopyRequest,
    PlanVersionCreateRequest,
    PlanVersionDetail,
    PlanVersionSummary,
    RollbackRequest,
    ShareLinkCreateRequest,
    ShareLinkResponse,
    ShareLinkSummary,
)
from app.services.audit import write_audit
from app.services.bom_diff import BomLineView, diff as diff_lines
from app.services.canonical import canonical_json
from app.services.plan_export import build_bundle
from app.services.rbac import AuthContext, ensure_permission
from app.services.share_tokens import compute_expiry, hash_token, is_usable, new_token

router = APIRouter(prefix="/plans", tags=["plans"])


def _format_quantity(q) -> str:
    """Render a Numeric quantity without the DB's fixed-scale trailing zeros."""
    s = format(q, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s or "0"


def _line_out(line: BomLine) -> BomLineOut:
    return BomLineOut(
        line_identity_key=line.line_identity_key,
        part_number=line.part_number,
        description=line.description,
        quantity=_format_quantity(line.quantity),
        unit=line.unit,
        notes=line.notes,
        tags=list(line.tags or []),
    )


def _version_summary(v: PlanVersion) -> PlanVersionSummary:
    return PlanVersionSummary(
        id=str(v.id),
        plan_id=str(v.plan_id),
        version_no=v.version_no,
        parent_version_id=str(v.parent_version_id) if v.parent_version_id else None,
        note=v.note,
        created_at=v.created_at.isoformat(),
        created_by=str(v.created_by) if v.created_by else None,
    )


def _plan_summary(p: Plan) -> PlanSummary:
    versions = sorted(p.versions, key=lambda v: v.version_no)
    head = versions[-1]
    return PlanSummary(
        id=str(p.id),
        name=p.name,
        description=p.description,
        head_version_id=str(head.id),
        head_version_no=head.version_no,
        versions=[_version_summary(v) for v in versions],
    )


async def _load_plan(db: AsyncSession, plan_id: str) -> Plan:
    try:
        pid = uuid.UUID(plan_id)
    except ValueError:
        raise NotFound(message="plan not found")
    plan = (
        await db.execute(
            select(Plan)
            .where(Plan.id == pid)
            .options(selectinload(Plan.versions).selectinload(PlanVersion.lines))
        )
    ).scalar_one_or_none()
    if plan is None:
        raise NotFound(message="plan not found")
    return plan


async def _load_version(db: AsyncSession, version_id: str) -> PlanVersion:
    try:
        vid = uuid.UUID(version_id)
    except ValueError:
        raise NotFound(message="plan version not found")
    v = (
        await db.execute(
            select(PlanVersion)
            .where(PlanVersion.id == vid)
            .options(selectinload(PlanVersion.lines))
        )
    ).scalar_one_or_none()
    if v is None:
        raise NotFound(message="plan version not found")
    return v


async def _load_version_for_plan(
    db: AsyncSession, plan_id: str, version_id: str
) -> PlanVersion:
    """Load a version and verify it belongs to the given plan_id in the path."""
    try:
        pid = uuid.UUID(plan_id)
    except ValueError:
        raise NotFound(message="plan version not found")
    v = await _load_version(db, version_id)
    if v.plan_id != pid:
        raise NotFound(message="plan version not found")
    return v


@router.get("", response_model=PlanListResponse)
async def list_plans(
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> PlanListResponse:
    ensure_permission(auth, "build_plan", "view")
    rows = (
        await db.execute(
            select(Plan)
            .options(selectinload(Plan.versions))
            .order_by(Plan.name)
        )
    ).scalars().all()
    return PlanListResponse(items=[_plan_summary(p) for p in rows])


@router.post("", response_model=PlanSummary, status_code=201)
async def create_plan(
    body: PlanCreateRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> PlanSummary:
    ensure_permission(auth, "build_plan", "manage")

    exists = (
        await db.execute(select(Plan).where(Plan.name == body.name))
    ).scalar_one_or_none()
    if exists is not None:
        raise Conflict(error="plan_name_taken", message="plan name already exists")

    keys = [ln.line_identity_key for ln in body.lines]
    if len(set(keys)) != len(keys):
        raise Conflict(error="duplicate_line_identity", message="line_identity_key must be unique per version")

    plan = Plan(
        name=body.name,
        description=body.description,
        owner_user_id=uuid.UUID(auth.user_id),
    )
    db.add(plan)
    await db.flush()

    version = PlanVersion(
        plan_id=plan.id,
        version_no=1,
        parent_version_id=None,
        created_by=uuid.UUID(auth.user_id),
        note=body.note,
    )
    db.add(version)
    await db.flush()

    for ln in body.lines:
        db.add(
            BomLine(
                plan_version_id=version.id,
                line_identity_key=ln.line_identity_key,
                part_number=ln.part_number,
                description=ln.description,
                quantity=ln.quantity,
                unit=ln.unit,
                notes=ln.notes,
                tags=list(ln.tags),
            )
        )
    await db.flush()
    await write_audit(
        db,
        action="PLAN_CREATE",
        resource_type="plan",
        resource_id=plan.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={"plan_name": plan.name, "initial_version_id": str(version.id)},
    )
    await db.commit()

    plan = await _load_plan(db, str(plan.id))
    return _plan_summary(plan)


@router.post("/{plan_id}/versions", response_model=PlanVersionSummary, status_code=201)
async def create_version(
    plan_id: str,
    body: PlanVersionCreateRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> PlanVersionSummary:
    ensure_permission(auth, "build_plan", "manage")
    plan = await _load_plan(db, plan_id)

    keys = [ln.line_identity_key for ln in body.lines]
    if len(set(keys)) != len(keys):
        raise Conflict(error="duplicate_line_identity", message="line_identity_key must be unique per version")

    parent_id = None
    if body.parent_version_id:
        try:
            parent_id = uuid.UUID(body.parent_version_id)
        except ValueError:
            raise NotFound(message="parent version not found")
        if not any(v.id == parent_id for v in plan.versions):
            raise NotFound(message="parent version not found")
    else:
        parent_id = max(plan.versions, key=lambda v: v.version_no).id

    next_no = max(v.version_no for v in plan.versions) + 1
    version = PlanVersion(
        plan_id=plan.id,
        version_no=next_no,
        parent_version_id=parent_id,
        created_by=uuid.UUID(auth.user_id),
        note=body.note,
    )
    db.add(version)
    await db.flush()

    for ln in body.lines:
        db.add(
            BomLine(
                plan_version_id=version.id,
                line_identity_key=ln.line_identity_key,
                part_number=ln.part_number,
                description=ln.description,
                quantity=ln.quantity,
                unit=ln.unit,
                notes=ln.notes,
                tags=list(ln.tags),
            )
        )
    await db.flush()
    await write_audit(
        db,
        action="PLAN_VERSION_CREATE",
        resource_type="plan",
        resource_id=plan.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={"version_no": next_no, "parent_version_id": str(parent_id)},
    )
    await db.commit()

    return _version_summary(version)


@router.post(
    "/{plan_id}/versions/{version_id}/copy",
    response_model=PlanVersionSummary,
    status_code=201,
)
async def copy_version(
    plan_id: str,
    version_id: str,
    body: PlanVersionCopyRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> PlanVersionSummary:
    ensure_permission(auth, "build_plan", "manage")
    plan = await _load_plan(db, plan_id)
    source = await _load_version(db, version_id)
    if source.plan_id != plan.id:
        raise NotFound(message="plan version not found")

    next_no = max(v.version_no for v in plan.versions) + 1
    default_note = f"copy of v{source.version_no}"
    version = PlanVersion(
        plan_id=plan.id,
        version_no=next_no,
        parent_version_id=source.id,
        created_by=uuid.UUID(auth.user_id),
        note=body.note or default_note,
    )
    db.add(version)
    await db.flush()

    for l in source.lines:
        db.add(
            BomLine(
                plan_version_id=version.id,
                line_identity_key=l.line_identity_key,
                part_number=l.part_number,
                description=l.description,
                quantity=l.quantity,
                unit=l.unit,
                notes=l.notes,
                tags=list(l.tags or []),
            )
        )
    await db.flush()
    await write_audit(
        db,
        action="PLAN_VERSION_COPY",
        resource_type="plan",
        resource_id=plan.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={
            "new_version_no": next_no,
            "source_version_id": str(source.id),
            "source_version_no": source.version_no,
        },
    )
    await db.commit()
    return _version_summary(version)


@router.get("/{plan_id}/versions/{version_id}", response_model=PlanVersionDetail)
async def get_version(
    plan_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> PlanVersionDetail:
    ensure_permission(auth, "build_plan", "view")
    v = await _load_version_for_plan(db, plan_id, version_id)
    return PlanVersionDetail(
        id=str(v.id),
        plan_id=str(v.plan_id),
        version_no=v.version_no,
        parent_version_id=str(v.parent_version_id) if v.parent_version_id else None,
        note=v.note,
        created_at=v.created_at.isoformat(),
        lines=[_line_out(l) for l in v.lines],
    )


@router.get("/{plan_id}/versions/{version_id}/diff", response_model=DiffResponse)
async def compare_version(
    plan_id: str,
    version_id: str,
    against: str | None = None,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> DiffResponse:
    ensure_permission(auth, "build_plan", "view")
    target = await _load_version_for_plan(db, plan_id, version_id)
    base = None
    if against:
        base = await _load_version(db, against)
        if base.plan_id != target.plan_id:
            raise NotFound(message="plan version not found")
    elif target.parent_version_id:
        base = await _load_version(db, str(target.parent_version_id))

    base_lines = [_line_to_view(l) for l in (base.lines if base else [])]
    target_lines = [_line_to_view(l) for l in target.lines]
    entries = diff_lines(base_lines, target_lines)
    return DiffResponse(
        base_version_id=str(base.id) if base else None,
        target_version_id=str(target.id),
        entries=[
            DiffLineOut(
                line_identity_key=e.line_identity_key,
                changes=sorted(e.changes),
                base=_view_to_out(e.base) if e.base else None,
                target=_view_to_out(e.target) if e.target else None,
            )
            for e in entries
        ],
    )


def _line_to_view(l: BomLine) -> BomLineView:
    return BomLineView(
        line_identity_key=l.line_identity_key,
        part_number=l.part_number,
        description=l.description,
        quantity=l.quantity,
        unit=l.unit,
        notes=l.notes,
        tags=list(l.tags or []),
    )


def _view_to_out(v: BomLineView) -> BomLineOut:
    return BomLineOut(**{**v.to_dict()})


@router.get("/{plan_id}/versions/{version_id}/export")
async def export_bundle(
    plan_id: str,
    version_id: str,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
):
    ensure_permission(auth, "build_plan", "view")
    target = await _load_version_for_plan(db, plan_id, version_id)
    base = None
    if target.parent_version_id:
        base = await _load_version(db, str(target.parent_version_id))

    plan_payload = {
        "plan_id": str(target.plan_id),
        "version_id": str(target.id),
        "version_no": target.version_no,
        "parent_version_id": str(target.parent_version_id) if target.parent_version_id else None,
        "created_at": target.created_at.isoformat(),
        "note": target.note,
        "lines": sorted(
            [_line_to_view(l).to_dict() for l in target.lines],
            key=lambda d: d["line_identity_key"],
        ),
    }
    entries = diff_lines(
        [_line_to_view(l) for l in (base.lines if base else [])],
        [_line_to_view(l) for l in target.lines],
    )
    diff_payload = [e.to_dict() for e in entries]

    bundle = build_bundle(plan_payload=plan_payload, diff_payload=diff_payload)

    await write_audit(
        db,
        action="PLAN_EXPORT",
        resource_type="plan",
        resource_id=target.plan_id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={"version_id": str(target.id)},
    )
    await db.commit()

    filename = f"plan-{target.plan_id}-v{target.version_no}.zip"
    return Response(
        content=bundle,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{plan_id}/versions/{version_id}/rollback", response_model=PlanVersionSummary, status_code=201)
async def rollback_version(
    plan_id: str,
    version_id: str,
    body: RollbackRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> PlanVersionSummary:
    ensure_permission(auth, "build_plan", "manage")
    plan = await _load_plan(db, plan_id)
    target = await _load_version(db, version_id)
    if target.plan_id != plan.id:
        raise NotFound(message="plan version not found")

    head = max(plan.versions, key=lambda v: v.version_no)
    next_no = head.version_no + 1

    new_version = PlanVersion(
        plan_id=plan.id,
        version_no=next_no,
        parent_version_id=head.id,
        created_by=uuid.UUID(auth.user_id),
        note=f"rollback to v{target.version_no}: {body.note}",
    )
    db.add(new_version)
    await db.flush()

    for l in target.lines:
        db.add(
            BomLine(
                plan_version_id=new_version.id,
                line_identity_key=l.line_identity_key,
                part_number=l.part_number,
                description=l.description,
                quantity=l.quantity,
                unit=l.unit,
                notes=l.notes,
                tags=list(l.tags or []),
            )
        )
    await db.flush()
    await write_audit(
        db,
        action="PLAN_ROLLBACK",
        resource_type="plan",
        resource_id=plan.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={
            "new_version_no": next_no,
            "restored_from_version_id": str(target.id),
            "restored_from_version_no": target.version_no,
        },
    )
    await db.commit()
    return _version_summary(new_version)


# --- Share links ---


@router.post(
    "/{plan_id}/versions/{version_id}/share",
    response_model=ShareLinkResponse,
    status_code=201,
)
async def issue_share_link(
    plan_id: str,
    version_id: str,
    body: ShareLinkCreateRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> ShareLinkResponse:
    ensure_permission(auth, "build_plan", "manage")
    target = await _load_version_for_plan(db, plan_id, version_id)

    token = new_token()
    expires_at = compute_expiry(body.expires_in_days)
    link = PlanShareLink(
        plan_version_id=target.id,
        role=body.role,
        token_hash=hash_token(token),
        expires_at=expires_at,
        created_by=uuid.UUID(auth.user_id),
    )
    db.add(link)
    await db.flush()
    await write_audit(
        db,
        action="SHARE_LINK_ISSUE",
        resource_type="plan_share_link",
        resource_id=link.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={
            "plan_version_id": str(target.id),
            "role": body.role,
            "expires_at": expires_at.isoformat(),
        },
    )
    await db.commit()
    return ShareLinkResponse(
        id=str(link.id),
        plan_version_id=str(target.id),
        role=link.role,
        token=token,
        expires_at=expires_at.isoformat(),
        revoked=False,
    )


@router.get("/share-links/mine", response_model=list[ShareLinkSummary])
async def list_my_share_links(
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> list[ShareLinkSummary]:
    ensure_permission(auth, "build_plan", "manage")
    rows = (
        await db.execute(
            select(PlanShareLink)
            .where(PlanShareLink.created_by == uuid.UUID(auth.user_id))
            .order_by(PlanShareLink.created_at.desc())
        )
    ).scalars().all()
    return [
        ShareLinkSummary(
            id=str(r.id),
            plan_version_id=str(r.plan_version_id),
            role=r.role,
            expires_at=r.expires_at.isoformat(),
            revoked=r.revoked_at is not None,
            created_at=r.created_at.isoformat(),
            opened_at=r.opened_at.isoformat() if r.opened_at else None,
        )
        for r in rows
    ]


@router.delete("/share-links/{link_id}", response_model=ShareLinkSummary)
async def revoke_share_link(
    link_id: str,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> ShareLinkSummary:
    from app.core.errors import Forbidden
    ensure_permission(auth, "build_plan", "manage")
    try:
        lid = uuid.UUID(link_id)
    except ValueError:
        raise NotFound(message="share link not found")
    link = (
        await db.execute(select(PlanShareLink).where(PlanShareLink.id == lid))
    ).scalar_one_or_none()
    if link is None:
        raise NotFound(message="share link not found")
    # Only the user who issued the link (or admin wildcard) may revoke it.
    if (
        str(link.created_by) != auth.user_id
        and not auth.has_permission("*", "*")
    ):
        raise Forbidden(
            error="share_link_not_yours",
            message="only the issuer may revoke this share link",
        )
    link.revoked_at = datetime.now(timezone.utc)
    await write_audit(
        db,
        action="SHARE_LINK_REVOKE",
        resource_type="plan_share_link",
        resource_id=link.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={"plan_version_id": str(link.plan_version_id)},
    )
    await db.commit()
    return ShareLinkSummary(
        id=str(link.id),
        plan_version_id=str(link.plan_version_id),
        role=link.role,
        expires_at=link.expires_at.isoformat(),
        revoked=True,
        created_at=link.created_at.isoformat(),
        opened_at=link.opened_at.isoformat() if link.opened_at else None,
    )
