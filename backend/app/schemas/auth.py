from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import BusinessType, UserRole


class UserRead(BaseModel):
    id: int
    business_group_id: int
    company_id: int | None
    company_name: str | None = None
    company_slug: str | None = None
    company_business_type: BusinessType | None = None
    name: str
    email: str
    role: UserRole
    branch_id: int | None
    permissions: list[str] = Field(default_factory=list)
    is_active: bool
    mfa_enabled: bool = False

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=255)
    totp_code: str | None = Field(default=None, min_length=6, max_length=12)
    recovery_code: str | None = Field(default=None, min_length=8, max_length=64)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class StepUpRequest(BaseModel):
    password: str = Field(min_length=1, max_length=255)
    totp_code: str | None = Field(default=None, min_length=6, max_length=12)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserRead


class MessageResponse(BaseModel):
    message: str


class BranchScopeResponse(BaseModel):
    all_branches: bool
    branch_ids: list[int]


class MfaEnrollResponse(BaseModel):
    secret: str
    provisioning_uri: str
    recovery_codes: list[str]


class MfaConfirmRequest(BaseModel):
    totp_code: str = Field(min_length=6, max_length=12)


class MfaDisableRequest(BaseModel):
    password: str = Field(min_length=1, max_length=255)
    totp_code: str = Field(min_length=6, max_length=12)
