from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt

ALGORITHM = "HS256"
ACCESS_MINUTES = 60 * 12


class InvalidToken(Exception):
    pass


def create_access_token(user_id: UUID, secret: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ACCESS_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def read_user_id(token: str, secret: str) -> UUID:
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        return UUID(str(payload["sub"]))
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise InvalidToken from exc
