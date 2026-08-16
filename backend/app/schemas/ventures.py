from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models import BusinessType, UserRole


class VentureRead(BaseModel):
    id: int
    business_group_id: int
    business_type: BusinessType
    slug: str
    code: str
    name: str
    legal_name: str
    trade_name: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class VentureUserRead(BaseModel):
    id: int
    business_group_id: int
    company_id: int | None
    branch_id: int | None
    name: str
    email: EmailStr
    role: UserRole
    token_version: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class VentureUserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=255)
    role: UserRole
    company_id: int | None = None
    branch_id: int | None = None

    @model_validator(mode="after")
    def validate_scope(self) -> "VentureUserCreate":
        if self.role == UserRole.SUPER_ADMIN:
            if self.company_id is not None or self.branch_id is not None:
                raise ValueError("Super Admin cannot be assigned to a company or branch.")
        elif self.company_id is None:
            raise ValueError("Non-Super-Admin users require exactly one company assignment.")
        return self


class VentureUserUpdate(BaseModel):
    role: UserRole
    company_id: int | None = None
    branch_id: int | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_scope(self) -> "VentureUserUpdate":
        if self.role == UserRole.SUPER_ADMIN:
            if self.company_id is not None or self.branch_id is not None:
                raise ValueError("Super Admin cannot be assigned to a company or branch.")
        elif self.company_id is None:
            raise ValueError("Non-Super-Admin users require exactly one company assignment.")
        return self
