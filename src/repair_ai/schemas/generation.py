"""Output contracts for repair description generation.

Three distinct concepts:
- ``LLMGenerationOutput``: what the language model is asked to produce.
- ``GenerationMetadata``: trusted application metadata, never supplied by the model.
- ``RepairDescriptionResponse``: the public API response.
"""

from enum import StrEnum

from pydantic import Field, model_validator

from repair_ai.schemas.repair import RepairDataModel


class GenerationStatus(StrEnum):
    GENERATED = "generated"
    INSUFFICIENT_DATA = "insufficient_data"


class ValidationStatus(StrEnum):
    PASSED = "passed"
    NOT_APPLICABLE = "not_applicable"


class LLMGenerationOutput(RepairDataModel):
    """Structured output requested from the language model."""

    status: GenerationStatus
    description: str | None = Field(default=None, max_length=2000)
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_status_consistency(self):
        if self.status == GenerationStatus.GENERATED:
            if not self.description or not self.description.strip():
                raise ValueError("A generated response must include a description.")
            if self.reason is not None:
                raise ValueError("A generated response must not include a reason.")

        if self.status == GenerationStatus.INSUFFICIENT_DATA:
            if self.description is not None:
                raise ValueError(
                    "An insufficient-data response must not include a description."
                )
            if not self.reason or not self.reason.strip():
                raise ValueError(
                    "An insufficient-data response must include a reason."
                )

        return self


class GenerationMetadata(RepairDataModel):
    model_version: str
    prompt_version: str
    validation_status: ValidationStatus


class RepairDescriptionResponse(RepairDataModel):
    request_id: str
    status: GenerationStatus
    description: str | None = None
    reason: str | None = None
    generation: GenerationMetadata | None = None
