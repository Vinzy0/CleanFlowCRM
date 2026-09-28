"""Outbound email workflow.

Two flows exist, and only one of them can send a customer message:

* ``notify_owner`` runs automatically after AI analysis and never blocks lead
  creation, no matter how badly email fails.
* ``tracked_email`` performs an owner-approved send. Draft generation never
  reaches this module, so an AI draft alone can never send anything.

Every attempt is recorded as an ``Activity`` row keyed by an idempotency key, so
a retry reuses the row and a duplicate send is refused instead of delivered
twice.
"""

import hashlib
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import settings
from .email import EmailMessage, EmailNotConfiguredError, EmailProvider, EmailProviderError, email_settings
from .models import AIAnalysis, Activity, Lead

logger = logging.getLogger(__name__)

OWNER_NOTIFICATION = "owner_notification"
CUSTOMER_REPLY = "customer_reply"


@dataclass(frozen=True)
class EmailOutcome:
    """The tracked activity row plus whether this call actually delivered mail."""

    activity: Activity
    delivered: bool
    duplicate: bool = False


def owner_notification_key(lead_id: int) -> str:
    return hashlib.sha256(f"owner-notification:{lead_id}".encode()).hexdigest()


def customer_reply_key(lead_id: int, subject: str, body: str) -> str:
    """Same lead, subject and body -> same key -> one delivery."""
    digest = hashlib.sha256(f"{lead_id}\n{subject}\n{body}".encode()).hexdigest()
    return digest


def crm_lead_url(lead_id: int) -> str:
    base = (settings.env("CRM_PUBLIC_URL", "http://127.0.0.1:3000") or "").rstrip("/")
    return f"{base}/crm/leads/{lead_id}"


def notify_owner(db: Session, lead: Lead, provider: EmailProvider) -> EmailOutcome | None:
    """Send the new-lead notification. Never raises: lead creation outranks email."""
    try:
        config = email_settings()
        subject = f"New lead: {lead.name} — {lead.service_type}"
        if not config.owner_address:
            key = owner_notification_key(lead.id)
            existing = db.scalar(select(Activity).where(Activity.idempotency_key == key))
            activity = _failed(
                db,
                _record(db, lead, OWNER_NOTIFICATION, key, record=existing, subject=subject),
                subject,
                "not_configured",
                "Owner notifications need OWNER_NOTIFICATION_EMAIL to be set.",
            )
            return EmailOutcome(activity=activity, delivered=False)
        return tracked_email(
            db,
            lead=lead,
            email_type=OWNER_NOTIFICATION,
            subject=subject,
            body=_notification_body(db, lead),
            intended_recipient=config.owner_address,
            idempotency_key=owner_notification_key(lead.id),
            provider=provider,
        )
    except Exception:  # pragma: no cover - defensive: email must never break a lead
        logger.warning("Owner notification failed unexpectedly for lead %s", lead.id, exc_info=True)
        return None


def tracked_email(
    db: Session,
    *,
    lead: Lead,
    email_type: str,
    subject: str,
    body: str,
    intended_recipient: str,
    idempotency_key: str,
    provider: EmailProvider,
) -> EmailOutcome:
    record = db.scalar(select(Activity).where(Activity.idempotency_key == idempotency_key))
    if record is not None and record.status == "sent":
        return EmailOutcome(activity=record, delivered=False, duplicate=True)
    config = email_settings()
    delivered_to = config.resolve_recipient(intended_recipient)
    blocked = "disabled" if config.demo_mode and not config.demo_override else None
    record = _attempt(
        db,
        _record(db, lead, email_type, idempotency_key, record=record, subject=subject),
        provider,
        subject=subject,
        body=body,
        intended_recipient=intended_recipient,
        delivered_to=delivered_to,
        blocked=blocked,
    )
    return EmailOutcome(activity=record, delivered=record.status == "sent")


def _notification_body(db: Session, lead: Lead) -> str:
    analysis = db.scalar(
        select(AIAnalysis)
        .where(AIAnalysis.lead_id == lead.id)
        .order_by(AIAnalysis.created_at.desc(), AIAnalysis.id.desc())
        .limit(1)
    )
    lines = [
        f"Customer: {lead.name}",
        f"Email: {lead.email}",
        f"Phone: {lead.phone}",
        f"Service: {lead.service_type}",
        f"Property: {lead.property_type}",
        f"Preferred date: {lead.preferred_date.isoformat()}",
        f"Priority: {lead.priority or 'not assessed'}",
        f"Stage: {lead.pipeline_stage}",
    ]
    if analysis is not None:
        lines.append(f"AI category: {analysis.service_category}")
        lines.append(f"AI summary: {' | '.join(analysis.summary.splitlines())}")
    lines.append("")
    lines.append(f"Open in the CRM: {crm_lead_url(lead.id)}")
    lines.append("")
    lines.append("This message is an automated notification from CleanFlow CRM.")
    return "\n".join(lines)


def _record(
    db: Session,
    lead: Lead,
    email_type: str,
    idempotency_key: str,
    *,
    record: Activity | None = None,
    subject: str = "",
) -> Activity:
    if record is None:
        record = Activity(
            lead_id=lead.id,
            type="email_sent",
            status="pending",
            idempotency_key=idempotency_key,
            content={},
        )
        db.add(record)
    content = dict(record.content or {})
    record.content = {
        "email_type": email_type,
        "to": content.get("to", lead.email if email_type == CUSTOMER_REPLY else ""),
        "subject": subject or content.get("subject", ""),
        "attempts": int(content.get("attempts", 0)) + 1,
    }
    db.commit()
    db.refresh(record)
    return record


def _attempt(
    db: Session,
    record: Activity,
    provider: EmailProvider,
    *,
    subject: str,
    body: str,
    intended_recipient: str,
    delivered_to: str,
    blocked: str | None,
) -> Activity:
    redirected = delivered_to != intended_recipient
    record.type = "email_sent"
    record.status = "pending"
    record.content = {
        **(record.content or {}),
        "to": intended_recipient,
        "delivered_to": delivered_to,
        "redirected": redirected,
        "subject": subject,
    }
    db.commit()
    if blocked:
        return _failed(
            db, record, subject, blocked, "Email sending is disabled in the public demo.", intended_recipient, delivered_to
        )
    try:
        provider_id = provider.send(EmailMessage(to=delivered_to, subject=subject, body=body))
    except EmailNotConfiguredError:
        return _failed(
            db,
            record,
            subject,
            "not_configured",
            "Email delivery is not configured for this environment.",
            intended_recipient,
            delivered_to,
        )
    except EmailProviderError:
        return _failed(
            db,
            record,
            subject,
            "provider_failure",
            "The email provider could not deliver this message. Retry when it recovers.",
            intended_recipient,
            delivered_to,
        )
    record.type = "email_sent"
    record.status = "sent"
    record.content = {**(record.content or {}), "provider_id": provider_id, "message": "Email sent."}
    db.commit()
    db.refresh(record)
    return record


def _failed(
    db: Session,
    record: Activity,
    subject: str,
    reason: str,
    message: str,
    intended_recipient: str | None = None,
    delivered_to: str | None = None,
) -> Activity:
    record.type = "email_failed"
    record.status = "failed"
    content = {**(record.content or {}), "subject": subject or (record.content or {}).get("subject", ""), "reason": reason, "message": message}
    if intended_recipient is not None:
        content["to"] = intended_recipient
        content["delivered_to"] = delivered_to
    record.content = content
    db.commit()
    db.refresh(record)
    return record
