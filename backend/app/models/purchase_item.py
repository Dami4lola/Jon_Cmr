"""
Purchase List Item model
"""
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from enum import Enum

if TYPE_CHECKING:
    from .user import User


class PurchasePriority(str, Enum):
    HIGH = "1_high"
    MEDIUM = "2_medium"
    LOW = "3_low"


class PurchaseStatus(str, Enum):
    NEEDED = "needed"
    PURCHASED = "purchased"


class PurchaseListItem(SQLModel, table=True):
    """Purchase/shopping list item"""
    __tablename__ = "purchase_list_item"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=200)
    quantity: str | None = Field(default=None, max_length=50)
    priority: str = Field(default=PurchasePriority.MEDIUM.value, max_length=10)
    status: str = Field(default=PurchaseStatus.NEEDED.value, max_length=10, index=True)
    notes: str | None = Field(default=None)

    # Who added it
    added_by_id: int | None = Field(default=None, foreign_key="user.id")
    added_at: datetime = Field(default_factory=datetime.utcnow)

    # Who purchased it
    purchased_by_id: int | None = Field(default=None, foreign_key="user.id")
    purchased_at: datetime | None = Field(default=None)
