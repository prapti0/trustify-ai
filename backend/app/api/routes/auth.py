import re
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas import (
    AuthResponse,
    LoginBody,
    PasswordBody,
    ProfileBody,
    RegisterBody,
    SessionPublic,
    UserPublic,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.core.passwords import hash_password, verify_password
from app.core.tokens import create_access_token
from app.domain.enums import UserRole
from app.models import UploadedFile, User, UserSession
from app.services.integrity import sha256_hex
from app.services.storage import LocalObjectStorage
from app.services.uploads import session_expiry
from pathlib import Path

router = APIRouter(prefix="/auth")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if not _EMAIL.fullmatch(email):
        raise HTTPException(status_code=400, detail={"error": "invalid_email", "message": "Enter a valid email address."})
    return email


def require_auth_config() -> str:
    secret = get_settings().signing_key
    if not secret:
        raise HTTPException(
            status_code=503,
            detail={"error": "auth_unconfigured", "message": "Authentication is not configured."},
        )
    return secret


def issue_session(db: Session, request: Request, user: User) -> AuthResponse:
    secret = require_auth_config()
    raw = secrets.token_urlsafe(32)
    record = UserSession(
        user_id=user.id,
        refresh_token_hash=sha256_hex(raw.encode()),
        expires_at=session_expiry(),
        ip_address=(request.client.host if request.client else None),
        user_agent=(request.headers.get("user-agent") or "")[:512] or None,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return AuthResponse(
        access_token=create_access_token(user.id, secret),
        session_id=record.id,
        user=UserPublic(id=user.id, email=user.email, full_name=user.full_name, role=user.role.value),
    )


@router.post("/register", response_model=AuthResponse)
def register(body: RegisterBody, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    require_auth_config()
    if not body.accepted_terms:
        raise HTTPException(
            status_code=400,
            detail={"error": "terms_required", "message": "Accept the Terms of Service and Privacy Policy to continue."},
        )
    email = normalize_email(body.email)
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail={"error": "email_in_use", "message": "An account with that email already exists."})
    try:
        password_hash = hash_password(body.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "weak_password", "message": str(exc)}) from exc
    user = User(email=email, password_hash=password_hash, full_name=body.full_name.strip(), role=UserRole.USER)
    db.add(user)
    db.commit()
    db.refresh(user)
    return issue_session(db, request, user)


@router.post("/login", response_model=AuthResponse)
def login(body: LoginBody, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    require_auth_config()
    email = normalize_email(body.email) if "@" in body.email else body.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail={"error": "invalid_credentials", "message": "Email or password is incorrect."})
    return issue_session(db, request, user)


@router.post("/logout")
def logout(session_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    record = db.get(UserSession, session_id)
    if record and record.user_id == user.id and record.revoked_at is None:
        from datetime import datetime, timezone

        record.revoked_at = datetime.now(timezone.utc)
        db.commit()
    return {"status": "signed_out"}


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)) -> UserPublic:
    return UserPublic(id=user.id, email=user.email, full_name=user.full_name, role=user.role.value)


@router.patch("/me", response_model=UserPublic)
def update_me(body: ProfileBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserPublic:
    email = normalize_email(body.email)
    existing = db.scalar(select(User).where(User.email == email, User.id != user.id))
    if existing:
        raise HTTPException(status_code=409, detail={"error": "email_in_use", "message": "An account with that email already exists."})
    user.email = email
    user.full_name = body.full_name.strip()
    db.commit()
    return UserPublic(id=user.id, email=user.email, full_name=user.full_name, role=user.role.value)


@router.post("/password")
def change_password(body: PasswordBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail={"error": "invalid_password", "message": "Current password is incorrect."})
    try:
        user.password_hash = hash_password(body.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": "weak_password", "message": str(exc)}) from exc
    db.commit()
    return {"status": "password_updated"}


@router.get("/sessions", response_model=list[SessionPublic])
def sessions(
    current_session: UUID | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SessionPublic]:
    rows = db.scalars(select(UserSession).where(UserSession.user_id == user.id).order_by(UserSession.created_at.desc())).all()
    return [
        SessionPublic(
            id=row.id,
            created_at=row.created_at,
            expires_at=row.expires_at,
            revoked_at=row.revoked_at,
            ip_address=row.ip_address,
            user_agent=row.user_agent,
            current=row.id == current_session,
        )
        for row in rows
    ]


@router.delete("/sessions/{session_id}")
def revoke_session(session_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    record = db.get(UserSession, session_id)
    if record is None or record.user_id != user.id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Session not found."})
    if record.revoked_at is None:
        from datetime import datetime, timezone

        record.revoked_at = datetime.now(timezone.utc)
        db.commit()
    return {"status": "revoked"}


@router.post("/google")
def google_sign_in() -> None:
    raise HTTPException(
        status_code=501,
        detail={"error": "not_configured", "message": "Google sign-in is not configured for this deployment."},
    )


@router.post("/forgot-password")
def forgot_password() -> None:
    raise HTTPException(
        status_code=501,
        detail={"error": "not_configured", "message": "Password reset email is not configured for this deployment."},
    )


account_router = APIRouter()


@account_router.delete("/account/files")
def delete_files(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _delete_user_files(db, user)
    db.commit()
    return {"status": "files_deleted"}


@account_router.delete("/account")
def delete_account(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _delete_user_files(db, user)
    db.delete(user)
    db.commit()
    return {"status": "account_deleted"}


def _delete_user_files(db: Session, user: User) -> None:
    settings = get_settings()
    storage = LocalObjectStorage(Path(settings.local_storage_dir))
    files = db.scalars(select(UploadedFile).where(UploadedFile.user_id == user.id)).all()
    for uploaded in files:
        try:
            storage.delete(uploaded.stored_key)
        except Exception:
            pass
        db.delete(uploaded)
