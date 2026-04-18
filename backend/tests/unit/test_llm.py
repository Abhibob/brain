"""Unit tests for app.services.llm helpers."""

from __future__ import annotations

import pytest

from app.services.llm import embedding_model, llm_client, llm_model
from app.settings import Settings, get_settings


class TestLLMClient:
    def test_client_constructs_when_key_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EDUTRACK_LLM_PROVIDER", "openai")
        monkeypatch.setenv("EDUTRACK_OPENAI_API_KEY", "sk-test-123")
        get_settings.cache_clear()
        try:
            client = llm_client()
            assert str(client.base_url).startswith("http")
            assert str(client.api_key) == "sk-test-123" or "test-123" in repr(client.api_key)
        finally:
            get_settings.cache_clear()

    def test_client_points_at_openai_when_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EDUTRACK_LLM_PROVIDER", "openai")
        monkeypatch.setenv("EDUTRACK_OPENAI_API_KEY", "sk-test-xyz")
        monkeypatch.setenv("EDUTRACK_OPENAI_BASE_URL", "https://api.openai.com/v1")
        get_settings.cache_clear()
        try:
            client = llm_client()
            assert "api.openai.com" in str(client.base_url)
        finally:
            get_settings.cache_clear()


class TestModelHelpers:
    def test_model_helpers_return_strings(self) -> None:
        assert isinstance(llm_model(), str)
        assert isinstance(embedding_model(), str)


class TestPrefixStripping:
    def test_strip_prefix_on_openai(self) -> None:
        s = Settings(llm_provider="openai", openai_api_key="k", llm_model="openai/gpt-5.4")
        assert s.resolved_llm_model == "gpt-5.4"

    def test_no_strip_on_openrouter(self) -> None:
        s = Settings(llm_provider="openrouter", openrouter_api_key="k", llm_model="openai/gpt-5.4")
        assert s.resolved_llm_model == "openai/gpt-5.4"

    def test_no_prefix_untouched(self) -> None:
        s = Settings(llm_provider="openai", openai_api_key="k", llm_model="gpt-5.4")
        assert s.resolved_llm_model == "gpt-5.4"


class TestGetSettingsWiring:
    def test_returns_settings_instance(self) -> None:
        s = get_settings()
        assert hasattr(s, "resolved_llm_provider")
