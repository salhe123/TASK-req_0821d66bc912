from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class BomLineIn(BaseModel):
    line_identity_key: str = Field(min_length=1, max_length=120)
    part_number: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    quantity: Decimal
    unit: str = Field(default="ea", max_length=30)
    notes: str = Field(default="", max_length=2000)
    tags: list[str] = Field(default_factory=list)


class BomLineOut(BaseModel):
    line_identity_key: str
    part_number: str
    description: str
    quantity: str
    unit: str
    notes: str
    tags: list[str]


class PlanCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=500)
    lines: list[BomLineIn] = Field(min_length=1)
    note: str = Field(default="initial version", max_length=500)


class PlanVersionCreateRequest(BaseModel):
    parent_version_id: str | None = None
    lines: list[BomLineIn] = Field(min_length=1)
    note: str = Field(default="", max_length=500)


class PlanVersionSummary(BaseModel):
    id: str
    plan_id: str
    version_no: int
    parent_version_id: str | None
    note: str
    created_at: str
    created_by: str | None


class PlanSummary(BaseModel):
    id: str
    name: str
    description: str
    head_version_id: str
    head_version_no: int
    versions: list[PlanVersionSummary]


class PlanListResponse(BaseModel):
    items: list[PlanSummary]


class PlanVersionDetail(BaseModel):
    id: str
    plan_id: str
    version_no: int
    parent_version_id: str | None
    note: str
    created_at: str
    lines: list[BomLineOut]


class DiffLineOut(BaseModel):
    line_identity_key: str
    changes: list[str]
    base: BomLineOut | None
    target: BomLineOut | None


class DiffResponse(BaseModel):
    base_version_id: str | None
    target_version_id: str
    entries: list[DiffLineOut]


class ShareLinkCreateRequest(BaseModel):
    role: str = Field(min_length=1, max_length=64)
    expires_in_days: int = Field(default=7, ge=1, le=7)


class ShareLinkResponse(BaseModel):
    id: str
    plan_version_id: str
    role: str
    token: str
    expires_at: str
    revoked: bool = False


class ShareLinkSummary(BaseModel):
    id: str
    plan_version_id: str
    role: str
    expires_at: str
    revoked: bool
    created_at: str
    opened_at: str | None


class RollbackRequest(BaseModel):
    note: str = Field(default="rollback", max_length=500)
