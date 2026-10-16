"""Deterministic, repair-specific output checks.

Pydantic proves the output has the right shape; it does not prove the
generated text is factually supported. These checks cover objective,
explainable constraints:

1. Prohibited claims (warranties/guarantees) in en/de/es.
2. Invented technical identifiers (part-number-like tokens that do not
   appear in the source facts).
3. Language of the generated text vs. the requested language.

Semantic factual support remains the job of human review and the separate
evaluation framework.
"""

import logging
import re
from dataclasses import dataclass, field

from langdetect import DetectorFactory, LangDetectException, detect

from repair_ai.schemas.generation import GenerationStatus, LLMGenerationOutput
from repair_ai.schemas.repair import RepairDescriptionRequest

logger = logging.getLogger(__name__)

# Make language detection reproducible in tests and across runs.
DetectorFactory.seed = 0

#: Warranty/guarantee stems in the supported languages. Substring stems are
#: distinctive enough to catch inflected forms (warranty/warranted,
#: garantiert/Garantie, garantizado/garantía, ...).
_PROHIBITED_CLAIMS = re.compile(
    r"\b\w*(warrant|guarantee|garantie|garantiz|garantía|gewährleist)\w*\b",
    re.IGNORECASE,
)

#: Candidate identifier tokens: hyphen/slash/dot-separated alphanumeric
#: groups, e.g. "MAT-123", "F-01", "6204-2RS", "P-100".
_TOKEN = re.compile(r"[A-Za-z0-9]+(?:[-_./][A-Za-z0-9]+)*")

#: Tokens like "1.5kg", "2pcs", "10mm" are quantity+unit, not identifiers.
_QUANTITY_LIKE = re.compile(r"^\d+([.,]\d+)?[a-zA-Z]{1,4}$")

_MIN_IDENTIFIER_LENGTH = 4


@dataclass
class ValidationResult:
    violations: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.violations


class RepairOutputValidator:
    """Runs deterministic checks on a generated draft against its source."""

    def validate(
        self,
        request: RepairDescriptionRequest,
        output: LLMGenerationOutput,
    ) -> ValidationResult:
        if output.status != GenerationStatus.GENERATED or not output.description:
            # Nothing to check on an abstention; structural consistency is
            # already enforced by the Pydantic model.
            return ValidationResult()

        description = output.description
        violations: list[str] = []
        violations.extend(self._check_prohibited_claims(description))
        violations.extend(self._check_invented_identifiers(request, description))
        violations.extend(self._check_language(request, description))
        return ValidationResult(violations=violations)

    @staticmethod
    def _check_prohibited_claims(description: str) -> list[str]:
        matches = {m.group(0) for m in _PROHIBITED_CLAIMS.finditer(description)}
        if matches:
            return [
                "Prohibited warranty/guarantee claim(s) found: "
                + ", ".join(sorted(matches))
            ]
        return []

    @staticmethod
    def _check_invented_identifiers(
        request: RepairDescriptionRequest, description: str
    ) -> list[str]:
        allowed = {
            m.material_id
            for m in request.materials
            if m.material_id is not None
        }
        allowed |= {f.code for f in request.findings if f.code is not None}
        allowed |= {o.code for o in request.operations if o.code is not None}

        candidates = set()
        for match in _TOKEN.finditer(description):
            token = match.group(0).strip(".,;:)")
            has_letter = any(c.isalpha() for c in token)
            has_digit = any(c.isdigit() for c in token)
            if (
                has_letter
                and has_digit
                and len(token) >= _MIN_IDENTIFIER_LENGTH
                and not _QUANTITY_LIKE.match(token)
            ):
                candidates.add(token)

        invented = sorted(c for c in candidates if c not in allowed)
        if invented:
            return [
                "Identifier(s) not present in the source facts: "
                + ", ".join(invented)
            ]
        return []

    @staticmethod
    def _check_language(
        request: RepairDescriptionRequest, description: str
    ) -> list[str]:
        try:
            detected = detect(description)
        except LangDetectException:
            logger.warning("Language detection failed", exc_info=True)
            return ["Language of the description could not be determined."]
        if detected != request.language:
            return [
                f"Description language '{detected}' does not match the "
                f"requested language '{request.language}'."
            ]
        return []
