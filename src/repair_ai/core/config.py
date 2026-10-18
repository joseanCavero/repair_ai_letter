"""Typed, environment-based application configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="REPAIR_AI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenAI credentials are read from the standard OPENAI_API_KEY env var
    # by the langchain-openai integration; it is intentionally not duplicated
    # into this settings object.
    model_name: str = "gpt-4o-mini"
    model_temperature: float = 0.0
    prompt_version: str = "repair-desc-v1"

    # API-key authentication for the generation endpoint. When unset, the
    # endpoint fails closed (503) so the service can never be exposed
    # unprotected by accident.
    api_key: str | None = None

    # Operational limits: bounded model calls and request sizes.
    model_timeout_seconds: float = 30.0
    model_max_retries: int = 1
    model_max_output_tokens: int = 800
    max_request_body_bytes: int = 262_144  # 256 KiB


@lru_cache
def get_settings() -> Settings:
    return Settings()
