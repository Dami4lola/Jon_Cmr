"""
Worker schemas
"""
from pydantic import BaseModel, Field
from decimal import Decimal


class WorkerCreate(BaseModel):
    """Create worker (admin only)"""
    user_id: int
    name: str = Field(..., max_length=100)
    hourly_rate: Decimal = Field(default=Decimal("0.00"), ge=0, le=999.99)
    charges_hst: bool = False
    is_employee: bool = False


class WorkerUpdate(BaseModel):
    """Update worker (admin only)"""
    name: str | None = Field(default=None, max_length=100)
    hourly_rate: Decimal | None = Field(default=None, ge=0, le=999.99)
    charges_hst: bool | None = None
    is_employee: bool | None = None


class WorkerResponse(BaseModel):
    """Worker response"""
    id: int
    user_id: int
    name: str
    hourly_rate: Decimal
    charges_hst: bool
    is_employee: bool

    class Config:
        from_attributes = True


class WorkerBrief(BaseModel):
    """Brief worker info for nested responses"""
    id: int
    name: str

    class Config:
        from_attributes = True
