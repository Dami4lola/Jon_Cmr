"""
Authentication schemas
"""
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import List


class Token(BaseModel):
    """JWT token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Data extracted from JWT token"""
    user_id: int | None = None
    username: str | None = None


class LoginRequest(BaseModel):
    """Login request body"""
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    """Registration request body"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    name: str = Field(..., min_length=1, max_length=100)
    hourly_rate: float = Field(default=0.0, ge=0)
    charges_hst: bool = False
    is_employee: bool = False


class UserResponse(BaseModel):
    """User response (safe to expose)"""
    id: int
    username: str
    email: str
    is_active: bool
    roles: List[str]
    created_at: datetime

    # Worker info if exists
    worker_id: int | None = None
    worker_name: str | None = None

    class Config:
        from_attributes = True
