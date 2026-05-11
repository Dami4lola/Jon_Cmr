"""
Timesheet inventory item model — company stock used on a job
"""
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .timesheet import Timesheet


class TimesheetInventoryItem(SQLModel, table=True):
    """Records company inventory/stock consumed on a timesheet day"""
    __tablename__ = "timesheet_inventory_item"

    id: int | None = Field(default=None, primary_key=True)
    timesheet_id: int = Field(foreign_key="timesheet.id", index=True)

    description: str = Field(max_length=500)
    quantity: str = Field(default="", max_length=100)

    created_at: datetime = Field(default_factory=datetime.utcnow)

    timesheet: Optional["Timesheet"] = Relationship(back_populates="inventory_items")
