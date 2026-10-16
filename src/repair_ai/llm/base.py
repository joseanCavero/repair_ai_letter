"""Generation interface.

The application service depends on this protocol rather than on a concrete
LangChain/provider implementation, so providers can be swapped and tests can
use deterministic fakes.
"""

from typing import Protocol

from repair_ai.schemas.generation import LLMGenerationOutput


class RepairDescriptionGenerator(Protocol):
    """Produces a structured repair description from prepared repair facts."""

    def generate(
        self,
        *,
        facts: str,
        language: str,
        repair_type: str,
        style: str,
    ) -> LLMGenerationOutput:
        """Generate a description.

        :param facts: Labeled, serialized repair facts (untrusted data).
        :param language: Requested output language code (e.g. ``en``).
        :param repair_type: Repair type enum value.
        :param style: Description style enum value.
        """
        ...
