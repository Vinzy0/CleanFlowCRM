import json
from uuid import uuid4

import httpx
import app.ai as ai_module
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.ai import AIProviderError, OpenRouterProvider
from app.auth import password_hash
from app.db import Base, get_db
from app.main import app
from app.models import User


def setup_client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "phase-three-test-secret-at-least-thirty-two-characters")
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
    token = client.post("/api/auth/login", json={"email": "owner@example.com", "password": "correct-password"}).json()["access_token"]
    payload = {
        "inquiry_key": str(uuid4()), "name": "Morgan Lee", "email": "morgan@example.com",
        "phone": "+63 912 345 6789", "service_type": "Deep Cleaning", "property_type": "House",
        "preferred_date": "2026-10-05", "message": "Please clean the kitchen and bedrooms next week.",
    }
    return client, engine, {"Authorization": f"Bearer {token}"}, payload


def test_classification_persistence_and_draft_are_mocked(monkeypatch, fake_provider):
    client, engine, headers, payload = setup_client(monkeypatch)
    try:
        fake_provider.structured_result = {
            "service_category": "Deep Cleaning", "priority": "high",
            "summary": ["Deep cleaning", "Kitchen and bedrooms"],
            "matched_priority_rules": ["Immediate response requested"],
            "classification_rationale": "Customer explicitly requested an immediate response.",
        }
        created = client.post("/api/leads", json=payload)
        assert created.status_code == 201
        lead_id = created.json()["id"]
        detail_url = f"/api/leads/{lead_id}"
        detail = client.get(detail_url, headers=headers).json()
        assert detail["priority"] == "high"
        assert detail["analysis"]["service_category"] == "Deep Cleaning"
        assert detail["analysis"]["matched_priority_rules"] == ["Immediate response requested"]
        assert detail["analysis"]["summary"] == "• Deep cleaning\n• Kitchen and bedrooms"
        assert detail["analysis"]["model"] == "test/mock-model"
        assert [item["type"] for item in detail["activities"]] == ["lead_created", "ai_classified"]
        assert detail["activities"][1]["status"] == "completed"
        assert client.post(f"{detail_url}/draft-reply").status_code == 401
        draft = client.post(f"{detail_url}/draft-reply", headers=headers)
        assert draft.status_code == 200
        assert draft.json()["draft"] == fake_provider.text_result
        assert client.get(detail_url, headers=headers).json()["activities"][-1]["type"] == "reply_generated"
        assert [call[0] for call in fake_provider.calls] == ["structured", "text"]
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_invalid_or_failed_classification_keeps_lead_and_allows_retry(monkeypatch, fake_provider):
    client, engine, headers, payload = setup_client(monkeypatch)
    try:
        fake_provider.structured_result["priority"] = "urgent"
        created = client.post("/api/leads", json=payload)
        assert created.status_code == 201
        lead_id = created.json()["id"]
        detail_url = f"/api/leads/{lead_id}"
        detail = client.get(detail_url, headers=headers).json()
        assert detail["analysis"] is None
        assert detail["activities"][-1]["status"] == "failed"
        assert client.post(f"{detail_url}/classify").status_code == 401
        fake_provider.fail = True
        assert client.post(f"{detail_url}/classify", headers=headers).status_code == 503
        fake_provider.fail = False
        fake_provider.structured_result["priority"] = "normal"
        assert client.post(f"{detail_url}/classify", headers=headers).status_code == 200
        detail = client.get(detail_url, headers=headers).json()
        assert detail["analysis"]["priority"] == "normal"
        assert [item["status"] for item in detail["activities"] if item["type"] == "ai_classified"] == [
            "failed", "failed", "completed"
        ]
        fake_provider.fail = True
        assert client.post(f"{detail_url}/draft-reply", headers=headers).status_code == 503
        assert client.get(detail_url, headers=headers).json()["activities"][-1]["status"] == "failed"
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_openrouter_adapter_uses_backend_endpoint_and_key_without_live_request():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"ok": True})}}]})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        provider = OpenRouterProvider(key="test-secret", model="deepseek/deepseek-v4.1-flash", client=client)
        assert provider.structured("system", "user", {"type": "object"}) == {"ok": True}
    request = requests[0]
    assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer test-secret"
    body = json.loads(request.content)
    assert body["model"] == "deepseek/deepseek-v4.1-flash"
    assert body["response_format"]["type"] == "json_schema"
    assert body["provider"]["require_parameters"] is True
    assert body["plugins"] == [{"id": "response-healing"}]


def test_openrouter_adapter_does_not_expose_provider_response():
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(401, text="secret details"))) as client:
        provider = OpenRouterProvider(key="test-secret", client=client)
        try:
            provider.text("system", "user")
            assert False, "Expected AIProviderError"
        except AIProviderError as exc:
            assert "secret" not in str(exc)


def test_openrouter_adapter_with_no_key_never_calls_transport():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        provider = OpenRouterProvider(key="", client=client)
        try:
            provider.text("system", "user")
            assert False, "Expected AIProviderError"
        except AIProviderError:
            pass
    assert requests == []


def test_openrouter_model_is_selected_from_backend_environment(monkeypatch, tmp_path):
    monkeypatch.setattr(ai_module, "PROJECT_ENV", tmp_path / "missing.env")
    monkeypatch.setenv("OPENROUTER_MODEL", "deepseek/configured-model")
    assert OpenRouterProvider(key="").model == "deepseek/configured-model"


def test_project_key_takes_precedence_for_direct_local_backend(monkeypatch, tmp_path):
    local_env = tmp_path / ".env"
    local_env.write_text("OPENROUTER_API_KEY=test-project-key\nOPENROUTER_MODEL=deepseek/deepseek-v4.1-flash\n")
    monkeypatch.setattr(ai_module, "PROJECT_ENV", local_env)
    monkeypatch.setenv("OPENROUTER_API_KEY", "unrelated-inherited-key")
    assert OpenRouterProvider().key == "test-project-key"
    assert OpenRouterProvider().model == "deepseek/deepseek-v4.1-flash"
