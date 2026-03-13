"""
Purchase list item schemas
"""
from pydantic import BaseModel, Field
from datetime import datetime


class PurchaseItemCreate(BaseModel):
    """Create purchase list item"""
    name: str = Field(..., min_length=1, max_length=200)
    quantity: str | None = Field(default=None, max_length=50)
    priority: str = Field(default="2_medium")  # 1_high, 2_medium, 3_low
    notes: str | None = None


class PurchaseItemResponse(BaseModel):
    """Purchase list item response"""
    id: int
    name: str
    quantity: str | None
    priority: str
    status: str
    notes: str | None
    added_by_id: int | None
    added_by_name: str | None = None
    added_at: datetime
    purchased_by_id: int | None
    purchased_by_name: str | None = None
    purchased_at: datetime | None

    class Config:
        from_attributes = True
