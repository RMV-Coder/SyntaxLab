"""Process-level settings, read from environment variables prefixed ``SYNTAXLAB_``."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SYNTAXLAB_", env_file=".env", extra="ignore")

    languages_file: Path = SERVICE_ROOT / "config" / "languages.yaml"
    models_dir: Path = SERVICE_ROOT / ".models"
    glossary_dir: Path = SERVICE_ROOT / "data" / "glossary"
    enabled_languages: list[str] | None = Field(
        default=None, description="Restrict to these language codes (default: all enabled)."
    )
    preload: bool = Field(default=True, description="Load models at startup, not on first use.")

    cpu_threads: int = Field(default_factory=lambda: os.cpu_count() or 1, ge=1)
    max_queue: int = Field(default=8, ge=1, description="Pending analyses per language.")
    analysis_timeout_s: float = Field(default=30.0, gt=0)
    cache_size: int = Field(default=256, ge=0)

    default_max_chars: int = Field(default=300, ge=1)
    default_max_words: int = Field(default=40, ge=1)
    default_max_sentences: int = Field(default=1, ge=1)
    max_body_bytes: int = Field(default=16_384, ge=1024)

    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    rate_limit_per_minute: int = Field(default=60, ge=0, description="0 disables rate limiting.")
    rate_limit_burst: int = Field(default=10, ge=1)
    trust_proxy_headers: bool = Field(
        default=False, description="Use X-Forwarded-For for client IPs (only behind a proxy)."
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
