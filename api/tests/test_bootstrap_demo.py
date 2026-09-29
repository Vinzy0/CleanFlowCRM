import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.auth import authenticate, password_hash
from app.bootstrap_demo import ensure_demo_user
from app.db import Base
from app.models import User


def test_demo_bootstrap_is_idempotent_and_rotates_password():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        assert ensure_demo_user(db, " Demo@Example.com ", "first-password-123") == "created"
        assert ensure_demo_user(db, "demo@example.com", "first-password-123") == "ready"
        assert ensure_demo_user(db, "demo@example.com", "second-password-123") == "updated"
        assert authenticate(db, "demo@example.com", "first-password-123") is None
        assert authenticate(db, "demo@example.com", "second-password-123").is_demo
        assert len(db.scalars(select(User)).all()) == 1
    engine.dispose()


def test_demo_bootstrap_refuses_real_account_and_weak_password():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(email="owner@example.com", name="Owner", is_demo=False, password_hash=password_hash.hash("a-long-real-password")))
        db.commit()
        with pytest.raises(ValueError, match="non-demo"):
            ensure_demo_user(db, "owner@example.com", "a-long-demo-password")
        with pytest.raises(ValueError, match="at least 12"):
            ensure_demo_user(db, "new@example.com", "short")
    engine.dispose()
