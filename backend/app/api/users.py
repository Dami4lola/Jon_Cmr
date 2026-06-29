"""
User Management API endpoints (Admin only)
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import select
from sqlalchemy.orm import selectinload
from sqlalchemy import delete as sa_delete
from typing import List

from ..database import get_session
from ..models import User, Worker, Role, Timesheet, TimeOffRequest, JobWorkerLink, JobWorkerSchedule
from ..schemas.auth import UserResponse
from ..services.auth import get_password_hash
from ..seed import get_role_by_name
from .deps import DBSession, AdminUser

router = APIRouter()


class AdminCreateUserRequest(BaseModel):
    """Admin request to create a user with specific roles"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    name: str = Field(..., min_length=1, max_length=100)
    hourly_rate: float = Field(default=0.0, ge=0)
    charges_hst: bool = False
    is_employee: bool = False
    roles: List[str] = Field(default=["worker"])  # List of role names


class UpdateUserRolesRequest(BaseModel):
    """Request to update a user's roles"""
    roles: List[str] = Field(..., min_items=1)


class AdminResetPasswordRequest(BaseModel):
    """Admin request to reset a user's password"""
    new_password: str = Field(..., min_length=6)


class UserWithWorkerResponse(BaseModel):
    """Extended user response with worker details"""
    id: int
    username: str
    email: str
    is_active: bool
    roles: List[str]
    created_at: str
    worker_id: int | None = None
    worker_name: str | None = None
    hourly_rate: float | None = None
    charges_hst: bool | None = None
    is_employee: bool | None = None

    class Config:
        from_attributes = True


@router.get("/", response_model=List[UserWithWorkerResponse])
def list_users(
    session: DBSession,
    admin: AdminUser,
):
    """List all users (admin only)"""
    statement = (
        select(User)
        .options(selectinload(User.roles))
        .order_by(User.created_at.desc())
    )
    users = session.exec(statement).all()

    result = []
    for user in users:
        # Get worker profile if exists
        worker_statement = select(Worker).where(Worker.user_id == user.id)
        worker = session.exec(worker_statement).first()

        result.append(UserWithWorkerResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            roles=[r.name for r in user.roles],
            created_at=user.created_at.isoformat(),
            worker_id=worker.id if worker else None,
            worker_name=worker.name if worker else None,
            hourly_rate=float(worker.hourly_rate) if worker else None,
            charges_hst=worker.charges_hst if worker else None,
            is_employee=worker.is_employee if worker else None,
        ))

    return result


@router.post("/", response_model=UserWithWorkerResponse)
def create_user(
    session: DBSession,
    admin: AdminUser,
    data: AdminCreateUserRequest,
):
    """Create a new user with specified roles (admin only)"""
    # Check if username exists
    statement = select(User).where(User.username == data.username)
    if session.exec(statement).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Check if email exists
    statement = select(User).where(User.email == data.email)
    if session.exec(statement).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Validate and get all roles
    roles = []
    for role_name in data.roles:
        role = get_role_by_name(session, role_name)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role '{role_name}' not found. Valid roles: worker, manager, admin",
            )
        roles.append(role)

    # Create user
    user = User(
        username=data.username,
        email=data.email,
        hashed_password=get_password_hash(data.password),
        is_active=True,
    )
    for role in roles:
        user.roles.append(role)
    session.add(user)
    session.commit()
    session.refresh(user)

    # Create worker profile
    worker = Worker(
        user_id=user.id,
        name=data.name,
        hourly_rate=data.hourly_rate,
        charges_hst=data.charges_hst,
        is_employee=data.is_employee,
    )
    session.add(worker)
    session.commit()
    session.refresh(worker)

    return UserWithWorkerResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        roles=[r.name for r in user.roles],
        created_at=user.created_at.isoformat(),
        worker_id=worker.id,
        worker_name=worker.name,
        hourly_rate=float(worker.hourly_rate),
        charges_hst=worker.charges_hst,
        is_employee=worker.is_employee,
    )


