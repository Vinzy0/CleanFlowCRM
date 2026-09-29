"""Create the public demo account after migrations on hosts without shell access."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import settings
from .auth import password_hash
from .db import SessionLocal
from .models import User


def ensure_demo_user(db: Session, email: str, password: str) -> str:
    email = email.strip().lower()
    if not email or "@" not in email or len(password) < 12:
        raise ValueError("DEMO_LOGIN_EMAIL and a DEMO_LOGIN_PASSWORD of at least 12 characters are required")
    user = db.scalar(select(User).where(User.email == email))
    if user is not None and not user.is_demo:
        raise ValueError("DEMO_LOGIN_EMAIL belongs to a non-demo account")
    if user is None:
        db.add(User(email=email, name="Public Demo", is_demo=True, password_hash=password_hash.hash(password)))
        db.commit()
        return "created"
    if not password_hash.verify(password, user.password_hash):
        user.password_hash = password_hash.hash(password)
        db.commit()
        return "updated"
    return "ready"


def main() -> None:
    if not settings.flag("DEMO_MODE"):
        print("Demo account bootstrap skipped")
        return
    email = settings.env("DEMO_LOGIN_EMAIL", "") or ""
    password = settings.env("DEMO_LOGIN_PASSWORD", "") or ""
    with SessionLocal() as db:
        result = ensure_demo_user(db, email, password)
    print(f"Demo account {result}")


if __name__ == "__main__":
    main()
