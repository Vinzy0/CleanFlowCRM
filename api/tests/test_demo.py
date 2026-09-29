"""Public demo mode: simulated inquiries, fake data only, and safe reset behaviour."""

from app.business import BUSINESS
from app.demo import SCENARIOS, SEED_STAGES
from app.auth import password_hash
from app.models import User


def demo_detail(crm, lead_id):
    response = crm.client.get(f"/api/leads/{lead_id}", headers=crm.headers)
    assert response.status_code == 200
    return response.json()


def simulate(crm, headers=None):
    return crm.client.post("/api/demo/simulate-inquiry", headers=crm.headers if headers is None else headers)


def enable_demo(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_EMAIL_OVERRIDE", "demo.inbox@example.com")


def test_simulated_inquiry_runs_the_real_pipeline(crm, monkeypatch, fake_provider, fake_email_provider):
    enable_demo(monkeypatch)
    response = simulate(crm)
    assert response.status_code == 201
    payload = response.json()
    assert payload["synthetic"] is True
    lead_id = payload["lead_id"]
    detail = demo_detail(crm, lead_id)
    assert detail["is_demo"] is True
    assert detail["name"] in [scenario.name for scenario in SCENARIOS]
    assert detail["service_type"] in BUSINESS["services"]
    assert [item["type"] for item in detail["activities"]] == ["lead_created", "ai_classified", "email_sent"]
    assert detail["analysis"] is not None
    assert detail["analysis"]["service_category"] in BUSINESS["services"]
    assert detail["analysis"]["priority"] in {"high", "normal"}
    assert [call[0] for call in fake_provider.calls] == ["structured"]
    assert fake_email_provider.calls[0].to == "demo.inbox@example.com"


def test_simulated_inquiries_rotate_through_fixed_scenarios(crm, monkeypatch):
    enable_demo(monkeypatch)
    first = simulate(crm).json()
    second = simulate(crm).json()
    assert first["scenario"] in {scenario.slug for scenario in SCENARIOS}
    assert second["scenario"] in {scenario.slug for scenario in SCENARIOS}
    assert first["scenario"] != second["scenario"]


def test_demo_data_is_always_synthetic(crm, monkeypatch):
    enable_demo(monkeypatch)
    assert crm.client.post("/api/demo/reset", headers=crm.headers).status_code == 200
    simulate(crm)
    leads = crm.client.get("/api/leads", headers=crm.headers).json()
    assert len(leads) == len(SEED_STAGES) + 1
    for lead in leads:
        assert lead["is_demo"] is True
        assert lead["email"].endswith("@example.com")
        assert lead["phone"].startswith("+1 555")
        assert lead["message"] in [scenario.message for scenario in SCENARIOS]


def test_demo_reset_seeds_a_populated_workspace(crm, monkeypatch):
    enable_demo(monkeypatch)
    summary = crm.client.post("/api/demo/reset", headers=crm.headers).json()
    assert summary["deleted"] == 0
    assert summary["seeded"] == len(SEED_STAGES)
    leads = crm.client.get("/api/leads", headers=crm.headers).json()
    assert {lead["pipeline_stage"] for lead in leads} == set(BUSINESS["pipeline_stages"])
    analysed = [crm.client.get(f"/api/leads/{lead['id']}", headers=crm.headers).json() for lead in leads]
    assert all(detail["analysis"] is not None for detail in analysed)
    assert any(
        activity["type"] == "status_changed"
        for detail in analysed
        for activity in detail["activities"]
    )


def test_demo_reset_deletes_only_demo_records(crm, monkeypatch):
    real_lead = crm.new_lead()
    enable_demo(monkeypatch)
    first = crm.client.post("/api/demo/reset", headers=crm.headers).json()
    assert first["deleted"] == 0
    simulate(crm)
    second = crm.client.post("/api/demo/reset", headers=crm.headers).json()
    assert second["deleted"] == len(SEED_STAGES) + 1
    leads = crm.client.get("/api/leads", headers=crm.headers).json()
    assert real_lead["id"] in [lead["id"] for lead in leads]
    assert [lead["is_demo"] for lead in leads].count(False) == 1
    assert demo_detail(crm, real_lead["id"])["activities"][0]["type"] == "lead_created"


def test_demo_user_cannot_read_or_mutate_real_leads(crm, monkeypatch, fake_email_provider):
    real = crm.new_lead()
    enable_demo(monkeypatch)
    simulated = simulate(crm).json()["lead_id"]
    with crm.session() as db:
        db.add(User(email="demo@example.com", name="Demo", is_demo=True,
                    password_hash=password_hash.hash("demo-password-123")))
        db.commit()
    login = crm.client.post("/api/auth/login", json={"email": "demo@example.com", "password": "demo-password-123"})
    demo_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert crm.client.get("/api/auth/me", headers=demo_headers).json()["is_demo"] is True
    assert [lead["id"] for lead in crm.client.get("/api/leads", headers=demo_headers).json()] == [simulated]
    url = f"/api/leads/{real['id']}"
    requests = [
        crm.client.get(url, headers=demo_headers),
        crm.client.patch(url, headers=demo_headers, json={"name": "Changed Name"}),
        crm.client.patch(f"{url}/status", headers=demo_headers, json={"stage": "Completed"}),
        crm.client.post(f"{url}/classify", headers=demo_headers),
        crm.client.post(f"{url}/draft-reply", headers=demo_headers),
        crm.client.post(f"{url}/notify-owner", headers=demo_headers),
        crm.client.post(f"{url}/send-email", headers=demo_headers,
                        json={"subject": "Hello", "body": "A message to the customer"}),
        crm.client.delete(url, headers=demo_headers),
    ]
    assert [response.status_code for response in requests] == [404] * (len(requests) - 1) + [403]
    assert demo_detail(crm, real["id"])["name"] == real["name"]
    assert crm.client.get(f"/api/leads/{simulated}", headers=demo_headers).status_code == 200
    assert crm.client.patch(f"/api/leads/{simulated}/status", headers=demo_headers,
                            json={"stage": "Contacted"}).status_code == 200
    assert crm.client.patch(f"/api/leads/{simulated}", headers=demo_headers,
                            json={"email": "outsider@example.com"}).status_code == 403
    assert crm.client.delete(f"/api/leads/{simulated}", headers=demo_headers).status_code == 403
    assert demo_detail(crm, simulated)["email"].endswith("@example.com")
    monkeypatch.setenv("DEMO_MODE", "false")
    assert crm.client.get("/api/auth/me", headers=demo_headers).status_code == 403
    assert crm.client.get("/api/leads", headers=demo_headers).status_code == 403
    assert [message.to for message in fake_email_provider.calls] == ["owner.inbox@example.com", "demo.inbox@example.com"]


def test_public_requests_cannot_mark_a_lead_as_demo(crm):
    tampered = crm.client.post("/api/leads", json=crm.inquiry(is_demo=True))
    assert tampered.status_code == 422
    real = crm.new_lead()
    update = crm.client.patch(f"/api/leads/{real['id']}", headers=crm.headers, json={"is_demo": True})
    assert update.status_code == 422
    assert demo_detail(crm, real["id"])["is_demo"] is False


def test_public_inquiry_is_closed_in_demo_mode(crm, monkeypatch, fake_provider, fake_email_provider):
    enable_demo(monkeypatch)
    response = crm.client.post("/api/leads", json=crm.inquiry(email="person@real-business.com"))
    assert response.status_code == 403
    assert crm.client.get("/api/leads", headers=crm.headers).json() == []
    assert fake_provider.calls == []
    assert fake_email_provider.calls == []
    assert simulate(crm).status_code == 201


def test_demo_reuses_stored_ai_results_instead_of_paying_twice(crm, monkeypatch, fake_provider):
    enable_demo(monkeypatch)
    crm.client.post("/api/demo/reset", headers=crm.headers)
    first_pass = len([call for call in fake_provider.calls if call[0] == "structured"])
    assert first_pass == len(SEED_STAGES)

    again = crm.client.post("/api/demo/reset", headers=crm.headers).json()
    assert again["seeded"] == len(SEED_STAGES)
    assert len([call for call in fake_provider.calls if call[0] == "structured"]) == first_pass
    detail = demo_detail(crm, again["lead_ids"][0])
    classifications = [item for item in detail["activities"] if item["type"] == "ai_classified"]
    assert classifications[-1]["content"]["reused"] is True


def test_demo_endpoints_need_authentication_and_demo_mode(crm, monkeypatch):
    assert simulate(crm, headers={}).status_code == 401
    assert crm.client.post("/api/demo/reset", headers={}).status_code == 401
    assert simulate(crm).status_code == 404
    assert crm.client.post("/api/demo/reset", headers=crm.headers).status_code == 404
    monkeypatch.setenv("DEMO_MODE", "true")
    assert simulate(crm).status_code == 201


def test_public_config_describes_demo_and_email_state(crm, monkeypatch):
    config = crm.client.get("/api/config").json()
    assert config["demo_mode"] is False
    assert config["email_delivery"] == "live"
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_EMAIL_OVERRIDE", "")
    demo_config = crm.client.get("/api/config").json()
    assert demo_config["demo_mode"] is True
    assert demo_config["email_delivery"] == "disabled"
