from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, JSON, String, Text
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
