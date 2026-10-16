"""API integration tests using FastAPI's test client.

The real LangChain pipeline is replaced with a deterministic fake through
dependency overrides; no live LLM is called.
"""

import pytest
from fastapi.testclient import TestClient

from repair_ai.api.endpoints.repair_descriptions import (
    get_repair_description_service,
)
from repair_ai.core.config import Settings
from repair_ai.core.exceptions import GenerationProviderError
from repair_ai.main import create_app
from repair_ai.schemas.generation import GenerationStatus, LLMGenerationOutput
from repair_ai.services.repair_description_service import RepairDescriptionService
from repair_ai.validation.output_validator import RepairOutputValidator
from tests.conftest import sample_payload


class FakeGenerator:
    def __init__(self, output: LLMGenerationOutput | None = None, exc=None):
        self._output = output
        self._exc = exc
        self.calls: list[dict] = []

    def generate(self, **kwargs) -> LLMGenerationOutput:
        self.calls.append(kwargs)
        if self._exc is not None:
            raise self._exc
        return self._output


GENERATED_OK = LLMGenerationOutput(
    status=GenerationStatus.GENERATED,
    description=(
        "We propose to replace the worn bearing on your equipment. "
        "The work includes material MAT-123 (quantity 2 pc) as part of "
        "operation OP-10."
    ),
)


def make_client(generator: FakeGenerator) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_repair_description_service] = (
        lambda: RepairDescriptionService(
            generator=generator,
            validator=RepairOutputValidator(),
            settings=Settings(),
        )
    )
    return TestClient(app)


@pytest.fixture
def client() -> TestClient:
    return make_client(FakeGenerator(output=GENERATED_OK))


URL = "/v1/repair-descriptions"


def test_generated_response_shape(client):
    response = client.post(URL, json=sample_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "generated"
    assert body["description"] == GENERATED_OK.description
    assert body["request_id"]
    assert body["generation"]["validation_status"] == "passed"
    assert body["generation"]["model_version"]
    assert body["generation"]["prompt_version"]


def test_all_empty_lists_return_structured_insufficient_data():
    generator = FakeGenerator(output=GENERATED_OK)
    client = make_client(generator)
    payload = sample_payload() | {"findings": [], "operations": [], "materials": []}

    response = client.post(URL, json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "insufficient_data"
    assert body["description"] is None
    assert body["reason"]
    assert body["generation"]["validation_status"] == "not_applicable"
    assert generator.calls == []


def test_llm_abstention_is_returned_as_business_outcome():
    abstention = LLMGenerationOutput(
        status=GenerationStatus.INSUFFICIENT_DATA,
        reason="The supplied facts do not describe any damage.",
    )
    client = make_client(FakeGenerator(output=abstention))

    response = client.post(URL, json=sample_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "insufficient_data"
    assert body["reason"] == abstention.reason


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.update({"language": "fr"}),
        lambda p: p["materials"][0].update({"quantity": -5}),
        lambda p: p.update({"surprise": True}),
        lambda p: p.pop("repair_type"),
    ],
)
def test_malformed_requests_return_422(client, mutate):
    payload = sample_payload()
    mutate(payload)
    response = client.post(URL, json=payload)
    assert response.status_code == 422


def test_provider_failure_maps_to_502_with_sanitized_detail():
    client = make_client(
        FakeGenerator(exc=GenerationProviderError("provider down"))
    )
    response = client.post(URL, json=sample_payload())

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert "provider down" not in detail
    assert "unavailable" in detail


def test_validation_failure_maps_to_500_and_discards_draft():
    bad = LLMGenerationOutput(
        status=GenerationStatus.GENERATED,
        description="All repairs are guaranteed forever.",
    )
    client = make_client(FakeGenerator(output=bad))
    response = client.post(URL, json=sample_payload())

    assert response.status_code == 500
    body = response.json()
    assert "guaranteed forever" not in str(body)
