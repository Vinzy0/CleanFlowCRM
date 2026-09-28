"""Email workflow: owner notification, owner-approved customer sends, safety."""

import json

import httpx
import pytest
from app.email import (
    EmailMessage,
    EmailNotConfiguredError,
    EmailProviderError,
    EmailSettings,
    ResendProvider,
    get_email_provider,
)
from app.main import app


def settings_with(**overrides) -> EmailSettings:
    base = dict(api_key="", sender="", owner_address="", demo_override="", demo_mode=False)
    return EmailSettings(**{**base, **overrides})


def owner_notifications(detail):
    return [item for item in detail["activities"] if item["content"].get("email_type") == "owner_notification"]


def customer_emails(detail):
    return [item for item in detail["activities"] if item["content"].get("email_type") == "customer_reply"]


def detail_of(crm, lead_id):
    response = crm.client.get(f"/api/leads/{lead_id}", headers=crm.headers)
    assert response.status_code == 200
    return response.json()


def test_owner_is_notified_with_lead_context_after_analysis(crm, fake_email_provider):
    lead = crm.new_lead()
    notification = owner_notifications(detail_of(crm, lead["id"]))[0]
    assert (notification["type"], notification["status"]) == ("email_sent", "sent")
    message = fake_email_provider.calls[0]
    assert message.to == "owner.inbox@example.com"
    assert "Morgan Lee" in message.subject and "Deep Cleaning" in message.subject
    assert "Priority: normal" in message.body
    assert f"/crm/leads/{lead['id']}" in message.body


def test_notification_failure_keeps_the_lead_and_can_be_retried(crm, fake_email_provider):
    fake_email_provider.fail = True
    lead = crm.new_lead()
    detail = detail_of(crm, lead["id"])
    assert detail["analysis"] is not None
    failed = owner_notifications(detail)[0]
    assert (failed["type"], failed["status"]) == ("email_failed", "failed")
    assert failed["content"]["reason"] == "provider_failure"
    assert not failed["content"]["message"] == ""

    fake_email_provider.fail = False
    retry = crm.client.post(f"/api/leads/{lead['id']}/notify-owner", headers=crm.headers)
    assert retry.status_code == 200
    assert retry.json()["delivered"] is True
    records = owner_notifications(detail_of(crm, lead["id"]))
    assert len(records) == 1
    assert records[0]["id"] == failed["id"]
    assert records[0]["status"] == "sent"
    assert records[0]["content"]["attempts"] == 2


def test_missing_owner_address_is_recorded_rather_than_swallowed(crm, monkeypatch, fake_email_provider):
    monkeypatch.setenv("OWNER_NOTIFICATION_EMAIL", "")
    lead = crm.new_lead()
    record = owner_notifications(detail_of(crm, lead["id"]))[0]
    assert record["status"] == "failed"
    assert record["content"]["reason"] == "not_configured"
    assert fake_email_provider.calls == []
    assert crm.client.post(f"/api/leads/{lead['id']}/notify-owner", headers=crm.headers).status_code == 503


def test_customer_send_requires_authentication_and_operator_approval(crm, fake_email_provider):
    lead = crm.new_lead()
    body = {"subject": "Re: your cleaning request", "body": "Thanks for reaching out about your cleaning."}
    assert crm.client.post(f"/api/leads/{lead['id']}/send-email", json=body).status_code == 401
    notifications_before = len(fake_email_provider.calls)
    draft = crm.client.post(f"/api/leads/{lead['id']}/draft-reply", headers=crm.headers)
    assert draft.status_code == 200
    assert len(fake_email_provider.calls) == notifications_before
    assert customer_emails(detail_of(crm, lead["id"])) == []

    sent = crm.client.post(f"/api/leads/{lead['id']}/send-email", headers=crm.headers, json=body)
    assert sent.status_code == 200
    assert sent.json()["delivered"] is True
    assert fake_email_provider.calls[-1].to == lead["email"]


