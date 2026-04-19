from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(BaseModel):
    user_id: str
    username: str
    roles: list[str]
    csrf_token: str
    session_token: str
    expires_at: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class MeResponse(BaseModel):
    user_id: str
    username: str
    display_name: str
    roles: list[str]
    permissions: list[dict[str, str]]
    field_view_allowlist: list[str]
    timezone: str = "UTC"
    # Returned so the SPA can restore its CSRF token after a hard page reload
    # (Pinia state is in-memory only; the session cookie survives the reload,
    # but the CSRF token needs to be re-fetched so mutating requests keep
    # passing the server-side CSRF check).
    csrf_token: str = ""


class UpdateTimezoneRequest(BaseModel):
    timezone: str = Field(min_length=1, max_length=64)
