"""Session-only configuration; separately scoped, versioned external lead API."""
import hashlib
import json
import secrets
from typing import Annotated
from uuid import NAMESPACE_URL, uuid5

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import leads, webhooks
from .ai import AIProvider, get_ai_provider
from .auth import current_user
from .db import get_db
from .email import EmailProvider, get_email_provider
from .integration_security import SCOPES, encrypt, external_key, get_webhook_sender, owner_only, require_scope, validate_url
from .models import Activity, IntegrationKey, IntegrationRequest, Lead, User, WebhookAttempt, WebhookDelivery, WebhookEndpoint, WebhookEvent, now_utc
from .schemas import LeadCreate, LeadDetailRead, LeadRead, LeadUpdate, StatusChange

router = APIRouter()
Db = Annotated[Session, Depends(get_db)]


def integration_owner(user: User = Depends(current_user)) -> User:
    owner_only(user)
    return user


Owner = Annotated[User, Depends(integration_owner)]
Key = Annotated[IntegrationKey, Depends(external_key)]
Idempotency = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")]


class KeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    scopes: list[str] = Field(default_factory=lambda: ["leads:read", "leads:write"], min_length=1, max_length=2)

    @field_validator("scopes")
    @classmethod
    def supported(cls, value):
        if not set(value) <= SCOPES or len(set(value)) != len(value):
            raise ValueError("Select supported, unique scopes")
        return value


class EndpointCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    url: str = Field(max_length=2048)
    events: list[str] = Field(min_length=1, max_length=len(webhooks.EVENTS))

    @field_validator("url")
    @classmethod
    def secure_url(cls, value):
        validate_url(value)
        return value

    @field_validator("events")
    @classmethod
    def supported(cls, value):
        if not set(value) <= webhooks.EVENTS or len(set(value)) != len(value):
            raise ValueError("Select supported, unique events")
        return value


class EndpointUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[str] = Field(min_length=1, max_length=len(webhooks.EVENTS))
    supported = field_validator("events")(EndpointCreate.supported.__func__)


class ExternalLeadCreate(LeadCreate):
    # External clients use the required Idempotency-Key header, not the public-form UUID.
    inquiry_key: str = Field(default="", exclude=True)

    @field_validator("inquiry_key")
    @classmethod
    def valid_inquiry_key(cls, value):
        if value:
            raise ValueError("Use the Idempotency-Key header")
        return value


class NoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    note: str = Field(min_length=1, max_length=5000)


def owned(db: Session, model, record_id: int, user: User):
    row = db.get(model, record_id)
    if row is None or row.owner_id != user.id:
        raise HTTPException(404, "Integration not found")
    return row


def key_read(key):
    return {field: getattr(key, field) for field in ("id", "name", "prefix", "scopes", "revoked_at", "last_used_at", "created_at")}


def endpoint_read(endpoint):
    return {field: getattr(endpoint, field) for field in ("id", "name", "destination_host", "events", "active", "created_at")}


@router.get("/api/integrations")
def overview(db: Db, user: Owner):
    return {
        "keys": [key_read(k) for k in db.scalars(select(IntegrationKey).where(IntegrationKey.owner_id == user.id).order_by(IntegrationKey.id.desc()))],
        "endpoints": [endpoint_read(e) for e in db.scalars(select(WebhookEndpoint).where(WebhookEndpoint.owner_id == user.id).order_by(WebhookEndpoint.id.desc()))],
        "events": sorted(webhooks.EVENTS),
    }


@router.post("/api/integrations/keys", status_code=201)
def create_key(payload: KeyCreate, db: Db, user: Owner, response: Response):
    raw = "tavo_" + secrets.token_urlsafe(32)
    key = IntegrationKey(owner_id=user.id, name=payload.name, prefix=raw[:13],
                         digest=hashlib.sha256(raw.encode()).hexdigest(), scopes=payload.scopes)
    db.add(key)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {**key_read(key), "key": raw}  # Shown once; never included in list responses.


@router.delete("/api/integrations/keys/{key_id}", status_code=204)
def revoke_key(key_id: int, db: Db, user: Owner):
    key = owned(db, IntegrationKey, key_id, user)
    key.revoked_at = key.revoked_at or now_utc()
    db.commit()


@router.post("/api/integrations/webhooks", status_code=201)
def create_endpoint(payload: EndpointCreate, db: Db, user: Owner, response: Response):
    secret = secrets.token_urlsafe(32)
    endpoint = WebhookEndpoint(owner_id=user.id, name=payload.name,
                               destination_host=validate_url(payload.url), url_ciphertext=encrypt(payload.url),
                               secret_ciphertext=encrypt(secret), events=payload.events)
    db.add(endpoint)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {**endpoint_read(endpoint), "signing_secret": secret}


