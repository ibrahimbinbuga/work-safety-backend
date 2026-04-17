"""Auth-related Pydantic schemas split from legacy auth.py."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: int
    email: str
    role: str
    company_code: str


class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None
    role: Optional[str] = None
    company_code: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str
    company_code: str


class UserCreate(BaseModel):
    email: str
    password: str
    company_code: str
    role: str = "user"


class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CompanyResponse(BaseModel):
    id: int
    code: str
    name: str
    created_at: datetime

    class Config:
        from_attributes = True

