from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EDUTRACK_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://edutrack:edutrack@localhost:54328/edutrack"
    redis_url: str = "redis://localhost:6389/0"
    api_cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"])

    jwt_secret: str = "dev-edutrack-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    refresh_token_days: int = 14

    celery_task_always_eager: bool = False

    llm_provider: Literal["auto", "openai", "openrouter", "deterministic"] = "auto"
    llm_model: str = "gpt-5.4"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    xgboost_min_samples: int = 50

    youtube_api_key: str | None = None
    youtube_search_base_url: str = "https://www.googleapis.com/youtube/v3/search"
    lesson_asset_model: str | None = None

    tribe_v2_enabled: bool = False
    tribe_v2_base_url: str | None = None
    tribe_v2_api_key: str | None = None
    tribe_v2_timeout_s: float = 20.0

    @property
    def resolved_lesson_asset_model(self) -> str:
        return self._strip_prefix(self.lesson_asset_model or self.llm_model)

    @property
    def resolved_llm_provider(self) -> str:
        if self.llm_provider == "auto":
            if self.openai_api_key:
                return "openai"
            if self.openrouter_api_key:
                return "openrouter"
            # auto no longer silently falls back to deterministic; force openai so
            # misconfiguration errors loudly at the first LLM call instead of
            # silently producing canned content.
            return "openai"
        return self.llm_provider

    @property
    def llm_base_url(self) -> str:
        if self.resolved_llm_provider == "openai":
            return self.openai_base_url
        return self.openrouter_base_url

    @property
    def llm_api_key(self) -> str | None:
        if self.resolved_llm_provider == "openai":
            return self.openai_api_key
        return self.openrouter_api_key

    @property
    def resolved_llm_model(self) -> str:
        return self._strip_prefix(self.llm_model)

    @property
    def resolved_embedding_model(self) -> str:
        return self._strip_prefix(self.embedding_model)

    def _strip_prefix(self, model: str) -> str:
        """OpenAI direct API rejects the `openai/` prefix used by OpenRouter."""
        if self.resolved_llm_provider == "openai" and model.startswith("openai/"):
            return model.split("/", 1)[1]
        return model


@lru_cache
def get_settings() -> Settings:
    return Settings()
