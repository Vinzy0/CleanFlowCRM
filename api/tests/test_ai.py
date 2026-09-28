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
        assert [item["type"] for item in detail["activities"]] == ["lead_created", "ai_classified", "email_sent"]
        assert detail["activities"][1]["status"] == "completed"
        assert detail["activities"][2]["content"]["email_type"] == "owner_notification"
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
        assert [item["status"] for item in detail["activities"] if item["type"] == "ai_classified"] == ["failed"]
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


def test_empty_provider_response_is_retried_once_then_succeeds():
    """OpenRouter sometimes answers with an empty completion; one retry absorbs it."""
    requests = []
    payload = {"service_category": "Deep Cleaning", "priority": "normal", "summary": ["Ok"],
               "matched_priority_rules": [], "classification_rationale": "No listed criteria apply."}

    def respond(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(200, json={"choices": [{"message": {"content": "   "}}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(payload)}}]})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        provider = OpenRouterProvider(key="test-secret", client=client)
        assert provider.structured("system", "user", {"type": "object"}) == payload
    assert len(requests) == 2


def test_persistently_unusable_responses_fail_within_the_attempt_budget():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "not json at all"}}]})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        provider = OpenRouterProvider(key="test-secret", client=client, attempts=2)
        try:
            provider.structured("system", "user", {"type": "object"})
            assert False, "Expected AIProviderError"
        except AIProviderError as exc:
            assert "not json" not in str(exc)
    assert len(requests) == 2

    requests.clear()

    def respond_empty(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": ""}}]})

    with httpx.Client(transport=httpx.MockTransport(respond_empty)) as client:
        provider = OpenRouterProvider(key="test-secret", client=client)
        try:
            provider.text("system", "user")
            assert False, "Expected AIProviderError"
        except AIProviderError:
            pass
    assert len(requests) == 2


def test_http_errors_are_not_retried():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(429, text="slow down")

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        provider = OpenRouterProvider(key="test-secret", client=client, attempts=3)
        try:
            provider.structured("system", "user", {"type": "object"})
            assert False, "Expected AIProviderError"
        except AIProviderError:
            pass
    assert len(requests) == 1


def test_attempt_budget_is_configurable_from_the_environment(monkeypatch):
    monkeypatch.setenv("OPENROUTER_MAX_ATTEMPTS", "4")
    assert OpenRouterProvider(key="").attempts == 2
    monkeypatch.setenv("OPENROUTER_MAX_ATTEMPTS", "1")
    assert OpenRouterProvider(key="").attempts == 1
    monkeypatch.setenv("OPENROUTER_MAX_ATTEMPTS", "not-a-number")
    assert OpenRouterProvider(key="").attempts == 2


def test_truncated_reasoning_response_is_retried_with_a_larger_budget():
    """A reasoning model can burn the whole budget and return no content at all."""
    import json as jsonlib
    requests = []
    payload = {"service_category": "Move-In / Move-Out", "priority": "high", "summary": ["Urgent move-out"],
               "matched_priority_rules": ["Urgent move-out deadline"],
               "classification_rationale": "The customer hands back the keys tomorrow."}

    def respond(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(200, json={"choices": [{"message": {"content": ""}, "finish_reason": "length"}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": jsonlib.dumps(payload)}, "finish_reason": "stop"}]})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        provider = OpenRouterProvider(key="test-secret", client=client)
        assert provider.structured("system", "user", {"type": "object"}) == payload
    budgets = [jsonlib.loads(request.content)["max_tokens"] for request in requests]
    assert len(requests) == 2
    assert budgets[1] > budgets[0], budgets


def test_completion_budgets_leave_room_for_reasoning_tokens():
    import json as jsonlib
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}]})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        provider = OpenRouterProvider(key="test-secret", client=client)
        provider.structured("system", "user", {"type": "object"})
        provider.text("system", "user")
    structured_budget, text_budget = (jsonlib.loads(request.content)["max_tokens"] for request in requests)
    assert structured_budget >= 4000
    assert text_budget >= 2000
