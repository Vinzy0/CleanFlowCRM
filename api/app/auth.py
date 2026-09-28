import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import User


password_hash = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)


def secret() -> str:
    value = os.getenv("JWT_SECRET", "")
    if len(value) < 32:
        raise RuntimeError("JWT_SECRET must be at least 32 characters")
    return value


def create_token(user: User) -> str:
    return jwt.encode(
        {"sub": str(user.id), "exp": datetime.now(timezone.utc) + timedelta(hours=8)},
        secret(),
        algorithm="HS256",
    )


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(401, "Sign in required")
    try:
        payload = jwt.decode(credentials.credentials, secret(), algorithms=["HS256"])
        user_id = int(payload["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError):
        raise HTTPException(401, "Invalid or expired session") from None
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(401, "Invalid or expired session")
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user and password_hash.verify(password, user.password_hash):
        return user
    return None
