"""Application service coordinating the repair description use case.

Responsibilities:
1. Apply deterministic business checks (insufficient facts).
2. Prepare a labeled, factual representation of the input.
3. Invoke the generation pipeline (behind an injectable interface).
4. Validate the output with deterministic checks.
5. Map the result to the API response with trusted metadata.

The service does not know whether its caller is Postman, SAP, or a test.
"""

import logging

from repair_ai.core.config import Settings
from repair_ai.core.exceptions import OutputValidationError
from repair_ai.llm.base import RepairDescriptionGenerator
from repair_ai.schemas.generation import (
    GenerationMetadata,
    GenerationStatus,
    RepairDescriptionResponse,
    ValidationStatus,
)
from repair_ai.schemas.repair import RepairDescriptionRequest
from repair_ai.validation.output_validator import RepairOutputValidator

logger = logging.getLogger(__name__)

_NO_FACTS_REASON = (
    "No findings, operations, or materials were supplied; a meaningful "
    "description cannot be generated."
)


class RepairDescriptionService:
    def __init__(
        self,
        generator: RepairDescriptionGenerator,
        validator: RepairOutputValidator,
        settings: Settings,
    ):
        self._generator = generator
        self._validator = validator
        self._settings = settings

    def generate_description(
        self, request: RepairDescriptionRequest
    ) -> RepairDescriptionResponse:
        if self._has_no_facts(request):
            logger.info(
                "Request %s: no repair facts supplied, abstaining",
                request.request_id,
            )
            return RepairDescriptionResponse(
                request_id=str(request.request_id),
                status=GenerationStatus.INSUFFICIENT_DATA,
                reason=_NO_FACTS_REASON,
                generation=self._metadata(ValidationStatus.NOT_APPLICABLE),
            )

        facts = self._serialize_facts(request)
        output = self._generator.generate(
            facts=facts,
            language=request.language,
            repair_type=request.repair_type.value,
            style=request.style.value,
        )

        result = self._validator.validate(request, output)
        if not result.passed:
            logger.warning(
                "Request %s: output validation failed: %s",
                request.request_id,
                result.violations,
            )
            raise OutputValidationError(result.violations)

        return RepairDescriptionResponse(
            request_id=str(request.request_id),
            status=output.status,
            description=output.description,
            reason=output.reason,
            generation=self._metadata(
                ValidationStatus.PASSED
                if output.status == GenerationStatus.GENERATED
                else ValidationStatus.NOT_APPLICABLE
            ),
        )

    def _metadata(self, validation_status: ValidationStatus) -> GenerationMetadata:
        return GenerationMetadata(
            model_version=self._settings.model_name,
            prompt_version=self._settings.prompt_version,
            validation_status=validation_status,
        )

    @staticmethod
    def _has_no_facts(request: RepairDescriptionRequest) -> bool:
        return (
            not request.findings
            and not request.operations
            and not request.materials
        )

    @staticmethod
    def _serialize_facts(request: RepairDescriptionRequest) -> str:
        """Render repair facts as a labeled plain-text block for the prompt.

        Codes and identifiers are kept verbatim; quantities render without a
        trailing ".0" for integral values.
        """
        lines: list[str] = [f"Equipment type: {request.equipment.type}"]

        if request.findings:
            lines.append("")
            lines.append("Findings:")
            for finding in request.findings:
                lines.append(f"- {_with_code(finding.code, finding.description)}")

        if request.operations:
            lines.append("")
            lines.append("Operations:")
            for op in request.operations:
                lines.append(
                    f"- {_with_code(op.code, op.description)} "
                    f"(status: {op.status.value})"
                )

        if request.materials:
            lines.append("")
            lines.append("Materials:")
            for mat in request.materials:
                lines.append(
                    f"- {_with_code(mat.material_id, mat.description)} "
                    f"(quantity: {_format_quantity(mat.quantity)} {mat.unit})"
                )

        return "\n".join(lines)


def _with_code(code: str | None, description: str) -> str:
    return f"[{code}] {description}" if code else description


def _format_quantity(quantity: float) -> str:
    return str(int(quantity)) if quantity.is_integer() else str(quantity)
