"""Lead operations shared by the CRM API and the demo workflows.

Routes stay thin; the workflows live here so the public inquiry form, the demo
simulation and the demo seed all travel the same code path.
"""

import hashlib
import json
import logging

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import demo, settings
from .ai import AIProvider, AIProviderError, Classification, classify
from .business import BUSINESS
from .email import EmailProvider
from .email_flow import notify_owner
from .models import AIAnalysis, Activity, Lead
from .schemas import LeadCreate

logger = logging.getLogger(__name__)


class InquiryConflict(Exception):
    """One inquiry key was reused for a different payload."""


def fingerprint_for(payload: LeadCreate) -> str:
    return hashlib.sha256(
        json.dumps(payload.model_dump(mode="json", exclude={"inquiry_key"}), sort_keys=True).encode()
    ).hexdigest()


def create_lead(
    db: Session,
    payload: LeadCreate,
    *,
    is_demo: bool = False,
    scenario_slug: str | None = None,
) -> tuple[Lead, bool]:
    """Insert the lead and its ``lead_created`` activity. No AI, no email.

    Returns ``(lead, created)`` so callers can tell a fresh lead from a retried
    submission that already exists.
    """
    fingerprint = fingerprint_for(payload)
    existing = db.scalar(select(Lead).where(Lead.inquiry_key == payload.inquiry_key))
    if existing is not None:
        return _existing_inquiry(existing, fingerprint), False
    lead = Lead(
        **payload.model_dump(),
        inquiry_fingerprint=fingerprint,
        is_demo=is_demo,
        demo_scenario=scenario_slug,
    )
    db.add(lead)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Lead).where(Lead.inquiry_key == payload.inquiry_key))
        if existing is not None:
            return _existing_inquiry(existing, fingerprint), False
        raise
    db.add(Activity(lead_id=lead.id, type="lead_created", status="completed", content={}))
    db.commit()
    db.refresh(lead)
    return lead, True


def _existing_inquiry(lead: Lead, fingerprint: str) -> Lead:
    if lead.inquiry_fingerprint != fingerprint:
        raise InquiryConflict("Inquiry key already used for a different request")
    return lead


def run_classification(
    db: Session,
    lead: Lead,
    provider: AIProvider,
    *,
    stored: Classification | None = None,
) -> Classification | None:
    """Store one AI analysis. Returns ``None`` when analysis is unavailable."""
    activity = Activity(lead_id=lead.id, type="ai_classified", status="pending", content={})
    db.add(activity)
    db.commit()
    try:
        result = stored if stored is not None else classify(lead, provider)
    except (AIProviderError, ValidationError):
        activity.status = "failed"
        activity.content = {"message": "AI analysis could not be completed. Retry from the lead page."}
        db.commit()
        return None
    db.add(AIAnalysis(
        lead_id=lead.id,
        service_category=result.service_category,
        priority=result.priority,
        summary="\n".join(f"• {item}" for item in result.summary),
        matched_priority_rules=result.matched_priority_rules,
        classification_rationale=result.classification_rationale,
        model=provider.model,
    ))
    lead.priority = result.priority
    activity.status = "completed"
    activity.content = {
        "category": result.service_category,
        "priority": result.priority,
        "reused": stored is not None,
    }
    db.commit()
    db.refresh(lead)
    return result


def classify_lead(
    db: Session, lead: Lead, provider: AIProvider, *, scenario: demo.Scenario | None = None
) -> Classification | None:
    """Classify a demo scenario using an already-stored identical result when possible."""
    stored = _reusable_classification(scenario)
    result = run_classification(db, lead, provider, stored=stored)
    if result is not None and scenario is not None:
        demo.remember_classification(scenario, result.model_dump())
    return result


def _reusable_classification(scenario: demo.Scenario | None) -> Classification | None:
    if scenario is None or not settings.flag("DEMO_REUSE_AI_RESULTS", True):
        return None
    cached = demo.cached_classification(scenario)
    if cached is None:
        return None
    try:
        return Classification.model_validate(cached)
    except ValidationError:  # a stale cache entry is simply ignored
        return None


def process_new_lead(
    db: Session, lead: Lead, provider: AIProvider, email_provider: EmailProvider, *, scenario: demo.Scenario | None = None
) -> bool:
    """Classify, then notify the owner. Neither step may break the lead."""
    classified = classify_lead(db, lead, provider, scenario=scenario) is not None
    notify_new_lead(db, lead, email_provider)
    return classified


def notify_new_lead(db: Session, lead: Lead, email_provider: EmailProvider) -> Activity | None:
    try:
        return notify_owner(db, lead, email_provider)
    except Exception:  # pragma: no cover - a notification must never fail a lead
        logger.warning("Owner notification failed unexpectedly for lead %s", lead.id, exc_info=True)
        return None


def apply_status(db: Session, lead: Lead, stage: str) -> Lead:
    if stage not in BUSINESS["pipeline_stages"]:
        raise ValueError("Unknown pipeline stage")
    previous = lead.pipeline_stage
    if previous != stage:
        lead.pipeline_stage = stage
        db.add(Activity(
            lead_id=lead.id,
            type="status_changed",
            status="completed",
            content={"from": previous, "to": stage},
        ))
        db.commit()
        db.refresh(lead)
    return lead


def lead_count(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(Lead)) or 0)


def demo_lead_count(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(Lead).where(Lead.is_demo.is_(True))) or 0)


def simulate_inquiry(db: Session, provider: AIProvider, email_provider: EmailProvider) -> Lead:
    """Create one fake inquiry through the ordinary lead pipeline."""
    scenario = demo.scenario_for_rotation(demo_lead_count(db))
    payload = LeadCreate(**demo.inquiry_payload(scenario))
    lead, _ = create_lead(db, payload, is_demo=True, scenario_slug=scenario.slug)
    process_new_lead(db, lead, provider, email_provider, scenario=scenario)
    return lead


def seed_demo_data(db: Session, provider: AIProvider, email_provider: EmailProvider) -> list[Lead]:
    seeded: list[Lead] = []
    by_slug = demo.scenarios_by_slug()
    for slug, stage in demo.SEED_STAGES:
        scenario = by_slug[slug]
        lead, _ = create_lead(db, LeadCreate(**demo.inquiry_payload(scenario)), is_demo=True, scenario_slug=slug)
        process_new_lead(db, lead, provider, email_provider, scenario=scenario)
        seeded.append(apply_status(db, lead, stage))
    return seeded


def reset_demo_data(db: Session, provider: AIProvider, email_provider: EmailProvider) -> dict:
    """Delete demo records only, then rebuild a populated demo state."""
    removed = db.scalars(select(Lead).where(Lead.is_demo.is_(True))).all()
    removed_ids = [lead.id for lead in removed]
    for lead in removed:  # ORM cascade removes the lead's analyses and activities
        db.delete(lead)
    db.commit()
    seeded = seed_demo_data(db, provider, email_provider)
    return {
        "deleted": len(removed_ids),
        "seeded": len(seeded),
        "lead_ids": [lead.id for lead in seeded],
    }
