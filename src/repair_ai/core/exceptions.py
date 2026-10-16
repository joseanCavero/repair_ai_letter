"""Application-level exceptions.

Kept in ``core`` so that the LLM, service, and API layers can share them
without creating import cycles.
"""


class GenerationError(Exception):
    """Base class for generation-related failures."""


class GenerationProviderError(GenerationError):
    """The upstream model provider failed or returned an unusable result."""


class OutputValidationError(GenerationError):
    """Deterministic output validation rejected the generated draft."""

    def __init__(self, violations: list[str]):
        self.violations = violations
        super().__init__("Output validation failed: " + "; ".join(violations))
