"""
llm_client.py — Unified LLM client for the FastAPI backend
Prisma | Production-Grade Backend

Pluggable provider system: Ollama / OpenAI / Anthropic.
Mirrors the provider pattern in src/llm_generator.py but is
import-safe (no Streamlit dependency) and async-ready.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("Prisma.LLMClient")


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

class OllamaClient:
    def generate(self, prompt: str, model: str | None = None, **_: Any) -> str:
        model = model or "gemma:2b"
        try:
            import ollama
            resp = ollama.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp["message"]["content"]
        except Exception as exc:
            raise ConnectionError(
                f"Ollama error ({model}): {exc}. "
                "Ensure `ollama serve` is running and the model is pulled."
            ) from exc


class OpenAIClient:
    def __init__(self, api_key: str) -> None:
        import openai
        self._client = openai.OpenAI(api_key=api_key)

    def generate(self, prompt: str, model: str | None = None, **_: Any) -> str:
        model = model or "gpt-4-turbo"
        resp = self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
        )
        return resp.choices[0].message.content or ""


class AnthropicClient:
    def __init__(self, api_key: str) -> None:
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)

    def generate(self, prompt: str, model: str | None = None, **_: Any) -> str:
        model = model or "claude-3-sonnet-20240229"
        msg = self._client.messages.create(
            model=model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text if msg.content else ""


# ---------------------------------------------------------------------------
# Unified dispatcher
# ---------------------------------------------------------------------------

class LLMClient:
    """
    Single object passed around the backend.

    Usage:
        client = LLMClient(provider="ollama")
        text = client.generate(prompt, provider="ollama", model="gemma:2b")
    """

    def __init__(
        self,
        provider: str = "ollama",
        openai_key: str | None = None,
        anthropic_key: str | None = None,
    ) -> None:
        self._providers: dict[str, Any] = {}
        self._default_provider = provider

        self._providers["ollama"] = OllamaClient()

        oai_key = openai_key or os.getenv("OPENAI_API_KEY", "")
        if oai_key:
            try:
                self._providers["openai"] = OpenAIClient(oai_key)
            except Exception as exc:
                logger.warning("OpenAI init failed: %s", exc)

        ant_key = anthropic_key or os.getenv("ANTHROPIC_API_KEY", "")
        if ant_key:
            try:
                self._providers["anthropic"] = AnthropicClient(ant_key)
            except Exception as exc:
                logger.warning("Anthropic init failed: %s", exc)

    def generate(
        self,
        prompt: str,
        provider: str | None = None,
        model: str | None = None,
    ) -> str:
        prov_name = provider or self._default_provider
        client = self._providers.get(prov_name)
        if client is None:
            raise ValueError(
                f"Provider '{prov_name}' is not initialised. "
                "Check API keys or ensure Ollama is running."
            )
        return client.generate(prompt, model=model)

    def update_key(self, provider: str, api_key: str) -> None:
        if provider == "openai":
            self._providers["openai"] = OpenAIClient(api_key)
        elif provider == "anthropic":
            self._providers["anthropic"] = AnthropicClient(api_key)
        else:
            logger.warning("Unknown provider for key update: %s", provider)
