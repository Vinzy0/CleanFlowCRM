import hashlib
import hmac
import json
import socket
from datetime import timedelta

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import func, select

from app import webhooks
from app.auth import create_token, password_hash
from app.integration_security import decrypt, get_webhook_sender, public_addresses, validate_url, send_webhook
from app.main import app
from app.models import IntegrationKey, IntegrationRequest, Lead, User, WebhookAttempt, WebhookDelivery, WebhookEndpoint, WebhookEvent, now_utc


@pytest.fixture(autouse=True)
def encryption(monkeypatch):
    monkeypatch.setenv("INTEGRATION_ENCRYPTION_KEY", Fernet.generate_key().decode())
    calls = []

    def sender(url, body, headers):
        calls.append((url, body, headers))
        return 204

    app.dependency_overrides[get_webhook_sender] = lambda: sender
    yield calls
    app.dependency_overrides.pop(get_webhook_sender, None)


def key(crm, scopes=None):
    response = crm.client.post("/api/integrations/keys", headers=crm.headers,
        json={"name": "Make development", **({"scopes": scopes} if scopes else {})})
    assert response.status_code == 201, response.text
    result = response.json()
    return result, {"X-API-Key": result["key"], "Idempotency-Key": "make-event-0001"}


def endpoint(crm, events=None):
    response = crm.client.post("/api/integrations/webhooks", headers=crm.headers, json={
        "name": "Make Sheets", "url": "https://hooks.example.com/private-token", "events": events or ["lead.created"],
    })
    assert response.status_code == 201, response.text
    return response.json()


def external_create(crm, headers, **overrides):
    payload = crm.inquiry(**overrides)
    payload.pop("inquiry_key")
    return crm.client.post("/api/v1/leads", headers=headers, json=payload)


def dispatch(crm):
    return crm.client.post("/api/integrations/dispatch", headers=crm.headers)


def test_key_hash_revocation_and_auth_separation(crm):
    result, headers = key(crm)
    with crm.session() as db:
        stored = db.get(IntegrationKey, result["id"])
        assert stored.digest == hashlib.sha256(result["key"].encode()).hexdigest()
        assert result["key"] not in repr(stored.__dict__)
    listing = crm.client.get("/api/integrations", headers=crm.headers)
    assert result["key"] not in listing.text
    assert crm.client.get("/api/v1/leads", headers=headers).status_code == 200
    assert crm.client.get("/api/leads", headers=headers).status_code == 401
    assert crm.client.get("/api/v1/leads", headers=crm.headers).status_code == 401
    assert crm.client.get("/api/v1/leads", headers={"X-API-Key": "tavo_invalid"}).status_code == 401
    assert crm.client.delete(f"/api/integrations/keys/{result['id']}", headers=crm.headers).status_code == 204
    assert crm.client.get("/api/v1/leads", headers=headers).status_code == 401


def test_external_creation_classification_and_idempotency(crm, fake_provider, encryption):
    endpoint(crm)
    _, headers = key(crm)
    response = external_create(crm, headers, source="Make custom webhook", tags=["web", "web"])
    assert response.status_code == 201, response.text
    lead_id = response.json()["id"]
    detail = crm.client.get(f"/api/v1/leads/{lead_id}", headers=headers).json()
    assert detail["analysis"]["service_category"] == "Deep Cleaning"
    assert detail["source"] == "Make custom webhook" and detail["tags"] == ["web"]
    duplicate = external_create(crm, headers, source="Make custom webhook", tags=["web", "web"])
    assert duplicate.json() == response.json()
    assert len(fake_provider.calls) == 1
    assert external_create(crm, headers, name="Another person").status_code == 409
    with crm.session() as db:
        assert db.scalar(select(func.count()).select_from(Lead)) == 1
        assert db.scalar(select(func.count()).select_from(IntegrationRequest)) == 1
        assert db.scalar(select(func.count()).select_from(WebhookDelivery)) == 1
    assert not encryption  # Outbox delivery is separate from the business request.


