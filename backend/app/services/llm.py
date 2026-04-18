from __future__ import annotations

from openai import AsyncOpenAI

from app.settings import get_settings


def llm_client() -> AsyncOpenAI:
    settings = get_settings()
    return AsyncOpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)


def llm_model() -> str:
    return get_settings().resolved_llm_model


def embedding_model() -> str:
    return get_settings().resolved_embedding_model
