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


@lru_cache
def get_settings() -> Settings:
    return Settings()
