from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TemplateItem(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=200)
    weight: float = Field(ge=0)
    required: bool = True
    missing_strategy: str = Field(default="ZERO_FILL")
    min_value: float | None = None
    max_value: float | None = None
    outlier_z: float | None = None

    @field_validator("missing_strategy")
    @classmethod
    def valid_missing_strategy(cls, v: str) -> str:
        if v not in ("ZERO_FILL", "EXCLUDE_FROM_DENOMINATOR"):
            raise ValueError("missing_strategy must be ZERO_FILL or EXCLUDE_FROM_DENOMINATOR")
        return v


class TemplateCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=500)
    items: list[TemplateItem] = Field(min_length=1)


class TemplateSummary(BaseModel):
    id: str
    name: str
    description: str
    latest_version_id: str
    latest_version_no: int
    items: list[dict[str, Any]]


class CycleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    starts_on: date
    ends_on: date
    deadline_at: datetime
    timezone: str = Field(default="UTC", max_length=64)
    makeup_enabled: bool = False
    makeup_business_days: int = Field(default=5, ge=0, le=5)
    holidays: list[str] = Field(default_factory=list)
    template_version_id: str
    rule_set_version_id: str | None = None


class CycleSummary(BaseModel):
    id: str
    name: str
    starts_on: str
    ends_on: str
    deadline_at: str
    effective_deadline_at: str
    timezone: str
    makeup_enabled: bool
    makeup_business_days: int
    holidays: list[str]
    template_version_id: str
    rule_set_version_id: str


class CycleListResponse(BaseModel):
    items: list[CycleSummary]


class AssignmentAddRequest(BaseModel):
    evaluator_user_id: str
    reviewer_user_id: str | None = None


class AssignmentSummary(BaseModel):
    id: str
    cycle_id: str
    evaluator_user_id: str
    reviewer_user_id: str | None
    state: str
    submitted_at: str | None
    late_flag: bool
    returned_reason: str | None
    archived_at: str | None


class AssignmentListResponse(BaseModel):
    items: list[AssignmentSummary]


class AssignmentFormResponse(BaseModel):
    assignment: AssignmentSummary
    cycle_name: str
    deadline_at: str
    template_version_id: str
    items: list[dict[str, Any]]
    draft_values: dict[str, Any]


class SaveDraftRequest(BaseModel):
    values: dict[str, Any]


class SubmitRequest(BaseModel):
    values: dict[str, Any]


class ReturnRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class DigestItemOut(BaseModel):
    assignment_id: str
    cycle_id: str
    cycle_name: str
    state: str
    deadline_at: str
    effective_deadline_at: str
    late_eligible: bool


class DigestResponse(BaseModel):
    show: bool
    as_of_local: str
    items: list[DigestItemOut]