def test_external_scopes_validation_and_pagination(crm):
    _, headers = key(crm, ["leads:read"])
    assert external_create(crm, headers).status_code == 403
    lead = crm.new_lead()
    assert crm.client.get("/api/v1/leads?limit=1", headers=headers).json()[0]["id"] == lead["id"]
    assert crm.client.get(f"/api/v1/leads?after_id={lead['id']}", headers=headers).json() == []
    _, write = key(crm, ["leads:write"])
    assert crm.client.get("/api/v1/leads", headers=write).status_code == 403
    assert external_create(crm, write, service_type="not a service").status_code == 422
    missing = {"X-API-Key": write["X-API-Key"]}
    assert external_create(crm, missing).status_code == 422


def test_stage_note_and_appointment_replays(crm):
    endpoint(crm, ["lead.stage_changed", "appointment.booked"])
    _, headers = key(crm)
    lead = crm.new_lead()
    path = f"/api/v1/leads/{lead['id']}"
    payload = {"stage": "Booked"}
    first = crm.client.patch(path + "/stage", headers=headers, json=payload)
    assert first.status_code == 200
    assert crm.client.patch(path + "/stage", headers=headers, json=payload).json() == first.json()
    assert crm.client.patch(path + "/stage", headers=headers, json={"stage": "Completed"}).status_code == 409
    headers["Idempotency-Key"] = "appointment-0001"
    values = {"appointment_at": "2026-10-05T09:00:00+08:00", "next_action": "Confirm appointment", "next_follow_up": "2026-10-04T10:00:00+08:00"}
    assert crm.client.patch(path, headers=headers, json=values).status_code == 200
    assert crm.client.patch(path, headers=headers, json=values).status_code == 200
    headers["Idempotency-Key"] = "bad-time-0001"
    assert crm.client.patch(path, headers=headers, json={"appointment_at": "2026-10-05T09:00:00"}).status_code == 422
    headers["Idempotency-Key"] = "note-event-0001"
    first = crm.client.post(path + "/notes", headers=headers, json={"note": "Called the customer"})
    assert first.status_code == 201
    assert crm.client.post(path + "/notes", headers=headers, json={"note": "Called the customer"}).json() == first.json()
    with crm.session() as db:
        assert db.scalar(select(func.count()).select_from(WebhookDelivery)) == 2


def test_signatures_success_and_duplicate_delivery(crm, encryption):
    config = endpoint(crm)
    crm.new_lead()
    assert dispatch(crm).json()["processed"] == 1
    assert dispatch(crm).json()["processed"] == 0
    url, body, headers = encryption[0]
    envelope = json.loads(body)
    assert envelope["type"] == "lead.created" and envelope["schema_version"] == 1
    signature = headers["X-Tavo-Signature"]
    timestamp, digest = signature.split(",")
    expected = hmac.new(config["signing_secret"].encode(), timestamp[2:].encode() + b"." + body, hashlib.sha256).hexdigest()
    assert hmac.compare_digest(digest[3:], expected)
    assert headers["Idempotency-Key"] == envelope["id"] == headers["X-Tavo-Event-Id"]
    rows = crm.client.get("/api/integrations/deliveries", headers=crm.headers).json()
    assert rows[0]["status"] == "succeeded"
    assert rows[0]["history"][0]["http_status"] == 204
    assert rows[0]["history"][0]["finished_at"]
    assert config["signing_secret"] not in json.dumps(rows)
    assert url not in json.dumps(rows)
    assert crm.client.post(f"/api/integrations/deliveries/{rows[0]['id']}/retry", headers=crm.headers).status_code == 409


