import pytest

from app.ai import AIProviderError, get_ai_provider
from app.main import app


class FakeProvider:
    model = "test/mock-model"

    def __init__(self):
        self.calls = []
        self.fail = False
        self.structured_result = {
            "service_category": "Deep Cleaning",
            "priority": "normal",
            "summary": ["Customer requested cleaning"],
            "matched_priority_rules": [],
            "classification_rationale": "No listed high-priority criteria are present.",
        }
        self.text_result = "Hi, thanks for contacting us. We would be glad to discuss your request."

    def structured(self, system, user, schema):
        self.calls.append(("structured", system, user, schema))
        if self.fail:
            raise AIProviderError("Mock failure")
        return self.structured_result

    def text(self, system, user):
        self.calls.append(("text", system, user))
        if self.fail:
            raise AIProviderError("Mock failure")
        return self.text_result


@pytest.fixture(autouse=True)
def fake_provider():
    provider = FakeProvider()
    app.dependency_overrides[get_ai_provider] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_ai_provider, None)
