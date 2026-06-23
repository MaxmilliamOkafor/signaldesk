"""Runtime configuration, driven entirely by environment variables.

Secrets never live in code. Copy ``.env.example`` to ``.env`` for local runs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Resolved settings for a process."""

    # Backend selection: "local" | "ollama" | "openai" | "gemini"
    llm_backend: str = os.getenv("SIGNALDESK_BACKEND", "local")

    # Ollama
    ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3")

    # API backends
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    # Stream
    redis_url: str = os.getenv("REDIS_URL", "")  # empty => in-memory stream
    stream_key: str = os.getenv("SIGNALDESK_STREAM", "signaldesk:headlines")

    # Ingest
    rss_feeds: tuple[str, ...] = tuple(
        f.strip()
        for f in os.getenv(
            "SIGNALDESK_RSS",
            "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        ).split(",")
        if f.strip()
    )


def get_settings() -> Settings:
    """Return a fresh Settings snapshot (re-reads env each call)."""
    return Settings()
