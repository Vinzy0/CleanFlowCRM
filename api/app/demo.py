"""Fixed fake inquiries for the public demo.

Every scenario is synthetic: example.com addresses and 555 phone numbers only.
Nothing here invents a parallel pipeline — scenarios are turned into the same
lead payload the public inquiry form submits, so the demo travels the real code
path. The small result cache exists solely to avoid paying for an identical AI
classification twice on the same day.
"""

import threading
from dataclasses import dataclass
from datetime import date, timedelta
from uuid import uuid4

from .business import BUSINESS


@dataclass(frozen=True)
class Scenario:
    slug: str
    label: str
    name: str
    email: str
    phone: str
    service_type: str
    property_type: str
    days_ahead: int
    message: str


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        slug="standard-house",
        label="Routine house cleaning",
        name="Ava Mitchell",
        email="ava.mitchell@example.com",
        phone="+1 555 0104",
        service_type="Standard House Cleaning",
        property_type="House",
        days_ahead=5,
        message=(
            "Hello, we would like a regular clean for our three-bedroom house next week. "
            "Nothing unusual, just floors, dusting and the kitchen."
        ),
    ),
    Scenario(
        slug="deep-clean",
        label="Deep cleaning before guests",
        name="Priya Raman",
        email="priya.raman@example.com",
        phone="+1 555 0117",
        service_type="Deep Cleaning",
        property_type="House",
        days_ahead=3,
        message=(
            "We are hosting family this weekend and the kitchen and bathrooms need a deep clean. "
            "Oven, grout and inside the cabinets if possible."
        ),
    ),
    Scenario(
        slug="urgent-move-out",
        label="Urgent move-out deadline",
        name="Daniel Ortiz",
        email="daniel.ortiz@example.com",
        phone="+1 555 0132",
        service_type="Move-In / Move-Out",
        property_type="Apartment",
        days_ahead=1,
        message=(
            "We hand the keys back in two days and need the apartment cleaned for the inspection. "
            "The deadline is firm, so please confirm as soon as you can."
        ),
    ),
    Scenario(
        slug="commercial-office",
        label="Commercial office contract",
        name="Grace Lim",
        email="grace.lim@example.com",
        phone="+1 555 0148",
        service_type="Commercial Cleaning",
        property_type="Office",
        days_ahead=2,
        message=(
            "Our office has forty desks and two meeting rooms. We need after-hours cleaning on a "
            "recurring basis and would like a quote this week."
        ),
    ),
    Scenario(
        slug="future-booking",
        label="Low-priority future booking",
        name="Noah Bennett",
        email="noah.bennett@example.com",
        phone="+1 555 0159",
        service_type="Standard House Cleaning",
        property_type="Apartment",
        days_ahead=30,
        message=(
            "Planning ahead: we would like a clean in about a month, no rush at all. "
            "Weekends work best for us."
        ),
    ),
    Scenario(
        slug="immediate-response",
        label="Customer asking for an immediate reply",
        name="Sofia Delgado",
        email="sofia.delgado@example.com",
        phone="+1 555 0163",
        service_type="Deep Cleaning",
        property_type="House",
        days_ahead=7,
        message=(
            "Please call or reply today if you have availability for a deep clean. "
            "I am comparing two companies and would like an answer quickly."
        ),
    ),
)

# Slug -> stage applied through the ordinary status-change path when seeding.
SEED_STAGES: tuple[tuple[str, str], ...] = (
    ("standard-house", "Completed"),
    ("commercial-office", "Contacted"),
    ("urgent-move-out", "Booked"),
    ("deep-clean", "New"),
    ("future-booking", "New"),
)

_cache: dict[tuple[str, str], dict] = {}
_cache_lock = threading.Lock()


def scenarios_by_slug() -> dict[str, Scenario]:
    return {scenario.slug: scenario for scenario in SCENARIOS}


def scenario_for_rotation(existing_demo_leads: int) -> Scenario:
    """Rotate through the fixed pool so repeated clicks show different requests."""
    return SCENARIOS[existing_demo_leads % len(SCENARIOS)]


def preferred_date(scenario: Scenario) -> date:
    return date.today() + timedelta(days=scenario.days_ahead)


def inquiry_payload(scenario: Scenario, inquiry_key: str | None = None) -> dict:
    """Build the same payload shape the public inquiry form sends."""
    return {
        "inquiry_key": inquiry_key or str(uuid4()),
        "name": scenario.name,
        "email": scenario.email,
        "phone": scenario.phone,
        "service_type": scenario.service_type,
        "property_type": scenario.property_type,
        "preferred_date": preferred_date(scenario).isoformat(),
        "message": scenario.message,
    }


def cached_classification(scenario: Scenario) -> dict | None:
    """Return a stored result for an identical inquiry dated the same day."""
    with _cache_lock:
        return _cache.get(_cache_key(scenario))


def remember_classification(scenario: Scenario, result: dict) -> None:
    with _cache_lock:
        _cache[_cache_key(scenario)] = result


def clear_cached_classifications() -> None:
    """Drop reused results (tests, and any deliberate cache reset)."""
    with _cache_lock:
        _cache.clear()


def _cache_key(scenario: Scenario) -> tuple[str, str]:
    return (scenario.slug, preferred_date(scenario).isoformat())


def _validate_scenarios() -> None:
    slugs = [scenario.slug for scenario in SCENARIOS]
    if len(slugs) != len(set(slugs)):
        raise RuntimeError("Demo scenarios must have unique slugs")
    for scenario in SCENARIOS:
        if scenario.service_type not in BUSINESS["services"]:
            raise RuntimeError(f"Demo scenario {scenario.slug} uses an unknown service")
        if scenario.property_type not in BUSINESS["property_types"]:
            raise RuntimeError(f"Demo scenario {scenario.slug} uses an unknown property type")
        if not scenario.email.endswith("@example.com"):
            raise RuntimeError(f"Demo scenario {scenario.slug} must use a synthetic address")
    for slug, stage in SEED_STAGES:
        if slug not in slugs:
            raise RuntimeError(f"Seed data references unknown scenario {slug}")
        if stage not in BUSINESS["pipeline_stages"]:
            raise RuntimeError(f"Seed data references unknown stage {stage}")


_validate_scenarios()
