from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .business import BUSINESS


class LeadCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    inquiry_key: str = Field(min_length=16, max_length=64)
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=32)
    service_type: str
    property_type: str
    preferred_date: date
    message: str = Field(min_length=10, max_length=5000)

    @field_validator("name")
    @classmethod
    def single_line_name(cls, value: str) -> str:
        if "\r" in value or "\n" in value:
            raise ValueError("Name must be one line")
        return value

    @field_validator("inquiry_key")
    @classmethod
    def valid_inquiry_key(cls, value: str) -> str:
        parsed = UUID(value)
        if parsed.version != 4:
            raise ValueError("Use a version 4 inquiry key")
        return str(parsed)

    @field_validator("service_type")
    @classmethod
    def known_service(cls, value: str) -> str:
        if value not in BUSINESS["services"]:
            raise ValueError("Choose a listed service")
        return value

    @field_validator("property_type")
    @classmethod
    def known_property(cls, value: str) -> str:
        if value not in BUSINESS["property_types"]:
            raise ValueError("Choose a listed property type")
        return value


class LeadUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, min_length=7, max_length=32)
    service_type: str | None = None
    property_type: str | None = None
    preferred_date: date | None = None
    message: str | None = Field(default=None, min_length=10, max_length=5000)

    @field_validator("name")
    @classmethod
    def single_line_name(cls, value: str | None) -> str | None:
        if value is not None and ("\r" in value or "\n" in value):
            raise ValueError("Name must be one line")
        return value

    @field_validator("service_type")
    @classmethod
    def known_service(cls, value: str | None) -> str | None:
        if value is not None and value not in BUSINESS["services"]:
            raise ValueError("Choose a listed service")
        return value

    @field_validator("property_type")
    @classmethod
    def known_property(cls, value: str | None) -> str | None:
        if value is not None and value not in BUSINESS["property_types"]:
            raise ValueError("Choose a listed property type")
        return value


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    phone: str
    service_type: str
    property_type: str
    preferred_date: date
    message: str
    pipeline_stage: str
    priority: str | None
    is_demo: bool = False
    created_at: datetime
    updated_at: datetime


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    status: str
    content: dict
    created_at: datetime


class AIAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    service_category: str
    priority: str
    summary: str
    matched_priority_rules: list[str]
    classification_rationale: str
    model: str
    created_at: datetime


class LeadDetailRead(LeadRead):
    activities: list[ActivityRead]
    analysis: AIAnalysisRead | None


class StatusChange(BaseModel):
    stage: str

    @field_validator("stage")
    @classmethod
    def known_stage(cls, value: str) -> str:
        if value not in BUSINESS["pipeline_stages"]:
            raise ValueError("Choose a listed pipeline stage")
        return value


class EmailSend(BaseModel):
    """An owner-approved customer reply.

    There is deliberately no recipient field: the backend always replies to the
    lead's own address, so a public visitor can never pick a target.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    subject: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=10, max_length=5000)

    @field_validator("subject")
    @classmethod
    def single_line_subject(cls, value: str) -> str:
        if "\r" in value or "\n" in value:
            raise ValueError("Subject must be one line")
        return value


class Login(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
