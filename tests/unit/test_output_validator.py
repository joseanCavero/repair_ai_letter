"""Deterministic output validator tests."""

import pytest

from repair_ai.schemas.generation import GenerationStatus, LLMGenerationOutput
from repair_ai.validation.output_validator import RepairOutputValidator

validator = RepairOutputValidator()


def generated(description: str) -> LLMGenerationOutput:
    return LLMGenerationOutput(
        status=GenerationStatus.GENERATED, description=description
    )


def test_clean_output_passes(sample_request):
    output = generated(
        "We propose to replace the worn bearing. The work uses material "
        "MAT-123 (quantity 2 pc) under operation OP-10, as described in "
        "finding F-01."
    )
    assert validator.validate(sample_request, output).passed


def test_abstention_is_not_checked(sample_request):
    output = LLMGenerationOutput(
        status=GenerationStatus.INSUFFICIENT_DATA, reason="not enough facts"
    )
    assert validator.validate(sample_request, output).passed


@pytest.mark.parametrize(
    "phrase",
    [
        "This repair comes with a two-year warranty.",
        "The repair is fully guaranteed.",
        "Die Reparatur ist garantiert.",  # de: guaranteed
        "Wir übernehmen die Gewährleistung.",  # de: warranty
        "La reparación está garantizada.",  # es: guaranteed
        "Incluye garantía de dos años.",  # es: warranty
    ],
)
def test_prohibited_claims_are_rejected(sample_request, phrase):
    result = validator.validate(sample_request, generated(phrase))
    assert not result.passed
    assert any("warranty/guarantee" in v for v in result.violations)


def test_invented_identifier_is_rejected(sample_request):
    output = generated(
        "We propose to replace the bearing using material MAT-999 "
        "(quantity 2 pc)."
    )
    result = validator.validate(sample_request, output)
    assert not result.passed
    assert any("MAT-999" in v for v in result.violations)


def test_source_identifiers_are_accepted(sample_request):
    output = generated(
        "Finding F-01 leads to operation OP-10 using material MAT-123 "
        "(quantity 2 pc)."
    )
    assert validator.validate(sample_request, output).passed


def test_quantity_with_unit_is_not_mistaken_for_identifier(sample_request):
    output = generated(
        "We will install 2pcs of the bearing using material MAT-123."
    )
    assert validator.validate(sample_request, output).passed


def test_wrong_language_is_rejected(sample_request):
    output = generated(
        "Wir schlagen vor, das verschlissene Lager an Ihrer Ausrüstung zu "
        "ersetzen. Die Arbeiten umfassen das Material MAT-123."
    )
    result = validator.validate(sample_request, output)
    assert not result.passed
    assert any("language" in v.lower() for v in result.violations)
