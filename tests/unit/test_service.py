"""Application service tests with a deterministic fake generator."""

import pytest

from repair_ai.core.config import Settings
from repair_ai.core.exceptions import GenerationProviderError, OutputValidationError
from repair_ai.schemas.generation import (
    GenerationStatus,
    LLMGenerationOutput,
    ValidationStatus,
)
from repair_ai.services.repair_description_service import RepairDescriptionService
from repair_ai.validation.output_validator import RepairOutputValidator


class FakeGenerator:
    """Deterministic stand-in for the LangChain pipeline."""

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


def make_service(generator: FakeGenerator) -> RepairDescriptionService:
    return RepairDescriptionService(
        generator=generator,
        validator=RepairOutputValidator(),
        settings=Settings(),
    )


def test_abstains_without_calling_the_llm_when_all_lists_empty(sample_request):
    request = sample_request.model_copy(
        update={"findings": [], "operations": [], "materials": []}
    )
    generator = FakeGenerator(output=GENERATED_OK)
    response = make_service(generator).generate_description(request)

    assert response.status == GenerationStatus.INSUFFICIENT_DATA
    assert response.reason
    assert response.description is None
    assert response.generation.validation_status == ValidationStatus.NOT_APPLICABLE
    assert generator.calls == []


def test_happy_path_returns_generated_text_and_metadata(sample_request):
    generator = FakeGenerator(output=GENERATED_OK)
    response = make_service(generator).generate_description(sample_request)

    assert response.status == GenerationStatus.GENERATED
    assert response.description == GENERATED_OK.description
    assert response.request_id == str(sample_request.request_id)
    assert response.generation.validation_status == ValidationStatus.PASSED
    assert response.generation.model_version
    assert response.generation.prompt_version
    assert generator.calls[0]["language"] == "en"
    assert generator.calls[0]["repair_type"] == "component_replacement"


def test_facts_serialization_is_labeled_and_preserves_identifiers(sample_request):
    generator = FakeGenerator(output=GENERATED_OK)
    make_service(generator).generate_description(sample_request)

    facts = generator.calls[0]["facts"]
    assert "Equipment type: Hydraulic pump" in facts
    assert "[F-01] Bearing wear detected" in facts
    assert "[OP-10] Replace bearing (status: proposed)" in facts
    assert "[MAT-123] Bearing 6204 (quantity: 2 pc)" in facts


def test_invalid_output_raises_and_never_returns_text(sample_request):
    bad_output = LLMGenerationOutput(
        status=GenerationStatus.GENERATED,
        description="This repair is fully guaranteed for life.",
    )
    service = make_service(FakeGenerator(output=bad_output))

    with pytest.raises(OutputValidationError) as exc_info:
        service.generate_description(sample_request)
    assert exc_info.value.violations


def test_provider_error_propagates(sample_request):
    service = make_service(
        FakeGenerator(exc=GenerationProviderError("provider down"))
    )
    with pytest.raises(GenerationProviderError):
        service.generate_description(sample_request)
