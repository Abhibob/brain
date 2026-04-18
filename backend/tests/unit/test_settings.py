"""Unit tests for app.settings: resolved_llm_provider, defaults, prefix handling."""

from __future__ import annotations

from app.settings import Settings, get_settings


class TestResolvedLLMProvider:
    def test_auto_prefers_openai_when_key_set(self) -> None:
        s = Settings(llm_provider="auto", openai_api_key="sk-openai-test")
        assert s.resolved_llm_provider == "openai"

    def test_auto_falls_back_to_openrouter_when_only_that_key_set(self) -> None:
        s = Settings(llm_provider="auto", openai_api_key=None, openrouter_api_key="sk-or-test")
        assert s.resolved_llm_provider == "openrouter"

    def test_auto_with_no_keys_still_targets_openai(self) -> None:
        """LLM is mandatory in runtime - auto never silently degrades to deterministic."""
        s = Settings(llm_provider="auto", openai_api_key=None, openrouter_api_key=None)
        assert s.resolved_llm_provider == "openai"

    def test_explicit_deterministic_wins_over_keys(self) -> None:
        s = Settings(llm_provider="deterministic", openai_api_key="sk-test")
        assert s.resolved_llm_provider == "deterministic"

    def test_explicit_openai_passes_through(self) -> None:
        s = Settings(llm_provider="openai", openai_api_key="sk-openai-test")
        assert s.resolved_llm_provider == "openai"

    def test_explicit_openrouter_passes_through(self) -> None:
        s = Settings(llm_provider="openrouter", openrouter_api_key="sk-or-test")
        assert s.resolved_llm_provider == "openrouter"


class TestResolvedModelNames:
    def test_openai_strips_openai_prefix(self) -> None:
        s = Settings(llm_provider="openai", llm_model="openai/gpt-5.4", embedding_model="openai/text-embedding-3-small")
        assert s.resolved_llm_model == "gpt-5.4"
        assert s.resolved_embedding_model == "text-embedding-3-small"

    def test_openrouter_keeps_prefix(self) -> None:
        s = Settings(llm_provider="openrouter", openrouter_api_key="x", llm_model="openai/gpt-5", embedding_model="openai/text-embedding-3-small")
        assert s.resolved_llm_model == "openai/gpt-5"
        assert s.resolved_embedding_model == "openai/text-embedding-3-small"


class TestLLMCredentials:
    def test_openai_returns_openai_base_and_key(self) -> None:
        s = Settings(llm_provider="openai", openai_api_key="sk-oa", openai_base_url="https://api.openai.com/v1")
        assert s.llm_base_url == "https://api.openai.com/v1"
        assert s.llm_api_key == "sk-oa"

    def test_openrouter_returns_openrouter_base_and_key(self) -> None:
        s = Settings(llm_provider="openrouter", openrouter_api_key="sk-or")
        assert s.llm_base_url == "https://openrouter.ai/api/v1"
        assert s.llm_api_key == "sk-or"


class TestDefaults:
    def test_core_defaults(self) -> None:
        s = Settings(llm_provider="deterministic")
        assert s.jwt_algorithm == "HS256"
        assert s.access_token_minutes == 60
        assert s.refresh_token_days == 14
        assert s.embedding_dim == 1536
        assert s.embedding_model == "text-embedding-3-small"
        assert s.llm_model == "gpt-5.4"

    def test_get_settings_cached(self) -> None:
        assert get_settings() is get_settings()


class TestLessonAssetModel:
    def test_defaults_to_llm_model(self) -> None:
        s = Settings(llm_provider="deterministic", llm_model="gpt-5.4", lesson_asset_model=None)
        assert s.resolved_lesson_asset_model == "gpt-5.4"

    def test_overridden_when_explicit(self) -> None:
        s = Settings(llm_provider="deterministic", llm_model="gpt-5.4", lesson_asset_model="gpt-5-mini")
        assert s.resolved_lesson_asset_model == "gpt-5-mini"
