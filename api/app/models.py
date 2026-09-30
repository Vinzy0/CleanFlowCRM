from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    inquiry_key: Mapped[str] = mapped_column(String(64), unique=True)
    inquiry_fingerprint: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(320))
    phone: Mapped[str] = mapped_column(String(32))
    service_type: Mapped[str] = mapped_column(String(80))
    property_type: Mapped[str] = mapped_column(String(40))
    preferred_date: Mapped[date] = mapped_column(Date)
    message: Mapped[str] = mapped_column(Text)
    pipeline_stage: Mapped[str] = mapped_column(String(30), default="New")
    priority: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Demo records are the only rows the demo reset is allowed to delete.
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    demo_scenario: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    next_action: Mapped[str | None] = mapped_column(String(500), nullable=True)
    next_follow_up: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    appointment_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )
    analyses: Mapped[list["AIAnalysis"]] = relationship(cascade="all, delete-orphan")
    activities: Mapped[list["Activity"]] = relationship(cascade="all, delete-orphan")


class AIAnalysis(Base):
    __tablename__ = "ai_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    service_category: Mapped[str] = mapped_column(String(80))
    priority: Mapped[str] = mapped_column(String(16))
    summary: Mapped[str] = mapped_column(Text)
    matched_priority_rules: Mapped[list[str]] = mapped_column(JSON)
    classification_rationale: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True)
    type: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20))
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    # One row per outbound email; a unique key makes duplicate sends impossible.
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class IntegrationKey(Base):
    __tablename__ = "integration_keys"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    prefix: Mapped[str] = mapped_column(String(24))
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    scopes: Mapped[list[str]] = mapped_column(JSON)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    # Make webhook paths can themselves contain credentials; encrypt the full URL.
    url_ciphertext: Mapped[str] = mapped_column(Text)
    destination_host: Mapped[str] = mapped_column(String(255))
    secret_ciphertext: Mapped[str] = mapped_column(Text)
    events: Mapped[list[str]] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    type: Mapped[str] = mapped_column(String(60))
    lead_id: Mapped[int] = mapped_column(index=True)
    lead_key: Mapped[str] = mapped_column(String(64))
    dedupe_key: Mapped[str] = mapped_column(String(160), unique=True)
    # Canonical JSON text: every retry sends precisely the same event bytes.
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (UniqueConstraint("event_id", "endpoint_id", name="uq_event_endpoint"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("webhook_events.id"), index=True)
    endpoint_id: Mapped[int] = mapped_column(ForeignKey("webhook_endpoints.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class WebhookAttempt(Base):
    __tablename__ = "webhook_attempts"
    __table_args__ = (UniqueConstraint("delivery_id", "number", name="uq_delivery_attempt"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    delivery_id: Mapped[int] = mapped_column(ForeignKey("webhook_deliveries.id"), index=True)
    number: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), default="sending")
    http_status: Mapped[int | None] = mapped_column(nullable=True)
    result: Mapped[str | None] = mapped_column(String(200), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IntegrationRequest(Base):
    __tablename__ = "integration_requests"
    __table_args__ = (UniqueConstraint("key_id", "token", name="uq_key_request"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    key_id: Mapped[int] = mapped_column(ForeignKey("integration_keys.id"))
    token: Mapped[str] = mapped_column(String(64))
    fingerprint: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status_code: Mapped[int] = mapped_column(default=200)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
