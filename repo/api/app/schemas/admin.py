from pydantic import BaseModel, Field


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    display_name: str = Field(default="", max_length=200)
    password: str = Field(min_length=12, max_length=256)
    roles: list[str] = Field(default_factory=list)


class UserSummary(BaseModel):
    id: str
    username: str
    display_name: str
    is_active: bool
    locked: bool
    roles: list[str]
    last_login_at: str | None


class UserListResponse(BaseModel):
    items: list[UserSummary]


class UserUnlockResponse(BaseModel):
    id: str
    unlocked: bool