@pytest.mark.parametrize("failure", [500, 302, TimeoutError("private-token"), RuntimeError("secret")])
def test_failure_backoff_manual_retry_and_stable_event(crm, encryption, failure):
    endpoint(crm)
    crm.new_lead()

    def fail(url, body, headers):
        if isinstance(failure, Exception):
            raise failure
        return failure

    app.dependency_overrides[get_webhook_sender] = lambda: fail
    assert dispatch(crm).json()["processed"] == 1
    rows = crm.client.get("/api/integrations/deliveries", headers=crm.headers).json()
    row = rows[0]
    assert row["status"] == "pending" and row["history"][0]["status"] == "failed"
    assert "private-token" not in json.dumps(rows) and "secret" not in json.dumps(rows)
    assert dispatch(crm).json()["processed"] == 0
    retry = crm.client.post(f"/api/integrations/deliveries/{row['id']}/retry", headers=crm.headers)
    assert retry.status_code == 200 and retry.json()["event_id"] == row["event_id"]
    app.dependency_overrides[get_webhook_sender] = lambda: lambda *args: 200
    assert dispatch(crm).json()["processed"] == 1
    with crm.session() as db:
        delivery = db.get(WebhookDelivery, row["id"])
        assert delivery.status == "succeeded" and delivery.attempts == 2
        assert db.scalar(select(func.count()).select_from(WebhookAttempt)) == 2


def test_retry_exhaustion_and_crash_recovery(crm):
    endpoint(crm)
    crm.new_lead()
    with crm.session() as db:
        delivery = db.scalar(select(WebhookDelivery))
        for _ in range(5):
            delivery.next_attempt_at = now_utc() - timedelta(seconds=1)
            db.commit()
            assert webhooks.deliver(db, delivery.id, lambda *args: 503)
        assert delivery.status == "failed" and delivery.attempts == 5
        assert not webhooks.deliver(db, delivery.id, lambda *args: 200)
        delivery.status = "sending"
        delivery.lease_until = now_utc() - timedelta(seconds=1)
        db.add(WebhookAttempt(delivery_id=delivery.id, number=6, status="sending"))
        db.commit()
        webhooks.recover_expired(db)
        db.refresh(delivery)
        assert delivery.status == "failed"
        attempt = db.scalar(select(WebhookAttempt).where(WebhookAttempt.number == 6))
        assert "unknown" in attempt.result and attempt.finished_at


def test_subscription_update_removal_and_encrypted_storage(crm, encryption):
    config = endpoint(crm)
    with crm.session() as db:
        stored = db.get(WebhookEndpoint, config["id"])
        assert config["signing_secret"] not in stored.secret_ciphertext
        assert decrypt(stored.url_ciphertext) == "https://hooks.example.com/private-token"
    assert crm.client.patch(f"/api/integrations/webhooks/{config['id']}", headers=crm.headers,
        json={"events": ["lead.classified"]}).status_code == 200
    crm.new_lead()
    rows = crm.client.get("/api/integrations/deliveries", headers=crm.headers).json()
    assert len(rows) == 1 and rows[0]["event_type"] == "lead.classified"
    assert crm.client.delete(f"/api/integrations/webhooks/{config['id']}", headers=crm.headers).status_code == 204
    assert dispatch(crm).json()["processed"] == 0
    assert crm.client.post(f"/api/integrations/deliveries/{rows[0]['id']}/retry", headers=crm.headers).status_code == 409
    with crm.session() as db:
        stored = db.get(WebhookEndpoint, config["id"])
        assert not stored.secret_ciphertext and not stored.url_ciphertext
    assert not encryption


def test_owner_authorization_and_demo_blocking(crm, monkeypatch):
    config = endpoint(crm)
    result, headers = key(crm)
    with crm.session() as db:
        user = User(email="other@example.com", name="Other owner", password_hash=password_hash.hash("other"))
        db.add(user)
        db.commit()
        other = {"Authorization": "Bearer " + create_token(user)}
        user.is_demo = True
        db.commit()
    # Normal second owner cannot edit the first owner's integrations.
    with crm.session() as db:
        user = db.scalar(select(User).where(User.email == "other@example.com"))
        user.is_demo = False
        db.commit()
    assert crm.client.delete(f"/api/integrations/keys/{result['id']}", headers=other).status_code == 404
    assert crm.client.delete(f"/api/integrations/webhooks/{config['id']}", headers=other).status_code == 404
    assert crm.client.get("/api/integrations", headers=other).json()["keys"] == []
    monkeypatch.setenv("DEMO_MODE", "true")
    with crm.session() as db:
        user = db.scalar(select(User).where(User.email == "other@example.com"))
        user.is_demo = True
        db.commit()
    for session_headers in (other, crm.headers):
        assert crm.client.get("/api/integrations", headers=session_headers).status_code == 403
        assert crm.client.post("/api/integrations/keys", headers=session_headers, json={"name": "blocked"}).status_code == 403
        assert crm.client.post("/api/integrations/dispatch", headers=session_headers).status_code == 403
    assert crm.client.get("/api/v1/leads", headers=headers).status_code == 403