def test_recipient_cannot_be_chosen_by_the_client(crm, fake_email_provider):
    lead = crm.new_lead()
    body = {"subject": "Re: your cleaning request", "body": "Thanks for reaching out about your cleaning."}
    injected = crm.client.post(
        f"/api/leads/{lead['id']}/send-email",
        headers=crm.headers,
        json={**body, "to": "someone.else@example.com"},
    )
    assert injected.status_code == 422
    accepted = crm.client.post(f"/api/leads/{lead['id']}/send-email", headers=crm.headers, json=body)
    assert accepted.status_code == 200
    assert [message.to for message in fake_email_provider.calls] == ["owner.inbox@example.com", lead["email"]]


def test_duplicate_send_is_suppressed_and_edits_are_new_sends(crm, fake_email_provider):
    lead = crm.new_lead()
    first = {"subject": "Re: your cleaning request", "body": "Thanks for reaching out about your cleaning."}
    assert crm.client.post(f"/api/leads/{lead['id']}/send-email", headers=crm.headers, json=first).json()["delivered"]
    delivered_total = len(fake_email_provider.calls)

    repeat = crm.client.post(f"/api/leads/{lead['id']}/send-email", headers=crm.headers, json=first)
    assert repeat.status_code == 200
    assert repeat.json()["duplicate"] is True
    assert repeat.json()["delivered"] is False
    assert repeat.json()["status"] == "sent"
    assert len(fake_email_provider.calls) == delivered_total

    edited = crm.client.post(
        f"/api/leads/{lead['id']}/send-email",
        headers=crm.headers,
        json={"subject": first["subject"], "body": first["body"] + " We can arrive at 9am."},
    )
    assert edited.json()["delivered"] is True
    assert len(fake_email_provider.calls) == delivered_total + 1
    assert len(customer_emails(detail_of(crm, lead["id"]))) == 2


def test_failed_send_is_recorded_and_retryable(crm, fake_email_provider):
    lead = crm.new_lead()
    body = {"subject": "Re: your cleaning request", "body": "Thanks for reaching out about your cleaning."}
    fake_email_provider.fail = True
    failed = crm.client.post(f"/api/leads/{lead['id']}/send-email", headers=crm.headers, json=body)
    assert failed.status_code == 502
    assert "provider" in failed.json()["detail"].lower()
    record = customer_emails(detail_of(crm, lead["id"]))[0]
    assert (record["type"], record["status"]) == ("email_failed", "failed")

    fake_email_provider.fail = False
    retried = crm.client.post(f"/api/leads/{lead['id']}/send-email", headers=crm.headers, json=body)
    assert retried.status_code == 200
    assert retried.json()["activity_id"] == record["id"]
    retried_record = customer_emails(detail_of(crm, lead["id"]))[0]
    assert retried_record["content"]["attempts"] == 2


def test_send_without_provider_configuration_reports_clearly(crm, monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "")
    monkeypatch.setenv("EMAIL_FROM", "")
    app.dependency_overrides.pop(get_email_provider, None)
    lead = crm.new_lead()
    response = crm.client.post(
        f"/api/leads/{lead['id']}/send-email",
        headers=crm.headers,
        json={"subject": "Re: your cleaning request", "body": "Thanks for reaching out about your cleaning."},
    )
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]
    record = customer_emails(detail_of(crm, lead["id"]))[0]
    assert record["content"]["reason"] == "not_configured"
    assert detail_of(crm, lead["id"])["message"] == lead["message"]


def test_public_demo_disables_sending_without_a_controlled_inbox(crm, monkeypatch, fake_email_provider):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_EMAIL_OVERRIDE", "")
    simulated = crm.client.post("/api/demo/simulate-inquiry", headers=crm.headers)
    assert simulated.status_code == 201
    lead_id = simulated.json()["lead_id"]
    assert fake_email_provider.calls == []
    blocked = crm.client.post(
        f"/api/leads/{lead_id}/send-email",
        headers=crm.headers,
        json={"subject": "Re: your cleaning request", "body": "Thanks for reaching out about your cleaning."},
    )
    assert blocked.status_code == 503
    assert "demo" in blocked.json()["detail"].lower()
    assert fake_email_provider.calls == []


