from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from . import leads, ratelimit, settings, integrations
from .ai import AIProvider, AIProviderError, draft_reply, get_ai_provider
from .auth import authenticate, create_token, current_user
from .business import BUSINESS
from .db import get_db
from .email import EmailProvider, email_settings, get_email_provider
from .email_flow import CUSTOMER_REPLY, EmailOutcome, customer_reply_key, notify_owner, tracked_email
from .models import AIAnalysis, Activity, Lead, User
from .schemas import EmailSend, LeadCreate, LeadDetailRead, LeadRead, LeadUpdate, Login, StatusChange

def configure_cors(application: FastAPI, origin: str) -> None:
    if not origin:
        return
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.rstrip("/")],
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )


app = FastAPI(title="Tavo API")
app.include_router(integrations.router)
configure_cors(app, settings.env("FRONTEND_ORIGIN", "") or "")


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


def lead_or_404(db: Session, lead_id: int, user: User) -> Lead:
    lead = db.get(Lead, lead_id)
    if lead is None or (user.is_demo and not lead.is_demo):
        raise HTTPException(404, "Lead not found")
    return lead


def require_demo_mode() -> None:
    if not settings.flag("DEMO_MODE"):
        raise HTTPException(404, "Demo mode is not enabled")


def email_response(outcome: EmailOutcome) -> dict:
    """Turn a tracked email row into an API response with an honest status."""
    record = outcome.activity
    content = record.content or {}
    payload = {
        "status": record.status,
        "delivered": outcome.delivered and not bool(content.get("sandboxed")),
        "captured": outcome.delivered and bool(content.get("sandboxed")),
        "duplicate": outcome.duplicate,
        "email_type": content.get("email_type", ""),
        "to": content.get("to", ""),
        "delivered_to": content.get("delivered_to", ""),
        "redirected": bool(content.get("redirected")),
        "sandboxed": bool(content.get("sandboxed")),
        "message": content.get("message", ""),
        "activity_id": record.id,
    }
    if outcome.duplicate:
        payload["message"] = "This email was already sent; it has not been sent again."
        return payload
    if record.status == "pending":
        raise HTTPException(409, "This email is already being sent. Refresh the lead before retrying.")
    if outcome.delivered:
        return payload
    raise HTTPException(
        status_code=503 if content.get("reason") in {"not_configured", "disabled"} else 502,
        detail=content.get("message") or "Email could not be sent.",
    )


@app.get("/api/config")
def public_config():
    config = email_settings()
    return {
        "business_name": BUSINESS["business_name"],
        "services": BUSINESS["services"],
        "property_types": BUSINESS["property_types"],
        "pipeline_stages": BUSINESS["pipeline_stages"],
        "demo_mode": config.demo_mode,
        "email_delivery": config.delivery,
    }


@app.post("/api/auth/login")
def login(payload: Login, request: Request, db: Session = Depends(get_db)):
    ratelimit.enforce("login", request)
    user = authenticate(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(401, "Incorrect email or password")
    return {"access_token": create_token(user), "token_type": "bearer"}


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "name": user.name, "is_demo": user.is_demo}