@router.patch("/api/integrations/webhooks/{endpoint_id}")
def update_endpoint(endpoint_id: int, payload: EndpointUpdate, db: Db, user: Owner):
    endpoint = owned(db, WebhookEndpoint, endpoint_id, user)
    if not endpoint.active:
        raise HTTPException(409, "Integration was removed; register a new destination")
    endpoint.events = payload.events
    db.commit()
    return endpoint_read(endpoint)


@router.delete("/api/integrations/webhooks/{endpoint_id}", status_code=204)
def remove_endpoint(endpoint_id: int, db: Db, user: Owner):
    endpoint = owned(db, WebhookEndpoint, endpoint_id, user)
    endpoint.active = False
    # Keep audit rows, erase decryptable destination and signing credential.
    endpoint.url_ciphertext = ""
    endpoint.secret_ciphertext = ""
    db.execute(update(WebhookDelivery).where(WebhookDelivery.endpoint_id == endpoint.id,
                                             WebhookDelivery.status.in_(["pending", "failed"])).values(status="cancelled"))
    db.commit()


@router.get("/api/integrations/deliveries")
def deliveries(db: Db, user: Owner, limit: int = 50, lead_id: int | None = None):
    lead = db.get(Lead, lead_id) if lead_id is not None else None
    if lead_id is not None and (lead is None or lead.is_demo):
        raise HTTPException(404, "Lead not found")
    rows = db.execute(select(WebhookDelivery, WebhookEvent.type, WebhookEndpoint.name).join(
        WebhookEndpoint, WebhookDelivery.endpoint_id == WebhookEndpoint.id,
    ).join(WebhookEvent, WebhookDelivery.event_id == WebhookEvent.id).where(
        WebhookEndpoint.owner_id == user.id,
        *([WebhookEvent.lead_id == lead_id, WebhookEvent.lead_key == lead.inquiry_key] if lead is not None else []),
    ).order_by(WebhookDelivery.id.desc()).limit(max(1, min(limit, 100)))).all()
    return [{
        "id": d.id, "event_id": d.event_id, "event_type": event_type, "destination": name,
        "status": d.status, "attempts": d.attempts, "created_at": d.created_at, "next_attempt_at": d.next_attempt_at,
        "history": [{field: getattr(a, field) for field in ("number", "status", "http_status", "result", "started_at", "finished_at")}
                    for a in db.scalars(select(WebhookAttempt).where(WebhookAttempt.delivery_id == d.id).order_by(WebhookAttempt.number))],
    } for d, event_type, name in rows]


@router.post("/api/integrations/deliveries/{delivery_id}/retry")
def retry_delivery(delivery_id: int, db: Db, user: Owner):
    delivery = db.get(WebhookDelivery, delivery_id)
    if delivery is None:
        raise HTTPException(404, "Delivery not found")
    endpoint = owned(db, WebhookEndpoint, delivery.endpoint_id, user)
    if not endpoint.active:
        raise HTTPException(409, "Integration was removed")
    # Allow a failed attempt waiting for automatic retry to be retried immediately.
    previous = db.scalar(select(WebhookAttempt).where(WebhookAttempt.delivery_id == delivery.id).order_by(WebhookAttempt.number.desc()))
    if delivery.status not in {"pending", "failed"} or previous is None or previous.status != "failed":
        raise HTTPException(409, "Only failed deliveries can be retried")
    claimed = db.execute(update(WebhookDelivery).where(WebhookDelivery.id == delivery.id,
        WebhookDelivery.status.in_(["pending", "failed"])).values(status="pending", next_attempt_at=now_utc()))
    if not claimed.rowcount:
        raise HTTPException(409, "Delivery is already being processed")
    db.commit()
    return {"status": "queued", "event_id": delivery.event_id}


@router.post("/api/integrations/dispatch")
def dispatch(db: Db, user: Owner, sender=Depends(get_webhook_sender)):
    # Process only this owner's queued destinations; small synchronous review/dev batch.
    webhooks.recover_expired(db)
    ids = db.scalars(select(WebhookDelivery.id).join(WebhookEndpoint).where(
        WebhookEndpoint.owner_id == user.id, WebhookDelivery.status == "pending",
        WebhookDelivery.next_attempt_at <= now_utc(),
    ).order_by(WebhookDelivery.id).limit(5)).all()
    return {"processed": sum(webhooks.deliver(db, i, sender) for i in ids)}


def external_lead(db: Session, lead_id: int) -> Lead:
    lead = db.get(Lead, lead_id)
    if lead is None or lead.is_demo:
        raise HTTPException(404, "Lead not found")
    return lead


