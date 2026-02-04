"""
Receipt model
"""
from sqlmodel import SQLModel, Field, Relationship
from decimal import Decimal
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .timesheet import Timesheet


class Receipt(SQLModel, table=True):
    """Receipt image model"""
    __tablename__ = "receipt"

    id: int | None = Field(default=None, primary_key=True)
    timesheet_id: int = Field(foreign_key="timesheet.id", index=True)

    # File info
    image_path: str  # Path to uploaded image
    description: str | None = Field(default=None, max_length=200)
    amount: Decimal | None = Field(default=None, max_digits=8, decimal_places=2)

    # Timestamps
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    timesheet: Optional["Timesheet"] = Relationship(back_populates="receipts")
