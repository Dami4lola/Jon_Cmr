"""
Role model for role-based access control
"""
from sqlmodel import SQLModel, Field, Relationship
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from .user import User


class UserRoleLink(SQLModel, table=True):
    """Many-to-many link between users and roles"""
    __tablename__ = "user_role_link"

    user_id: int = Field(foreign_key="user.id", primary_key=True)
    role_id: int = Field(foreign_key="role.id", primary_key=True)


class Role(SQLModel, table=True):
    """Role model for RBAC"""
    __tablename__ = "role"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)  # "worker", "manager", "admin"
    description: str | None = None

    # Relationships
    users: List["User"] = Relationship(
        back_populates="roles",
        link_model=UserRoleLink
    )
