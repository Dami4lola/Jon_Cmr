"""
User model for authentication
"""
from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from .role import Role
    from .worker import Worker

from .role import UserRoleLink


class User(SQLModel, table=True):
    """User model for authentication"""
    __tablename__ = "user"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True, max_length=50)
    email: str = Field(unique=True, index=True, max_length=255)
    hashed_password: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    roles: List["Role"] = Relationship(
        back_populates="users",
        link_model=UserRoleLink
    )
    worker: Optional["Worker"] = Relationship(back_populates="user")

    def has_role(self, role_name: str) -> bool:
        """Check if user has a specific role"""
        return any(r.name == role_name for r in self.roles)

    @property
    def is_manager(self) -> bool:
        """Check if user is a manager or admin"""
        return self.has_role("manager") or self.has_role("admin")

    @property
    def is_admin(self) -> bool:
        """Check if user is an admin"""
        return self.has_role("admin")

    @property
    def role_names(self) -> List[str]:
        """Get list of role names"""
        return [r.name for r in self.roles]
