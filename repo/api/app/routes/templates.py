from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_session
from app.core.errors import Conflict, NotFound
from app.middleware.auth import get_auth
from app.models.cycle import Template, TemplateVersion
from app.schemas.cycles import TemplateCreateRequest, TemplateSummary
from app.services.audit import write_audit
from app.services.rbac import AuthContext, ensure_permission

router = APIRouter(prefix="/templates", tags=["templates"])


def _summary(t: Template) -> TemplateSummary:
    latest = max(t.versions, key=lambda v: v.version_no)
    return TemplateSummary(
        id=str(t.id),
        name=t.name,
        description=t.description,
        latest_version_id=str(latest.id),
        latest_version_no=latest.version_no,
        items=latest.items,
    )


@router.get("", response_model=list[TemplateSummary])
async def list_templates(
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> list[TemplateSummary]:
    ensure_permission(auth, "template", "manage")
    templates = (
        await db.execute(
            select(Template).options(selectinload(Template.versions)).order_by(Template.name)
        )
    ).scalars().all()
    return [_summary(t) for t in templates]


@router.post("", response_model=TemplateSummary, status_code=201)
async def create_template(
    body: TemplateCreateRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> TemplateSummary:
    ensure_permission(auth, "template", "manage")
    keys = [item.key for item in body.items]
    if len(set(keys)) != len(keys):
        raise Conflict(error="duplicate_item_keys", message="template items must have unique keys")

    exists = (
        await db.execute(select(Template).where(Template.name == body.name))
    ).scalar_one_or_none()
    if exists is not None:
        raise Conflict(error="template_name_taken", message="template name already exists")

    template = Template(name=body.name, description=body.description)
    db.add(template)
    await db.flush()

    version = TemplateVersion(
        template_id=template.id,
        version_no=1,
        items=[item.model_dump() for item in body.items],
    )
    db.add(version)
    await db.flush()

    await write_audit(
        db,
        action="TEMPLATE_CREATE",
        resource_type="template",
        resource_id=template.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={"name": template.name, "version_no": 1},
    )
    await db.commit()

    template = (
        await db.execute(
            select(Template).where(Template.id == template.id).options(selectinload(Template.versions))
        )
    ).scalar_one()
    return _summary(template)


@router.post("/{template_id}/versions", response_model=TemplateSummary, status_code=201)
async def publish_version(
    template_id: str,
    body: TemplateCreateRequest,
    db: AsyncSession = Depends(get_session),
    auth: AuthContext = Depends(get_auth),
) -> TemplateSummary:
    ensure_permission(auth, "template", "manage")
    try:
        tid = uuid.UUID(template_id)
    except ValueError:
        raise NotFound(message="template not found")
    template = (
        await db.execute(
            select(Template).where(Template.id == tid).options(selectinload(Template.versions))
        )
    ).scalar_one_or_none()
    if template is None:
        raise NotFound(message="template not found")

    keys = [item.key for item in body.items]
    if len(set(keys)) != len(keys):
        raise Conflict(error="duplicate_item_keys", message="template items must have unique keys")

    next_no = max((v.version_no for v in template.versions), default=0) + 1
    version = TemplateVersion(
        template_id=template.id,
        version_no=next_no,
        items=[item.model_dump() for item in body.items],
    )
    db.add(version)
    await db.flush()
    await write_audit(
        db,
        action="TEMPLATE_VERSION_PUBLISH",
        resource_type="template",
        resource_id=template.id,
        actor_user_id=uuid.UUID(auth.user_id),
        payload={"version_no": next_no},
    )
    await db.commit()

    template = (
        await db.execute(
            select(Template).where(Template.id == template.id).options(selectinload(Template.versions))
        )
    ).scalar_one()
    return _summary(template)
