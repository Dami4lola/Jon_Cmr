"""
Client model
"""
from sqlmodel import SQLModel, Field, Relationship
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from .job import Job


class Client(SQLModel, table=True):
    """Client/customer model"""
    __tablename__ = "client"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=100, index=True)
    phone_number: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    address: str  # Required - job location

    # Relationships
    jobs: List["Job"] = Relationship(back_populates="client")