def begin_request(db: Session, key: IntegrationKey, token: str, request: Request, payload):
    fingerprint = hashlib.sha256(json.dumps({"method": request.method, "path": request.url.path,
        "body": payload.model_dump(mode="json")}, sort_keys=True).encode()).hexdigest()
    existing = db.scalar(select(IntegrationRequest).where(IntegrationRequest.key_id == key.id, IntegrationRequest.token == token))
    if existing:
        if existing.fingerprint != fingerprint:
            raise HTTPException(409, "Idempotency key already used for another request")
        return existing, False
    row = IntegrationRequest(key_id=key.id, token=token, fingerprint=fingerprint)
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Request is already being processed; retry with the same key") from None
    return row, True


def finish_request(db: Session, row: IntegrationRequest, result: dict, status_code: int = 200):
    row.response = result
    row.status_code = status_code
    db.commit()
    return result


@router.get("/api/v1/leads", response_model=list[LeadRead])
def external_list(db: Db, key: Key, after_id: int = 0, limit: int = 50):
    require_scope(key, "leads:read")
    return db.scalars(select(Lead).where(Lead.is_demo.is_(False), Lead.id > after_id).order_by(Lead.id).limit(max(1, min(limit, 100)))).all()


@router.get("/api/v1/leads/{lead_id}", response_model=LeadDetailRead)
def external_detail(lead_id: int, db: Db, key: Key):
    require_scope(key, "leads:read")
    # Reuse the existing detail presentation and shared-workspace authorization.
    from .main import get_lead
    external_lead(db, lead_id)
    return get_lead(lead_id, db, db.get(User, key.owner_id))


@router.post("/api/v1/leads", status_code=201, response_model=LeadRead)
def external_create(payload: ExternalLeadCreate, token: Idempotency, request: Request, db: Db, key: Key,
                    provider: AIProvider = Depends(get_ai_provider), email_provider: EmailProvider = Depends(get_email_provider)):
    require_scope(key, "leads:write")
    row, fresh = begin_request(db, key, token, request, payload)
    if not fresh:
        return row.response
    # Stable UUID namespaced to the credential; cannot collide with a public inquiry.
    inquiry_key = str(uuid5(NAMESPACE_URL, f"tavo-integration:{key.id}:{token}"))
    # The shared model requires a v4 UUID: derive the version bits while retaining entropy.
    from uuid import UUID
    inquiry_key = str(UUID(inquiry_key, version=4))
    public = LeadCreate(**payload.model_dump(), inquiry_key=inquiry_key)
    lead, created = leads.create_lead(db, public, commit=False, actor=f"integration:{key.id}")
    # Save the creation snapshot and the outbox atomically; retries always return it.
    result = finish_request(db, row, LeadRead.model_validate(lead).model_dump(mode="json"), 201)
    if created:
        leads.process_new_lead(db, lead, provider, email_provider)
    return result


@router.patch("/api/v1/leads/{lead_id}", response_model=LeadRead)
def external_update(lead_id: int, payload: LeadUpdate, token: Idempotency, request: Request, db: Db, key: Key):
    require_scope(key, "leads:write")
    lead = external_lead(db, lead_id)
    row, fresh = begin_request(db, key, token, request, payload)
    if not fresh:
        return row.response
    try:
        leads.apply_update(db, lead, payload, commit=False, actor=f"integration:{key.id}")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return finish_request(db, row, LeadRead.model_validate(lead).model_dump(mode="json"))


@router.patch("/api/v1/leads/{lead_id}/stage", response_model=LeadRead)
def external_stage(lead_id: int, payload: StatusChange, token: Idempotency, request: Request, db: Db, key: Key):
    require_scope(key, "leads:write")
    lead = external_lead(db, lead_id)
    row, fresh = begin_request(db, key, token, request, payload)
    if not fresh:
        return row.response
    leads.apply_status(db, lead, payload.stage, commit=False)
    return finish_request(db, row, LeadRead.model_validate(lead).model_dump(mode="json"))


@router.post("/api/v1/leads/{lead_id}/notes", status_code=201)
def external_note(lead_id: int, payload: NoteCreate, token: Idempotency, request: Request, db: Db, key: Key):
    require_scope(key, "leads:write")
    lead = external_lead(db, lead_id)
    row, fresh = begin_request(db, key, token, request, payload)
    if not fresh:
        return row.response
    note = Activity(lead_id=lead.id, type="note_added", status="completed", content={"note": payload.note, "actor": f"integration:{key.id}"})
    db.add(note)
    db.flush()
    return finish_request(db, row, {"id": note.id, "lead_id": lead.id, "note": payload.note}, 201)
