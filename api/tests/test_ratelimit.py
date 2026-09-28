"""Rate limits and AI-usage protection for the public demo."""

from fastapi.testclient import TestClient

from app import ratelimit
from app.main import app


def limit(monkeypatch, bucket: str, value: int, window: int | None = None) -> None:
    monkeypatch.setenv(f"RATE_LIMIT_{bucket.upper()}", str(value))
    if window is not None:
        monkeypatch.setenv(f"RATE_LIMIT_{bucket.upper()}_WINDOW_SECONDS", str(window))
    ratelimit.reset()


def test_sign_in_attempts_are_limited_with_a_clear_message(crm, monkeypatch):
    limit(monkeypatch, "login", 2)
    assert crm.login(password="wrong").status_code == 401
    assert crm.login(password="wrong").status_code == 401
    blocked = crm.login()
    assert blocked.status_code == 429
    assert "sign-in attempts" in blocked.json()["detail"]
    assert int(blocked.headers["retry-after"]) > 0
    assert crm.login().status_code == 429


def test_public_inquiry_submission_is_limited(crm, monkeypatch):
    limit(monkeypatch, "inquiry", 1)
    assert crm.client.post("/api/leads", json=crm.inquiry()).status_code == 201
    blocked = crm.client.post("/api/leads", json=crm.inquiry())
    assert blocked.status_code == 429
    assert "public inquiry submissions" in blocked.json()["detail"]


def test_simulated_inquiries_are_limited(crm, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_EMAIL_OVERRIDE", "demo.inbox@example.com")
    limit(monkeypatch, "simulate", 2)
    assert crm.client.post("/api/demo/simulate-inquiry", headers=crm.headers).status_code == 201
    assert crm.client.post("/api/demo/simulate-inquiry", headers=crm.headers).status_code == 201
    blocked = crm.client.post("/api/demo/simulate-inquiry", headers=crm.headers)
    assert blocked.status_code == 429
    assert "simulated demo inquiries" in blocked.json()["detail"]


def test_ai_and_email_endpoints_are_limited(crm, monkeypatch):
    limit(monkeypatch, "classify", 1)
    limit(monkeypatch, "draft", 1)
    limit(monkeypatch, "email", 1)
    lead = crm.new_lead()
    url = f"/api/leads/{lead['id']}"
    assert crm.client.post(f"{url}/classify", headers=crm.headers).status_code == 200
    assert crm.client.post(f"{url}/classify", headers=crm.headers).status_code == 429
    assert crm.client.post(f"{url}/draft-reply", headers=crm.headers).status_code == 200
    assert crm.client.post(f"{url}/draft-reply", headers=crm.headers).status_code == 429
    email = {"subject": "Re: your cleaning request", "body": "Thanks for reaching out about your cleaning."}
    assert crm.client.post(f"{url}/send-email", headers=crm.headers, json=email).status_code == 200
    assert crm.client.post(f"{url}/send-email", headers=crm.headers, json=email).status_code == 429


def test_demo_resets_are_limited(crm, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_EMAIL_OVERRIDE", "demo.inbox@example.com")
    limit(monkeypatch, "reset", 1)
    assert crm.client.post("/api/demo/reset", headers=crm.headers).status_code == 200
    blocked = crm.client.post("/api/demo/reset", headers=crm.headers)
    assert blocked.status_code == 429
    assert "demo data resets" in blocked.json()["detail"]


def test_limits_apply_per_address(crm, monkeypatch):
    limit(monkeypatch, "inquiry", 1)
    other_caller = TestClient(app, client=("203.0.113.7", 50123))
    assert crm.client.post("/api/leads", json=crm.inquiry()).status_code == 201
    assert crm.client.post("/api/leads", json=crm.inquiry()).status_code == 429
    assert other_caller.post("/api/leads", json=crm.inquiry()).status_code == 201


def test_limits_expire_after_their_window(crm, monkeypatch):
    clock = {"now": 1_000.0}
    monkeypatch.setattr(ratelimit, "_now", lambda: clock["now"])
    limit(monkeypatch, "inquiry", 1, window=60)
    assert crm.client.post("/api/leads", json=crm.inquiry()).status_code == 201
    assert crm.client.post("/api/leads", json=crm.inquiry()).status_code == 429
    clock["now"] += 61
    assert crm.client.post("/api/leads", json=crm.inquiry()).status_code == 201


def test_a_zero_limit_disables_limiting(crm, monkeypatch):
    limit(monkeypatch, "login", 0)
    for _ in range(3):
        assert crm.login(password="wrong").status_code == 401
    assert crm.login().status_code == 200