@app.post("/api/leads", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
def create_lead(
    payload: LeadCreate,
    request: Request,
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
    email_provider: EmailProvider = Depends(get_email_provider),
):
    if settings.flag("DEMO_MODE"):
        raise HTTPException(403, "Public inquiries are disabled in demo mode. Use the synthetic demo workflow.")
    ratelimit.enforce("inquiry", request)
    try:
        lead, created = leads.create_lead(db, payload)
    except leads.InquiryConflict as exc:
        raise HTTPException(409, str(exc)) from None
    if created:
        # AI and email failures are recorded on the lead instead of blocking it.
        leads.process_new_lead(db, lead, provider, email_provider)
    return lead


@app.get("/api/leads", response_model=list[LeadRead])
def list_leads(db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(Lead).order_by(Lead.created_at.desc(), Lead.id.desc())
    if user.is_demo:
        query = query.where(Lead.is_demo.is_(True))
    return db.scalars(query).all()


@app.get("/api/leads/{lead_id}", response_model=LeadDetailRead)
def get_lead(lead_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    lead = lead_or_404(db, lead_id, user)
    activities = db.scalars(
        select(Activity).where(Activity.lead_id == lead_id).order_by(Activity.created_at, Activity.id)
    ).all()
    analysis = db.scalar(
        select(AIAnalysis)
        .where(AIAnalysis.lead_id == lead_id)
        .order_by(AIAnalysis.created_at.desc(), AIAnalysis.id.desc())
        .limit(1)
    )
    return {
        **LeadRead.model_validate(lead).model_dump(),
        "activities": activities,
        "analysis": analysis,
    }


@app.post("/api/leads/{lead_id}/classify")
def retry_classification(
    lead_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    provider: AIProvider = Depends(get_ai_provider),
):
    ratelimit.enforce("classify", request)
    lead = lead_or_404(db, lead_id, user)
    if leads.run_classification(db, lead, provider) is None:
        raise HTTPException(503, "AI analysis is unavailable; the lead was saved")
    return {"status": "completed"}


@app.post("/api/leads/{lead_id}/draft-reply")
def create_draft_reply(
    lead_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    provider: AIProvider = Depends(get_ai_provider),
):
    ratelimit.enforce("draft", request)
    lead = lead_or_404(db, lead_id, user)
    try:
        draft = draft_reply(lead, provider)
    except AIProviderError:
        db.add(Activity(
            lead_id=lead.id, type="reply_generated", status="failed",
            content={"message": "Draft generation failed. Please try again."},
        ))
        db.commit()
        raise HTTPException(503, "Draft generation is unavailable") from None
    # Generating a draft only stores text. Sending is a separate, owner-approved call.
    db.add(Activity(lead_id=lead.id, type="reply_generated", status="completed", content={"draft": draft}))
    db.commit()
    return {"draft": draft}


@app.post("/api/leads/{lead_id}/send-email")
def send_customer_reply(
    lead_id: int,
    payload: EmailSend,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    provider: EmailProvider = Depends(get_email_provider),
):
    """Send the owner-approved reply. The recipient is always the lead's address."""
    ratelimit.enforce("email", request)
    lead = lead_or_404(db, lead_id, user)
    config = email_settings()
    if config.demo_mode and not lead.is_demo:
        raise HTTPException(403, "The public demo can only email its own fake leads")
    outcome = tracked_email(
        db,
        lead=lead,
        email_type=CUSTOMER_REPLY,
        subject=payload.subject,
        body=payload.body,
        intended_recipient=lead.email,
        idempotency_key=customer_reply_key(lead.id, lead.email, payload.subject, payload.body),
        provider=provider,
    )
    return email_response(outcome)


@app.post("/api/leads/{lead_id}/notify-owner")
def retry_owner_notification(
    lead_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    provider: EmailProvider = Depends(get_email_provider),
):
    ratelimit.enforce("email", request)
    lead = lead_or_404(db, lead_id, user)
    if email_settings().demo_mode and not lead.is_demo:
        raise HTTPException(403, "The public demo can only email its own fake leads")
    outcome = notify_owner(db, lead, provider)
    if outcome is None:
        raise HTTPException(503, "Owner notification is unavailable")
    return email_response(outcome)


@app.patch("/api/leads/{lead_id}/status", response_model=LeadRead)
def change_status(
    lead_id: int, payload: StatusChange, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    return leads.apply_status(db, lead_or_404(db, lead_id, user), payload.stage)


@app.patch("/api/leads/{lead_id}", response_model=LeadRead)
def update_lead(
    lead_id: int, payload: LeadUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)
):
    lead = lead_or_404(db, lead_id, user)
    if user.is_demo:
        raise HTTPException(403, "Demo leads cannot be edited")
    try:
        return leads.apply_update(db, lead, payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@app.delete("/api/leads/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead(lead_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.is_demo:
        raise HTTPException(403, "Use demo reset to restore the workspace")
    db.delete(lead_or_404(db, lead_id, user))
    db.commit()


@app.post("/api/demo/simulate-inquiry", status_code=status.HTTP_201_CREATED)
def simulate_inquiry(
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
    provider: AIProvider = Depends(get_ai_provider),
    email_provider: EmailProvider = Depends(get_email_provider),
):
    require_demo_mode()
    ratelimit.enforce("simulate", request)
    lead = leads.simulate_inquiry(db, provider, email_provider)
    return {
        "lead_id": lead.id,
        "scenario": lead.demo_scenario or "",
        "synthetic": True,
    }


@app.post("/api/demo/reset")
def reset_demo(
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(current_user),
    provider: AIProvider = Depends(get_ai_provider),
    email_provider: EmailProvider = Depends(get_email_provider),
):
    require_demo_mode()
    ratelimit.enforce("reset", request)
    summary = leads.reset_demo_data(db, provider, email_provider)
    return {**summary, "synthetic": True}
