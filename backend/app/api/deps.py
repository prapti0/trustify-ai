from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.tokens import InvalidToken, read_user_id
from app.models import User


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> User:
    secret = get_settings().signing_key
    if not secret:
        raise HTTPException(
            status_code=503,
            detail={"error": "auth_unconfigured", "message": "Authentication is not configured."},
        )
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Sign in required."})
    try:
        user_id: UUID = read_user_id(authorization.split(" ", 1)[1].strip(), secret)
    except InvalidToken:
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Sign in required."}) from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Sign in required."})
    return user
