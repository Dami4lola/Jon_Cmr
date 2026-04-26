"""
API dependencies - authentication, database sessions, role checks
"""
from typing import Annotated, Callable
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload

from ..database import get_session
from ..models import User, Worker
from ..services.auth import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    session: Annotated[Session, Depends(get_session)],
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    """Get the current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    # sub is stored as string per JWT spec, convert to int
    sub = payload.get("sub")
    if sub is None:
        raise credentials_exception
    user_id = int(sub)

    # Check token type
    if payload.get("type") != "access":
        raise credentials_exception

    # Get user with roles loaded
    statement = (
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.roles))
    )
    user = session.exec(statement).first()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return user


def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Ensure user is active"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def get_current_worker(
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Worker:
    """Get the worker profile for the current user"""
    statement = select(Worker).where(Worker.user_id == current_user.id)
    worker = session.exec(statement).first()

    if worker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Worker profile not found. Contact administrator.",
        )

    return worker


def require_role(*allowed_roles: str) -> Callable:
    """
    Dependency factory for role-based access control.

    Usage:
        @router.get("/admin")
        def admin_endpoint(user: User = Depends(require_role("admin"))):
            ...
    """
    def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if not any(user.has_role(role) for role in allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires one of: {', '.join(allowed_roles)}",
            )
        return user
    return checker


def require_manager(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require manager or admin role"""
    if not current_user.is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager access required",
        )
    return current_user


def require_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require admin role"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


# Type aliases for cleaner route signatures
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentWorker = Annotated[Worker, Depends(get_current_worker)]
ManagerUser = Annotated[User, Depends(require_manager)]
AdminUser = Annotated[User, Depends(require_admin)]
DBSession = Annotated[Session, Depends(get_session)]
