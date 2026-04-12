"""
llm_client.py — Unified LLM client for the FastAPI backend
Prisma | Production-Grade Backend

Pluggable provider system: Ollama / Groq / Gemini.
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


class GroqClient:
    def __init__(self, api_key: str) -> None:
        import openai
        # Groq seamlessly supports the OpenAI SDK!
        self._client = openai.OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

    def generate(self, prompt: str, model: str | None = None, **_: Any) -> str:
        model = model or "llama3-8b-8192"
        resp = self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
        )
        return (resp.choices[0].message.content or "").strip()


class GeminiClient:
    def __init__(self, api_key: str) -> None:
        import openai
        # Google Gemini supports the OpenAI SDK natively!
        self._client = openai.OpenAI(api_key=api_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")

    def generate(self, prompt: str, model: str | None = None, **_: Any) -> str:
        model = model or "gemini-1.5-flash"
        resp = self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
        )
        return (resp.choices[0].message.content or "").strip()


# ---------------------------------------------------------------------------
# Unified dispatcher
# ---------------------------------------------------------------------------

class LLMClient:
    """
    Single object passed around the backend.

    Usage:
        client = LLMClient(provider="ollama")
        text = client.generate(prompt, provider="groq", model="llama3-8b-8192")
    """

    def __init__(
        self,
        provider: str = "ollama",
        groq_key: str | None = None,
        gemini_key: str | None = None,
    ) -> None:
        self._providers: dict[str, Any] = {}
        self._default_provider = provider

        self._providers["ollama"] = OllamaClient()

        g_key = groq_key or os.getenv("GROQ_API_KEY", "")
        if g_key:
            try:
                self._providers["groq"] = GroqClient(g_key)
            except Exception as exc:
                logger.warning("Groq init failed: %s", exc)

        gem_key = gemini_key or os.getenv("GEMINI_API_KEY", "")
        if gem_key:
            try:
                self._providers["gemini"] = GeminiClient(gem_key)
            except Exception as exc:
                logger.warning("Gemini init failed: %s", exc)

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
        if provider == "groq":
            self._providers["groq"] = GroqClient(api_key)
        elif provider == "gemini":
            self._providers["gemini"] = GeminiClient(api_key)
        else:
            logger.warning("Unknown provider for key update: %s", provider)