def test_no_demo_events_or_external_demo_access(crm):
    endpoint(crm)
    _, headers = key(crm)
    lead = crm.new_lead()
    with crm.session() as db:
        stored = db.get(Lead, lead["id"])
        stored.is_demo = True
        webhooks.emit(db, stored, "lead.classified", "demo-event")
        db.commit()
        assert db.scalar(select(WebhookEvent).where(WebhookEvent.dedupe_key == "demo-event")) is None
    assert crm.client.get(f"/api/v1/leads/{lead['id']}", headers=headers).status_code == 404
    assert crm.client.get("/api/v1/leads", headers=headers).json() == []


def test_event_deduplication_atomic_rollback_and_email_events(crm):
    endpoint(crm, ["lead.created", "email.sent", "email.failed"])
    lead = crm.new_lead()
    with crm.session() as db:
        stored = db.get(Lead, lead["id"])
        count = db.scalar(select(func.count()).select_from(WebhookEvent))
        webhooks.emit(db, stored, "lead.created", f"lead.created:{lead['id']}")
        db.commit()
        assert db.scalar(select(func.count()).select_from(WebhookEvent)) == count
        webhooks.emit(db, stored, "lead.stage_changed", "rolled-back")
        db.rollback()
        assert db.scalar(select(WebhookEvent).where(WebhookEvent.dedupe_key.endswith(":rolled-back"))) is None
        assert "email.sent" in db.scalars(select(WebhookEvent.type)).all()


def test_missing_encryption_does_not_break_crm(crm, monkeypatch):
    monkeypatch.setenv("INTEGRATION_ENCRYPTION_KEY", "")
    response = crm.client.post("/api/integrations/webhooks", headers=crm.headers, json={
        "name": "missing", "url": "https://example.com/hook", "events": ["lead.created"],
    })
    assert response.status_code == 503
    assert crm.new_lead()["id"]


@pytest.mark.parametrize("url", ["http://example.com", "https://user:pass@example.com", "https://example.com:8443", "https://example.com/#fragment", "https://example.com/\nBad", "https://example.com\\evil"])
def test_url_validation(url):
    with pytest.raises(ValueError):
        validate_url(url)


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "::ffff:8.8.8.8", "192.0.2.1", "224.0.0.1", "ff02::1"])
def test_ssrf_dns_rejection(monkeypatch, address):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))])
    with pytest.raises(ValueError):
        public_addresses("example.com")


def test_transport_pins_dns_and_keeps_host_tls(monkeypatch):
    from app import integration_security as security
    observed = []
    monkeypatch.setattr(security, "public_addresses", lambda host: ["8.8.8.8"])

    class Connection:
        def __init__(self, host, address):
            observed.append((host, address))
        def request(self, method, path, body, headers):
            observed.append((method, path, body))
        def getresponse(self):
            return type("Response", (), {"status": 202})()
        def close(self):
            observed.append("closed")

    monkeypatch.setattr(security, "PinnedHTTPSConnection", Connection)
    assert send_webhook("https://example.com/hook?token=test", b"{}", {}) == 202
    assert observed == [("example.com", "8.8.8.8"), ("POST", "/hook?token=test", b"{}"), "closed"]


