from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.auth import password_hash
from app.db import Base, get_db
from app.main import app
from app.models import Activity, Lead, User


def test_phase_one_flow(monkeypatch, fake_provider):
    monkeypatch.setenv("JWT_SECRET", "phase-one-test-secret-at-least-thirty-two-characters")
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)

    def test_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_db
    try:
        with Session(engine) as db:
            db.add(User(email="owner@example.com", name="Owner", password_hash=password_hash.hash("correct-password")))
            db.commit()

        client = TestClient(app)
        assert client.get("/api/leads").status_code == 401
        assert client.post("/api/auth/login", json={"email": "owner@example.com", "password": "wrong"}).status_code == 401
        login = client.post("/api/auth/login", json={"email": "owner@example.com", "password": "correct-password"})
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        assert client.get("/api/auth/me", headers=headers).json()["name"] == "Owner"

        payload = {
            "inquiry_key": "7ebf64d4-882a-4e8d-b137-79966b8240f9",
            "name": "Jordan Reyes",
            "email": "jordan@example.com",
            "phone": "+63 912 345 6789",
            "service_type": "Deep Cleaning",
            "property_type": "House",
            "preferred_date": "2026-10-02",
            "message": "Please focus on the kitchen and bathrooms.",
        }
        assert client.post("/api/leads", json={**payload, "service_type": "Invented"}).status_code == 422
        assert client.post("/api/leads", json={**payload, "name": "   "}).status_code == 422
        assert client.post("/api/leads", json={**payload, "message": "          "}).status_code == 422
        created = client.post("/api/leads", json=payload)
        assert created.status_code == 201
        lead_id = created.json()["id"]
        assert client.post("/api/leads", json=payload).json()["id"] == lead_id
        assert len(fake_provider.calls) == 1
        assert client.post("/api/leads", json={**payload, "name": "Another Person"}).status_code == 409
        assert len(client.get("/api/leads", headers=headers).json()) == 1
        assert client.get(f"/api/leads/{lead_id}", headers=headers).json()["message"] == payload["message"]
        updated = client.patch(f"/api/leads/{lead_id}", headers=headers, json={"phone": "+63 999 111 2222"})
        assert updated.status_code == 200
        assert updated.json()["phone"] == "+63 999 111 2222"
        assert client.post("/api/leads", json=payload).json()["id"] == lead_id
        assert client.patch(f"/api/leads/{lead_id}", headers=headers, json={"name": None}).status_code == 422
        with Session(engine) as db:
            assert db.scalar(select(Lead).where(Lead.id == lead_id)) is not None
            assert db.scalar(select(Activity).where(Activity.lead_id == lead_id)).type == "lead_created"
        assert client.delete(f"/api/leads/{lead_id}", headers=headers).status_code == 204
        assert client.get(f"/api/leads/{lead_id}", headers=headers).status_code == 404
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