@router.get("/{user_id}", response_model=UserWithWorkerResponse)
def get_user(
    session: DBSession,
    admin: AdminUser,
    user_id: int,
):
    """Get a specific user (admin only)"""
    statement = (
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.roles))
    )
    user = session.exec(statement).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Get worker profile
    worker_statement = select(Worker).where(Worker.user_id == user.id)
    worker = session.exec(worker_statement).first()

    return UserWithWorkerResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        roles=[r.name for r in user.roles],
        created_at=user.created_at.isoformat(),
        worker_id=worker.id if worker else None,
        worker_name=worker.name if worker else None,
        hourly_rate=float(worker.hourly_rate) if worker else None,
        charges_hst=worker.charges_hst if worker else None,
        is_employee=worker.is_employee if worker else None,
    )


@router.put("/{user_id}/roles", response_model=UserWithWorkerResponse)
def update_user_roles(
    session: DBSession,
    admin: AdminUser,
    user_id: int,
    data: UpdateUserRolesRequest,
):
    """Update a user's roles (admin only)"""
    statement = (
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.roles))
    )
    user = session.exec(statement).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent admin from removing their own admin role
    if user.id == admin.id and "admin" not in data.roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove your own admin role",
        )

    # Validate and get all roles
    new_roles = []
    for role_name in data.roles:
        role = get_role_by_name(session, role_name)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role '{role_name}' not found. Valid roles: worker, manager, admin",
            )
        new_roles.append(role)

    # Update roles
    user.roles.clear()
    for role in new_roles:
        user.roles.append(role)
    session.commit()
    session.refresh(user)

    # Get worker profile
    worker_statement = select(Worker).where(Worker.user_id == user.id)
    worker = session.exec(worker_statement).first()

    return UserWithWorkerResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        roles=[r.name for r in user.roles],
        created_at=user.created_at.isoformat(),
        worker_id=worker.id if worker else None,
        worker_name=worker.name if worker else None,
        hourly_rate=float(worker.hourly_rate) if worker else None,
        charges_hst=worker.charges_hst if worker else None,
        is_employee=worker.is_employee if worker else None,
    )


@router.put("/{user_id}/toggle-active", response_model=UserWithWorkerResponse)
def toggle_user_active(
    session: DBSession,
    admin: AdminUser,
    user_id: int,
):
    """Toggle a user's active status (admin only)"""
    statement = (
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.roles))
    )
    user = session.exec(statement).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent admin from deactivating themselves
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )

    user.is_active = not user.is_active
    session.commit()
    session.refresh(user)

    # Get worker profile
    worker_statement = select(Worker).where(Worker.user_id == user.id)
    worker = session.exec(worker_statement).first()

    return UserWithWorkerResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        roles=[r.name for r in user.roles],
        created_at=user.created_at.isoformat(),
        worker_id=worker.id if worker else None,
        worker_name=worker.name if worker else None,
        hourly_rate=float(worker.hourly_rate) if worker else None,
        charges_hst=worker.charges_hst if worker else None,
        is_employee=worker.is_employee if worker else None,
    )


@router.put("/{user_id}/reset-password")
def admin_reset_password(
    session: DBSession,
    admin: AdminUser,
    user_id: int,
    data: AdminResetPasswordRequest,
):
    """Reset a user's password (admin only)"""
    statement = select(User).where(User.id == user_id)
    user = session.exec(statement).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.hashed_password = get_password_hash(data.new_password)
    session.add(user)
    session.commit()

    return {"message": f"Password for '{user.username}' has been reset successfully."}


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    session: DBSession,
    admin: AdminUser,
):
    """
    Delete a user (admin only). All timesheets are orphaned (worker_id set to NULL,
    name preserved via worker_name_snapshot) so payroll history is retained.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    worker = session.exec(select(Worker).where(Worker.user_id == user_id)).first()
    if worker:
        # Orphan all timesheets (paid and unpaid), preserving the employee's name for historical records
        timesheets = session.exec(
            select(Timesheet).where(Timesheet.worker_id == worker.id)
        ).all()
        for ts in timesheets:
            ts.worker_name_snapshot = worker.name
            ts.worker_id = None
            session.add(ts)

        session.flush()

        # Clean up operational records with no financial/historical value
        session.exec(sa_delete(TimeOffRequest).where(TimeOffRequest.worker_id == worker.id))
        session.exec(sa_delete(JobWorkerLink).where(JobWorkerLink.worker_id == worker.id))
        session.exec(sa_delete(JobWorkerSchedule).where(JobWorkerSchedule.worker_id == worker.id))

        session.flush()

        session.delete(worker)

    session.delete(user)
    session.commit()