def test_failed_email_event_and_same_appointment_no_duplicate(crm, fake_email_provider):
    endpoint(crm, ["email.failed", "appointment.booked"])
    fake_email_provider.fail = True
    lead = crm.new_lead()
    path = f"/api/leads/{lead['id']}"
    values = {"appointment_at": "2026-10-05T09:00:00+08:00"}
    assert crm.client.patch(path, headers=crm.headers, json=values).status_code == 200
    assert crm.client.patch(path, headers=crm.headers, json=values).status_code == 200
    detail = crm.client.get(path, headers=crm.headers).json()
    assert detail["appointment_at"] == "2026-10-05T01:00:00Z"
    with crm.session() as db:
        assert db.scalars(select(WebhookEvent.type).where(WebhookEvent.type == "appointment.booked")).all() == ["appointment.booked"]
        assert "email.failed" in db.scalars(select(WebhookEvent.type)).all()


def test_deleted_owner_and_missing_configuration_fail_visible(crm, monkeypatch):
    endpoint(crm)
    crm.new_lead()
    monkeypatch.setenv("INTEGRATION_ENCRYPTION_KEY", "")
    assert dispatch(crm).json()["processed"] == 1
    row = crm.client.get("/api/integrations/deliveries", headers=crm.headers).json()[0]
    assert row["history"][0]["status"] == "failed"
    assert row["history"][0]["result"] == "Transport or configuration failure"
    assert row["history"][0]["http_status"] is None


def test_atomic_claim_prevents_second_sender(crm):
    endpoint(crm)
    crm.new_lead()
    with crm.session() as db:
        delivery = db.scalar(select(WebhookDelivery))
        calls = []
        def sender(*args):
            # While the first claim is active, even a new DB session cannot send again.
            with crm.session() as other:
                assert not webhooks.deliver(other, delivery.id, lambda *a: calls.append("duplicate"))
            calls.append("first")
            return 204
        assert webhooks.deliver(db, delivery.id, sender)
        assert calls == ["first"]


def test_receiver_rejects_tampering_expiry_and_malformed_signature():
    from app.webhook_verify import verify_signature
    body = b'{"id":"synthetic-event"}'
    header = webhooks.signature("synthetic-signing-secret", "1000", body)
    assert verify_signature("synthetic-signing-secret", header, body, now=1000)
    assert not verify_signature("synthetic-signing-secret", header, body + b" ", now=1000)
    assert not verify_signature("synthetic-signing-secret", header, body, now=1301)
    assert not verify_signature("wrong-secret", header, body, now=1000)
    assert not verify_signature("synthetic-signing-secret", "bad", body, now=1000)


def test_deleted_lead_id_reuse_keeps_new_events_separate(crm):
    endpoint(crm)
    first = crm.new_lead()
    assert crm.client.delete(f"/api/leads/{first['id']}", headers=crm.headers).status_code == 204
    second = crm.new_lead(name="New synthetic customer")
    with crm.session() as db:
        assert db.scalar(select(func.count()).select_from(WebhookDelivery)) == 2
    history = crm.client.get(f"/api/integrations/deliveries?lead_id={second['id']}", headers=crm.headers)
    assert history.status_code == 200 and len(history.json()) == 1


def test_external_rate_limit(crm, monkeypatch):
    _, headers = key(crm)
    monkeypatch.setenv("RATE_LIMIT_INTEGRATION", "1")
    assert crm.client.get("/api/v1/leads", headers=headers).status_code == 200
    response = crm.client.get("/api/v1/leads", headers=headers)
    assert response.status_code == 429 and int(response.headers["Retry-After"]) > 0


def test_pre_migration_public_inquiry_fingerprint_is_preserved(crm):
    from app.leads import fingerprint_for
    from app.schemas import LeadCreate
    payload = crm.inquiry()
    old_content = {k: v for k, v in payload.items() if k != "inquiry_key"}
    old_digest = hashlib.sha256(json.dumps(old_content, sort_keys=True).encode()).hexdigest()
    assert fingerprint_for(LeadCreate(**payload)) == old_digest
