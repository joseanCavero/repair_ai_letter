"""LangChain pipeline for repair description generation.

The chain composes a versioned prompt with a chat model using LCEL and
requests structured output. It knows nothing about HTTP, FastAPI, or SAP.
"""

import logging

from langchain_openai import ChatOpenAI

from repair_ai.core.config import Settings
from repair_ai.core.exceptions import GenerationProviderError
from repair_ai.llm.prompts import build_prompt, language_name, style_instruction
from repair_ai.schemas.generation import LLMGenerationOutput

logger = logging.getLogger(__name__)


class LangChainGenerator:
    """``RepairDescriptionGenerator`` backed by a LangChain LCEL chain.

    The chain is built lazily on first use so that constructing the service
    never requires credentials; missing/invalid credentials surface as
    ``GenerationProviderError`` when generation is actually attempted.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._chain = None

    def _get_chain(self):
        if self._chain is None:
            prompt = build_prompt()
            model = ChatOpenAI(
                model=self._settings.model_name,
                temperature=self._settings.model_temperature,
            )
            self._chain = prompt | model.with_structured_output(
                LLMGenerationOutput
            )
        return self._chain

    def generate(
        self,
        *,
        facts: str,
        language: str,
        repair_type: str,
        style: str,
    ) -> LLMGenerationOutput:
        try:
            result = self._get_chain().invoke(
                {
                    "language_name": language_name(language),
                    "style_instruction": style_instruction(style),
                    "repair_type": repair_type,
                    "facts": facts,
                }
            )
        except Exception as exc:
            logger.exception("LLM generation failed")
            raise GenerationProviderError(
                "The text generation provider failed to produce a result."
            ) from exc

        if not isinstance(result, LLMGenerationOutput):
            logger.error("LLM returned unusable structured output: %r", result)
            raise GenerationProviderError(
                "The text generation provider returned an unusable result."
            )

        return result
