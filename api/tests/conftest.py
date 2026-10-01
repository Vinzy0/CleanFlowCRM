import pytest
import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from uuid import uuid4

from app import demo, ratelimit
from app.ai import AIProviderError, get_ai_provider
from app.auth import password_hash
from app.db import Base, get_db
from app.email import EmailProviderError, get_email_provider
from app.main import app
from app.models import User


@contextmanager
def postgres_schema():
    """Optional localhost-only PostgreSQL checks, never against an application DB."""
    raw = os.getenv("TAVO_TEST_POSTGRES_URL")
    if not raw:
        raise ValueError("TAVO_TEST_POSTGRES_URL is not configured")
    url = make_url(raw)
    if (url.get_backend_name() != "postgresql" or url.host not in {"localhost", "127.0.0.1", "::1"}
            or not (url.database or "").startswith("tavo_test_")):
        raise ValueError("PostgreSQL tests require localhost and a dedicated tavo_test_ database")
    schema = "test_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as db:
        db.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated = url.update_query_dict({"options": f"-csearch_path={schema}"})
    try:
        yield isolated
    finally:
        with admin.begin() as db:
            db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


class FakeProvider:
    model = "test/mock-model"

    def __init__(self):
        self.calls = []
        self.fail = False
        self.structured_result = {
            "service_category": "Deep Cleaning",
            "priority": "normal",
            "summary": ["Customer requested cleaning"],
            "matched_priority_rules": [],
            "classification_rationale": "No listed high-priority criteria are present.",
        }
        self.text_result = "Hi, thanks for contacting us. We would be glad to discuss your request."

    def structured(self, system, user, schema):
        self.calls.append(("structured", system, user, schema))
        if self.fail:
            raise AIProviderError("Mock failure")
        return self.structured_result

    def text(self, system, user):
        self.calls.append(("text", system, user))
        if self.fail:
            raise AIProviderError("Mock failure")
        return self.text_result


class FakeEmailProvider:
    """Stands in for Resend. Records messages and can be told to fail."""

    def __init__(self):
        self.calls = []
        self.fail = False

    def send(self, message):
        self.calls.append(message)
        if self.fail:
            raise EmailProviderError("Mock email failure")
        return f"mock-email-{len(self.calls)}"


@pytest.fixture(autouse=True)
def fake_provider():
    provider = FakeProvider()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_ai_provider, None)


@pytest.fixture(autouse=True)
def fake_email_provider():
    provider = FakeEmailProvider()
    app.dependency_overrides[get_email_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_email_provider, None)


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch):
    """Keep every test offline and clear of another test's rate-limit counters."""
    monkeypatch.setenv("RESEND_API_KEY", "test-resend-key")
    monkeypatch.setenv("EMAIL_FROM", "Acme Cleaning Services <no-reply@example.com>")
    monkeypatch.setenv("EMAIL_TRANSPORT", "resend")
    monkeypatch.setenv("OWNER_NOTIFICATION_EMAIL", "owner.inbox@example.com")
    monkeypatch.setenv("DEMO_EMAIL_OVERRIDE", "")
    monkeypatch.setenv("DEMO_MODE", "")
    for bucket in ratelimit.BUCKETS:
        monkeypatch.setenv(f"RATE_LIMIT_{bucket.upper()}", "1000")
    ratelimit.reset()
    demo.clear_cached_classifications()
    yield
    ratelimit.reset()
    demo.clear_cached_classifications()


class Crm:
    """Small harness: an in-memory CRM instance with an API client and a token."""

    def __init__(self, client, engine, headers):
        self.client = client
        self.engine = engine
        self.headers = headers
        self.email = "owner@example.com"
        self.password = "correct-password"

    def session(self):
        return Session(self.engine)

    def inquiry(self, **overrides):
        payload = {
            "inquiry_key": str(uuid4()),
            "name": "Morgan Lee",
            "email": "morgan@example.com",
            "phone": "+1 555 0100",
            "service_type": "Deep Cleaning",
            "property_type": "House",
            "preferred_date": "2026-10-05",
            "message": "Please clean the kitchen and bedrooms next week.",
        }
        payload.update(overrides)
        return payload

    def new_lead(self, **overrides):
        response = self.client.post("/api/leads", json=self.inquiry(**overrides))
        assert response.status_code == 201, response.text
        return response.json()

    def login(self, password=None):
        return self.client.post(
            "/api/auth/login", json={"email": self.email, "password": password or self.password}
        )


@pytest.fixture
def crm(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "cleanflow-test-secret-at-least-thirty-two-characters")
    schema_context = postgres_schema() if os.getenv("TAVO_TEST_POSTGRES_URL") else None
    if schema_context:
        engine = create_engine(schema_context.__enter__())
    else:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)

    def test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    with Session(engine) as db:
        db.add(User(email="owner@example.com", name="Owner", password_hash=password_hash.hash("correct-password")))
        db.commit()
    client = TestClient(app)
    token = client.post(
        "/api/auth/login", json={"email": "owner@example.com", "password": "correct-password"}
    ).json()["access_token"]
    harness = Crm(client, engine, {"Authorization": f"Bearer {token}"})
    yield harness
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()
    if schema_context:
        schema_context.__exit__(None, None, None)
