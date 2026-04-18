from __future__ import annotations

from pydantic import BaseModel, Field


class RuleSetCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=500)
    rules: dict = Field(default_factory=dict)


class RuleSetVersionCreateRequest(BaseModel):
    rules: dict = Field(default_factory=dict)


class RuleSetVersionSummary(BaseModel):
    id: str
    rule_set_id: str
    version_no: int
    rules: dict
    published_at: str


class RuleSetSummary(BaseModel):
    id: str
    name: str
    description: str
    latest_version_id: str
    latest_version_no: int
    rules: dict
    versions: list[RuleSetVersionSummary]


class RuleSetListResponse(BaseModel):
    items: list[RuleSetSummary]
