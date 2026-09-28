"""Resend email boundary.

Mirrors the AI provider shape: business logic depends on ``EmailProvider``, and
the adapter owns the endpoint, transport and credentials. Nothing here is
imported by the frontend, and no secret ever reaches a response body or a log.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import uuid4

import httpx

from . import settings

RESEND_ENDPOINT = "https://api.resend.com/emails"
LOG_TRANSPORT = "log"
RESEND_TRANSPORT = "resend"
DEFAULT_LOG_PATH = Path(__file__).resolve().parents[1] / "email-outbox.jsonl"


class EmailProviderError(Exception):
    """Safe, provider-independent error; never contains a key or response body."""


class EmailNotConfiguredError(EmailProviderError):
    """Email delivery is switched off or missing credentials."""


@dataclass(frozen=True)
class EmailSettings:
    api_key: str
    sender: str
    owner_address: str
    demo_override: str
    demo_mode: bool
    transport: str = RESEND_TRANSPORT

    @property
    def delivery(self) -> str:
        """``live``, ``sandbox``, ``redirected`` (demo inbox) or ``disabled``."""
        if self.demo_mode and not self.demo_override:
            return "disabled"
        if self.transport == LOG_TRANSPORT:
            return "redirected" if self.demo_override else "sandbox"
        if self.demo_override:
            return "redirected"
        return "live" if self.api_key and self.sender else "disabled"

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.sender)

    def resolve_recipient(self, intended: str) -> str:
        """Public demo traffic never reaches a real customer or owner address."""
        return self.demo_override or intended


def email_settings() -> EmailSettings:
    return EmailSettings(
        api_key=settings.env("RESEND_API_KEY", "") or "",
        sender=settings.env("EMAIL_FROM", "") or "",
        owner_address=settings.env("OWNER_NOTIFICATION_EMAIL", "") or "",
        demo_override=settings.env("DEMO_EMAIL_OVERRIDE", "") or "",
        demo_mode=settings.flag("DEMO_MODE"),
        transport=(settings.env("EMAIL_TRANSPORT", RESEND_TRANSPORT) or RESEND_TRANSPORT).lower(),
    )


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    body: str
    reply_to: str | None = None


class EmailProvider(Protocol):
    def send(self, message: EmailMessage) -> str:
        """Deliver a message and return the provider's message id."""


class ResendProvider:
    def __init__(self, config: EmailSettings | None = None, client: httpx.Client | None = None):
        self.config = config or email_settings()
        self.client = client

    def send(self, message: EmailMessage) -> str:
        if not self.config.configured:
            raise EmailNotConfiguredError("Email delivery is not configured")
        payload = {
            "from": self.config.sender,
            "to": [message.to],
            "subject": message.subject,
            "text": message.body,
        }
        if message.reply_to:
            payload["reply_to"] = message.reply_to
        headers = {"Authorization": f"Bearer {self.config.api_key}", "Content-Type": "application/json"}
        try:
            if self.client is None:
                with httpx.Client(timeout=20.0) as client:
                    response = client.post(RESEND_ENDPOINT, json=payload, headers=headers)
            else:
                response = self.client.post(RESEND_ENDPOINT, json=payload, headers=headers)
            response.raise_for_status()
            provider_id = response.json().get("id")
        except (httpx.HTTPError, ValueError, AttributeError) as exc:
            raise EmailProviderError("Email provider request failed") from exc
        return provider_id if isinstance(provider_id, str) else ""


class LogProvider:
    """Sandbox transport for local development and the hosted demo.

    Writes each message to a JSON-lines file instead of delivering it. Selected
    only through ``EMAIL_TRANSPORT=log``; production uses Resend.
    """

    def __init__(self, config: EmailSettings | None = None, path: Path | None = None):
        self.config = config or email_settings()
        self.path = path or Path(settings.env("EMAIL_LOG_PATH", "") or DEFAULT_LOG_PATH)

    def send(self, message: EmailMessage) -> str:
        record = {
            "id": f"log-{uuid4()}",
            "from": self.config.sender or "sandbox@localhost",
            "to": message.to,
            "subject": message.subject,
            "text": message.body,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            with self.path.open("a", encoding="utf-8") as outbox:
                outbox.write(json.dumps(record) + "\n")
        except OSError as exc:
            raise EmailProviderError("Email sandbox could not record the message") from exc
        return record["id"]


def get_email_provider() -> EmailProvider:
    """Resend by default; the sandbox sink only when explicitly selected."""
    if email_settings().transport == LOG_TRANSPORT:
        return LogProvider()
    return ResendProvider()
