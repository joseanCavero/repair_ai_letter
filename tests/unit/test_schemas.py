"""Schema constraint tests. No LLM is involved."""

import pytest
from pydantic import ValidationError

from repair_ai.schemas.generation import GenerationStatus, LLMGenerationOutput
from repair_ai.schemas.repair import RepairDescriptionRequest
from tests.conftest import sample_payload


def test_valid_request_is_accepted():
    request = RepairDescriptionRequest(**sample_payload())
    assert request.language == "en"
    assert request.request_id is not None
    assert len(request.materials) == 1


def test_extra_fields_are_rejected():
    payload = sample_payload() | {"unexpected_field": "nope"}
    with pytest.raises(ValidationError):
        RepairDescriptionRequest(**payload)


def test_unsupported_language_is_rejected():
    payload = sample_payload() | {"language": "fr"}
    with pytest.raises(ValidationError):
        RepairDescriptionRequest(**payload)


@pytest.mark.parametrize("language", ["en", "de", "es"])
def test_supported_languages_are_accepted(language):
    payload = sample_payload() | {"language": language}
    assert RepairDescriptionRequest(**payload).language == language


@pytest.mark.parametrize("quantity", [0, -1, float("inf"), float("nan")])
def test_invalid_quantities_are_rejected(quantity):
    payload = sample_payload()
    payload["materials"][0]["quantity"] = quantity
    with pytest.raises(ValidationError):
        RepairDescriptionRequest(**payload)


def test_empty_description_is_rejected():
    payload = sample_payload()
    payload["findings"][0]["description"] = ""
    with pytest.raises(ValidationError):
        RepairDescriptionRequest(**payload)


def test_oversized_list_is_rejected():
    payload = sample_payload()
    payload["findings"] = [{"description": f"finding {i}"} for i in range(51)]
    with pytest.raises(ValidationError):
        RepairDescriptionRequest(**payload)


def test_empty_lists_are_allowed_by_schema():
    payload = sample_payload() | {"findings": [], "operations": [], "materials": []}
    request = RepairDescriptionRequest(**payload)
    assert request.findings == []


class TestLLMGenerationOutputConsistency:
    def test_generated_without_description_is_rejected(self):
        with pytest.raises(ValidationError):
            LLMGenerationOutput(status=GenerationStatus.GENERATED)

    def test_generated_with_blank_description_is_rejected(self):
        with pytest.raises(ValidationError):
            LLMGenerationOutput(
                status=GenerationStatus.GENERATED, description="   "
            )

    def test_generated_with_reason_is_rejected(self):
        with pytest.raises(ValidationError):
            LLMGenerationOutput(
                status=GenerationStatus.GENERATED,
                description="Valid description.",
                reason="should not be here",
            )

    def test_generated_with_description_is_accepted(self):
        output = LLMGenerationOutput(
            status=GenerationStatus.GENERATED, description="Valid description."
        )
        assert output.description == "Valid description."

    def test_insufficient_data_with_description_is_rejected(self):
        with pytest.raises(ValidationError):
            LLMGenerationOutput(
                status=GenerationStatus.INSUFFICIENT_DATA,
                description="should not be here",
                reason="no facts",
            )

    def test_insufficient_data_without_reason_is_rejected(self):
        with pytest.raises(ValidationError):
            LLMGenerationOutput(status=GenerationStatus.INSUFFICIENT_DATA)

    def test_insufficient_data_with_reason_is_accepted(self):
        output = LLMGenerationOutput(
            status=GenerationStatus.INSUFFICIENT_DATA, reason="no facts"
        )
        assert output.reason == "no facts"
