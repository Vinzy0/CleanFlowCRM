"""Transactional outbox with at-least-once delivery and bounded automatic retries."""
import hashlib
import hmac
import json
import time
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from . import settings
from .integration_security import decrypt, send_webhook
from .models import Lead, User, WebhookAttempt, WebhookDelivery, WebhookEndpoint, WebhookEvent, now_utc
from .schemas import LeadRead

EVENTS = {"lead.created", "lead.classified", "lead.stage_changed", "appointment.booked", "email.sent", "email.failed"}
MAX_ATTEMPTS = 5


def emit(db: Session, lead: Lead, event_type: str, dedupe_key: str, extra: dict | None = None) -> None:
    """Caller commits event, delivery rows and business mutation in one transaction."""
    if lead.is_demo or settings.flag("DEMO_MODE"):
        return
    if event_type not in EVENTS:
        raise ValueError("Unsupported integration event")
    # Include the immutable inquiry identity: SQLite may reuse deleted integer IDs.
    dedupe_key = f"{lead.inquiry_key}:{dedupe_key}"
    if db.scalar(select(WebhookEvent.id).where(WebhookEvent.dedupe_key == dedupe_key)):
        return
    event_id = str(uuid4())
    occurred = now_utc()
    body = json.dumps({
        "id": event_id, "type": event_type, "schema_version": 1,
        "occurred_at": occurred.isoformat(),
        "data": {"lead": LeadRead.model_validate(lead).model_dump(mode="json"), **(extra or {})},
    }, sort_keys=True, separators=(",", ":"))
    db.add(WebhookEvent(id=event_id, lead_id=lead.id, lead_key=lead.inquiry_key, type=event_type, dedupe_key=dedupe_key, body=body, created_at=occurred))
    db.flush()
    endpoints = db.scalars(select(WebhookEndpoint).join(User, User.id == WebhookEndpoint.owner_id).where(
        WebhookEndpoint.active.is_(True), User.is_demo.is_(False),
    )).all()
    for endpoint in endpoints:
        if event_type in endpoint.events:
            db.add(WebhookDelivery(event_id=event_id, endpoint_id=endpoint.id))


def signature(secret: str, timestamp: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def recover_expired(db: Session) -> None:
    """A crash/unknown result is visible. A retry can duplicate receiver-side work."""
    now = now_utc()
    ids = db.scalars(select(WebhookDelivery.id).where(
        WebhookDelivery.status == "sending", WebhookDelivery.lease_until < now,
    )).all()
    for delivery_id in ids:
        claimed = db.execute(update(WebhookDelivery).where(
            WebhookDelivery.id == delivery_id, WebhookDelivery.status == "sending", WebhookDelivery.lease_until < now,
        ).values(status="failed", lease_until=None).execution_options(synchronize_session="fetch"))
        if claimed.rowcount:
            db.execute(update(WebhookAttempt).where(
                WebhookAttempt.delivery_id == delivery_id, WebhookAttempt.status == "sending",
            ).values(status="failed", result="Worker interrupted; receiver outcome unknown", finished_at=now))
    db.commit()


def deliver(db: Session, delivery_id: int, sender=send_webhook) -> bool:
    if settings.flag("DEMO_MODE"):
        return False
    now = now_utc()
    # Atomic compare-and-set across workers and manual retry requests.
    claimed = db.execute(update(WebhookDelivery).where(
        WebhookDelivery.id == delivery_id, WebhookDelivery.status == "pending",
        WebhookDelivery.next_attempt_at <= now,
    ).values(status="sending", lease_until=now + timedelta(minutes=5), attempts=WebhookDelivery.attempts + 1).execution_options(synchronize_session="fetch"))
    if not claimed.rowcount:
        db.rollback()
        return False
    delivery = db.get(WebhookDelivery, delivery_id)
    db.refresh(delivery)
    attempt = WebhookAttempt(delivery_id=delivery.id, number=delivery.attempts, started_at=now)
    db.add(attempt)
    db.commit()  # Persist the claim and attempt BEFORE making a network request.
    # Keep the claim identity across the network call. An expired worker can return
    # after recovery and a newer attempt; it must not overwrite that result.
    number, attempt_id = attempt.number, attempt.id
    outcome = {}
    delivery_outcome = {"lease_until": None}
    endpoint = db.get(WebhookEndpoint, delivery.endpoint_id)
    owner = db.get(User, endpoint.owner_id) if endpoint else None
    if endpoint is None or not endpoint.active or owner is None or owner.is_demo:
        delivery_outcome["status"] = "cancelled"
        outcome.update(status="cancelled", result="Integration removed or owner unavailable")
    else:
        try:
            event = db.get(WebhookEvent, delivery.event_id)
            body = event.body.encode()
            timestamp = str(int(time.time()))
            status = sender(decrypt(endpoint.url_ciphertext), body, {
                "Content-Type": "application/json", "User-Agent": "Tavo-Webhooks/1",
                "X-Tavo-Event-Id": event.id, "Idempotency-Key": event.id,
                "X-Tavo-Signature": signature(decrypt(endpoint.secret_ciphertext), timestamp, body),
            })
            outcome.update(http_status=status, result=f"HTTP {status}",
                           status="succeeded" if 200 <= status < 300 else "failed")
        except Exception as exc:
            # Never persist exception text: it can contain endpoint tokens/secrets.
            outcome.update(status="failed", result=("Destination rejected" if isinstance(exc, ValueError) else
                           "Timeout" if isinstance(exc, TimeoutError) else "Transport or configuration failure"))
        if outcome["status"] == "succeeded":
            delivery_outcome["status"] = "succeeded"
        elif number < MAX_ATTEMPTS:
            delivery_outcome.update(status="pending", next_attempt_at=now_utc() + timedelta(seconds=30 * 2 ** (number - 1)))
        else:
            delivery_outcome["status"] = "failed"
    finalized = db.execute(update(WebhookDelivery).where(
        WebhookDelivery.id == delivery_id, WebhookDelivery.status == "sending",
        WebhookDelivery.attempts == number,
    ).values(**delivery_outcome).execution_options(synchronize_session="fetch"))
    if not finalized.rowcount:
        db.rollback()
        db.expire_all()
        return True  # A request ran, but recovery/newer attempt owns its outcome.
    db.execute(update(WebhookAttempt).where(
        WebhookAttempt.id == attempt_id, WebhookAttempt.status == "sending",
    ).values(**outcome, finished_at=now_utc()).execution_options(synchronize_session="fetch"))
    db.commit()
    return True


def drain(db: Session, sender=send_webhook, limit: int = 20) -> int:
    if settings.flag("DEMO_MODE"):
        return 0
    recover_expired(db)
    ids = db.scalars(select(WebhookDelivery.id).where(
        WebhookDelivery.status == "pending", WebhookDelivery.next_attempt_at <= now_utc(),
    ).order_by(WebhookDelivery.id).limit(limit)).all()
    return sum(deliver(db, delivery_id, sender) for delivery_id in ids)
