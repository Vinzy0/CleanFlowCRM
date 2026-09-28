from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth import password_hash
from app.db import Base, get_db
from app.main import app
from app.models import User


def test_status_changes_and_activity_timeline(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "phase-two-test-secret-at-least-thirty-two-characters")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
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
        token = client.post("/api/auth/login", json={"email": "owner@example.com", "password": "correct-password"}).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post("/api/leads", json={
            "inquiry_key": str(uuid4()),
            "name": "Taylor Cruz",
            "email": "taylor@example.com",
            "phone": "+63 912 444 5555",
            "service_type": "Move-In / Move-Out",
            "property_type": "Apartment",
            "preferred_date": "2026-10-04",
            "message": "Moving this weekend; please clean all rooms.",
        })
        assert created.status_code == 201
        lead_id = created.json()["id"]
        detail_url = f"/api/leads/{lead_id}"
        initial = client.get(detail_url, headers=headers).json()
        assert initial["pipeline_stage"] == "New"
        assert initial["analysis"]["priority"] == "normal"
        assert [item["type"] for item in initial["activities"]] == ["lead_created", "ai_classified", "email_sent"]
        assert client.patch(f"{detail_url}/status", json={"stage": "Contacted"}).status_code == 401
        assert client.patch(f"{detail_url}/status", headers=headers, json={"stage": "Lost"}).status_code == 422

        for stage in ("Contacted", "Booked", "Completed"):
            response = client.patch(f"{detail_url}/status", headers=headers, json={"stage": stage})
            assert response.status_code == 200
            assert response.json()["pipeline_stage"] == stage
        no_op = client.patch(f"{detail_url}/status", headers=headers, json={"stage": "Completed"})
        assert no_op.status_code == 200
        persisted = client.get(detail_url, headers=headers).json()
        assert persisted["pipeline_stage"] == "Completed"
        status_changes = [item for item in persisted["activities"] if item["type"] == "status_changed"]
        assert [item["content"] for item in status_changes] == [
            {"from": "New", "to": "Contacted"},
            {"from": "Contacted", "to": "Booked"},
            {"from": "Booked", "to": "Completed"},
        ]
        assert persisted["updated_at"] >= initial["updated_at"]
        assert client.get("/api/leads", headers=headers).json()[0]["pipeline_stage"] == "Completed"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
