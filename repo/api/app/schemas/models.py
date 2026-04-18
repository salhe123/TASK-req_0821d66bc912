from __future__ import annotations

from pydantic import BaseModel, Field


class FeatureDescriptor(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    dtype: str = Field(min_length=1, max_length=60)
    transform: str = Field(default="identity", max_length=120)
    source_query_hash: str = Field(min_length=1, max_length=64)


class ModelCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=500)


class ModelVersionCreateRequest(BaseModel):
    feature_schema: list[FeatureDescriptor] = Field(min_length=1)
    artifact_uri: str = Field(default="", max_length=500)
    artifact_params: dict = Field(default_factory=dict)


class ModelVersionSummary(BaseModel):
    id: str
    model_id: str
    version_no: int
    status: str
    feature_schema_hash: str
    artifact_uri: str
    created_at: str
    approved_at: str | None


class ModelSummary(BaseModel):
    id: str
    name: str
    description: str
    live_schema_hash: str | None
    versions: list[ModelVersionSummary]


class ModelListResponse(BaseModel):
    items: list[ModelSummary]


class ModelRunStartRequest(BaseModel):
    kind: str = Field(pattern="^(TRAINING|EVALUATION)$")
    dataset_ref: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=2000)


class ModelRunCompleteRequest(BaseModel):
    status: str = Field(pattern="^(SUCCEEDED|FAILED)$")
    metrics: dict = Field(default_factory=dict)
    notes: str = Field(default="", max_length=2000)


class ModelRunSummary(BaseModel):
    id: str
    model_version_id: str
    kind: str
    status: str
    dataset_ref: str
    metrics: dict
    notes: str
    started_by: str | None
    started_at: str
    completed_at: str | None


class ModelRunListResponse(BaseModel):
    items: list[ModelRunSummary]


class ExperimentCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=500)
    model_a_version_id: str
    model_b_version_id: str | None = None
    weight_a: int = Field(default=90, ge=0, le=100)


class ExperimentSummary(BaseModel):
    id: str
    name: str
    description: str
    ingest_enabled: bool
    apply_enabled: bool
    model_a_id: str
    model_b_id: str | None
    weight_a: int
    weight_b: int


class ExperimentListResponse(BaseModel):
    items: list[ExperimentSummary]


class ExperimentToggleRequest(BaseModel):
    ingest_enabled: bool | None = None
    apply_enabled: bool | None = None


class RoutingUpdateRequest(BaseModel):
    weight_a: int = Field(ge=0, le=100)


class RollbackRequest(BaseModel):
    trigger: str = Field(default="manual")
    reason: str = Field(default="", max_length=500)


class PredictRequest(BaseModel):
    experiment_id: str
    subject_key: str = Field(min_length=1, max_length=200)
    features: dict = Field(default_factory=dict)


class PredictResponse(BaseModel):
    subject_key: str
    experiment_id: str
    arm: str
    model_version_id: str
    score: float
    latency_ms: float
