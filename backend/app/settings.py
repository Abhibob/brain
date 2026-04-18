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

    llm_provider: Literal["auto", "openrouter", "deterministic"] = "auto"
    llm_model: str = "anthropic/claude-opus-4-7"
    openrouter_api_key: str | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    embedding_model: str = "openai/text-embedding-3-small"
    embedding_dim: int = 1536

    xgboost_min_samples: int = 50

    @property
    def resolved_llm_provider(self) -> str:
        if self.llm_provider == "auto":
            return "openrouter" if self.openrouter_api_key else "deterministic"
        return self.llm_provider


@lru_cache
def get_settings() -> Settings:
    return Settings()
