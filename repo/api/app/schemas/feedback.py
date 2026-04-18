from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    experiment_id: str
    subject_key: str = Field(min_length=1, max_length=200)
    target_id: str = Field(min_length=1, max_length=200)
    kind: str = Field(pattern="^(LIKE|NOT_INTERESTED|BLOCK)$")
    arm: str | None = Field(default=None, pattern="^(A|B)$")
    model_version_id: str | None = None


class FeedbackResponse(BaseModel):
    event_id: str
    experiment_id: str
    arm: str
    subject_key: str
    target_id: str
    kind: str
    signal_updated: bool


class SignalOut(BaseModel):
    experiment_id: str
    arm: str
    target_id: str
    like_count: int
    not_interested_count: int
    last_updated_at: str


class SignalsResponse(BaseModel):
    items: list[SignalOut]


class BlockOut(BaseModel):
    target_id: str
    created_at: str


class BlocksResponse(BaseModel):
    subject_key: str
    items: list[BlockOut]
