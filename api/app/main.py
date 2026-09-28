import hashlib
import json

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import authenticate, create_token, current_user
from .business import BUSINESS
from .db import get_db
from .models import AIAnalysis, Activity, Lead, User
from .schemas import LeadCreate, LeadDetailRead, LeadRead, LeadUpdate, Login, StatusChange


app = FastAPI(title="CleanFlow CRM API")


@app.get("/api/config")
def public_config():
    return {
        "business_name": BUSINESS["business_name"],
        "services": BUSINESS["services"],
        "property_types": BUSINESS["property_types"],
        "pipeline_stages": BUSINESS["pipeline_stages"],
    }


@app.post("/api/auth/login")
def login(payload: Login, db: Session = Depends(get_db)):
    user = authenticate(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(401, "Incorrect email or password")
    return {"access_token": create_token(user), "token_type": "bearer"}


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "name": user.name}


@app.post("/api/leads", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
def create_lead(payload: LeadCreate, db: Session = Depends(get_db)):
    fingerprint = hashlib.sha256(
        json.dumps(payload.model_dump(mode="json", exclude={"inquiry_key"}), sort_keys=True).encode()
    ).hexdigest()
    existing = db.scalar(select(Lead).where(Lead.inquiry_key == payload.inquiry_key))
    if existing:
        return matching_lead(existing, fingerprint)
    lead = Lead(**payload.model_dump(), inquiry_fingerprint=fingerprint)
    db.add(lead)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Lead).where(Lead.inquiry_key == payload.inquiry_key))
        if existing:
            return matching_lead(existing, fingerprint)
        raise
    db.add(Activity(lead_id=lead.id, type="lead_created", status="completed", content={}))
    db.commit()
    db.refresh(lead)
    return lead


def matching_lead(lead: Lead, fingerprint: str) -> Lead:
    if lead.inquiry_fingerprint != fingerprint:
        raise HTTPException(409, "Inquiry key already used for a different request")
    return lead


@app.get("/api/leads", response_model=list[LeadRead])
def list_leads(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return db.scalars(select(Lead).order_by(Lead.created_at.desc(), Lead.id.desc())).all()


@app.get("/api/leads/{lead_id}", response_model=LeadDetailRead)
def get_lead(lead_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(404, "Lead not found")
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


@app.patch("/api/leads/{lead_id}/status", response_model=LeadRead)
def change_status(
    lead_id: int, payload: StatusChange, db: Session = Depends(get_db), _: User = Depends(current_user)
):
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(404, "Lead not found")
    previous = lead.pipeline_stage
    if previous != payload.stage:
        lead.pipeline_stage = payload.stage
        db.add(
            Activity(
                lead_id=lead.id,
                type="status_changed",
                status="completed",
                content={"from": previous, "to": payload.stage},
            )
        )
        db.commit()
        db.refresh(lead)
    return lead


@app.patch("/api/leads/{lead_id}", response_model=LeadRead)
def update_lead(
    lead_id: int, payload: LeadUpdate, db: Session = Depends(get_db), _: User = Depends(current_user)
):
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(404, "Lead not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is None:
            raise HTTPException(422, f"{field} cannot be null")
        setattr(lead, field, value)
    db.commit()
    db.refresh(lead)
    return lead


@app.delete("/api/leads/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lead(lead_id: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(404, "Lead not found")
    db.delete(lead)
    db.commit()
