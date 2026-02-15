"""
Authentication API endpoints
"""
from fastapi import APIRouter, HTTPException, status, Depends, Body
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload

from ..database import get_session
from ..models import User, Worker, Role
from ..schemas.auth import Token, LoginRequest, RegisterRequest, UserResponse, ForgotPasswordRequest, ResetPasswordRequest, ChangePasswordRequest, MessageResponse
from ..services.auth import verify_password, get_password_hash, create_access_token, create_refresh_token, decode_token, create_password_reset_token, verify_password_reset_token
from ..services.email import send_password_reset_email
from ..seed import get_role_by_name
from .deps import DBSession, CurrentUser

router = APIRouter()


@router.post("/login", response_model=Token)
def login(
    session: DBSession,
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """
    OAuth2 compatible login endpoint.
    Returns JWT access and refresh tokens.
    """
    # Find user by username
    statement = (
        select(User)
        .where(User.username == form_data.username)
        .options(selectinload(User.roles))
    )
    user = session.exec(statement).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    # Create tokens (sub must be a string per JWT spec)
    access_token = create_access_token(data={"sub": str(user.id), "username": user.username})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
    )


class RegisterResponse(BaseModel):
    """Registration response with token and user"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


@router.post("/register", response_model=RegisterResponse)
def register(
    session: DBSession,
    data: RegisterRequest,
):
    """
    Register a new user account.
    Creates user and worker profile with default 'worker' role.
    Returns access token for immediate login.
    """
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

    # Get worker role
    worker_role = get_role_by_name(session, "worker")
    if not worker_role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Worker role not found. Database may not be seeded.",
        )

    # Create user
    user = User(
        username=data.username,
        email=data.email,
        hashed_password=get_password_hash(data.password),
        is_active=True,
    )
    user.roles.append(worker_role)
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

    # Create access token for immediate login (sub must be a string per JWT spec)
    access_token = create_access_token(data={"sub": str(user.id), "username": user.username})

    return RegisterResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            roles=[r.name for r in user.roles],
            created_at=user.created_at,
            worker_id=worker.id,
            worker_name=worker.name,
        ),
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    session: DBSession,
    current_user: CurrentUser,
):
    """Get current authenticated user info"""
    # Get worker profile if exists
    statement = select(Worker).where(Worker.user_id == current_user.id)
    worker = session.exec(statement).first()

    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        is_active=current_user.is_active,
        roles=[r.name for r in current_user.roles],
        created_at=current_user.created_at,
        worker_id=worker.id if worker else None,
        worker_name=worker.name if worker else None,
    )


@router.post("/refresh", response_model=Token)
def refresh_token(
    session: DBSession,
    refresh_token: str = Body(..., embed=True),
):
    """Refresh access token using refresh token"""
    payload = decode_token(refresh_token)

    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user_id = int(payload.get("sub"))
    statement = select(User).where(User.id == user_id)
    user = session.exec(statement).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Create new tokens (sub must be a string per JWT spec)
    access_token = create_access_token(data={"sub": str(user.id), "username": user.username})
    new_refresh_token = create_refresh_token(data={"sub": str(user.id)})

    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
    )


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    session: DBSession,
    data: ForgotPasswordRequest,
):
    """
    Request a password reset email.
    Always returns success to prevent email enumeration.
    """
    statement = select(User).where(User.email == data.email)
    user = session.exec(statement).first()

    if user and user.is_active:
        token = create_password_reset_token(user.id)
        try:
            send_password_reset_email(user.email, token)
        except Exception:
            # Log but don't expose email sending failures to the user
            pass

    return MessageResponse(message="If an account exists with that email, you will receive a password reset link.")


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    session: DBSession,
    data: ResetPasswordRequest,
):
    """Reset password using a valid reset token"""
    user_id = verify_password_reset_token(data.token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    statement = select(User).where(User.id == user_id)
    user = session.exec(statement).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user.hashed_password = get_password_hash(data.new_password)
    session.add(user)
    session.commit()

    return MessageResponse(message="Your password has been reset successfully.")


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    session: DBSession,
    current_user: CurrentUser,
    data: ChangePasswordRequest,
):
    """Change password for the currently authenticated user"""
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.hashed_password = get_password_hash(data.new_password)
    session.add(current_user)
    session.commit()

    return MessageResponse(message="Password changed successfully.")