def test_public_demo_redirects_email_to_the_controlled_inbox(crm, monkeypatch, fake_email_provider):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_EMAIL_OVERRIDE", "demo.inbox@example.com")
    simulated = crm.client.post("/api/demo/simulate-inquiry", headers=crm.headers)
    lead_id = simulated.json()["lead_id"]
    assert fake_email_provider.calls[0].to == "demo.inbox@example.com"

    sent = crm.client.post(
        f"/api/leads/{lead_id}/send-email",
        headers=crm.headers,
        json={"subject": "Re: your cleaning request", "body": "Thanks for reaching out about your cleaning."},
    )
    assert sent.status_code == 200
    assert sent.json()["redirected"] is True
    assert sent.json()["delivered_to"] == "demo.inbox@example.com"
    assert fake_email_provider.calls[-1].to == "demo.inbox@example.com"
    record = customer_emails(detail_of(crm, lead_id))[0]
    assert record["content"]["to"].endswith("@example.com")
    assert record["content"]["delivered_to"] == "demo.inbox@example.com"


def test_public_demo_refuses_to_email_records_it_did_not_create(crm, monkeypatch, fake_email_provider):
    lead = crm.new_lead()
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("DEMO_EMAIL_OVERRIDE", "demo.inbox@example.com")
    body = {"subject": "Re: your cleaning request", "body": "Thanks for reaching out about your cleaning."}
    assert crm.client.post(f"/api/leads/{lead['id']}/send-email", headers=crm.headers, json=body).status_code == 403
    assert crm.client.post(f"/api/leads/{lead['id']}/notify-owner", headers=crm.headers).status_code == 403


def test_resend_adapter_payload_and_receipt():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"id": "provider-message-id"})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        provider = ResendProvider(
            config=settings_with(api_key="test-key", sender="Acme Cleaning <no-reply@example.com>"),
            client=client,
        )
        receipt = provider.send(EmailMessage(to="customer@example.com", subject="Hello", body="Body text"))
    assert receipt == "provider-message-id"
    request = requests[0]
    assert str(request.url) == "https://api.resend.com/emails"
    assert request.headers["Authorization"] == "Bearer test-key"
    body = json.loads(request.content)
    assert body["from"] == "Acme Cleaning <no-reply@example.com>"
    assert body["to"] == ["customer@example.com"]
    assert body["subject"] == "Hello"
    assert body["text"] == "Body text"
    assert "api_key" not in body


def test_resend_adapter_without_configuration_never_calls_the_network():
    requests = []

    def respond(request):  # pragma: no cover - must never run
        requests.append(request)
        return httpx.Response(200, json={"id": "unexpected"})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        provider = ResendProvider(config=settings_with(), client=client)
        with pytest.raises(EmailNotConfiguredError):
            provider.send(EmailMessage(to="customer@example.com", subject="Hello", body="Body"))
    assert requests == []


def test_resend_adapter_does_not_expose_provider_errors():
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(401, text="key sk-live-123 rejected"))) as client:
        provider = ResendProvider(config=settings_with(api_key="test-key", sender="Acme <a@example.com>"), client=client)
        with pytest.raises(EmailProviderError) as error:
            provider.send(EmailMessage(to="customer@example.com", subject="Hello", body="Body"))
    assert "sk-live-123" not in str(error.value)


def test_sandbox_transport_records_mail_without_a_contract(crm, monkeypatch, tmp_path):
    """The log transport is a documented sandbox; it must never need a provider key."""
    outbox = tmp_path / "outbox.jsonl"
    monkeypatch.setenv("EMAIL_TRANSPORT", "log")
    monkeypatch.setenv("EMAIL_LOG_PATH", str(outbox))
    monkeypatch.setenv("RESEND_API_KEY", "")
    monkeypatch.setenv("EMAIL_FROM", "")
    app.dependency_overrides.pop(get_email_provider, None)
    lead = crm.new_lead()
    response = crm.client.post(
        f"/api/leads/{lead['id']}/send-email",
        headers=crm.headers,
        json={"subject": "Re: your cleaning request", "body": "Thanks for reaching out about your cleaning."},
    )
    assert response.status_code == 200
    assert response.json()["delivered"] is True
    records = [json.loads(line) for line in outbox.read_text(encoding="utf-8").splitlines()]
    assert [record["to"] for record in records] == ["owner.inbox@example.com", lead["email"]]
    assert records[-1]["subject"] == "Re: your cleaning request"
