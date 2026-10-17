"""
DocSync — Application configuration.
All secrets are loaded from environment variables / .env file.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Gemma AI ─────────────────────────────────────────────────────────────
    gemma_api_url: Optional[str] = None
    gemma_api_key: Optional[str] = None
    gemma_model: Optional[str] = None   # optional if endpoint encodes the model

    # ── GitHub ───────────────────────────────────────────────────────────────
    github_token: Optional[str] = None  # optional; raises rate limit for public repos

    # ── Analysis limits ──────────────────────────────────────────────────────
    max_files: int = 60
    max_file_size_bytes: int = 200_000   # 200 KB per file
    max_total_bytes: int = 3_000_000    # 3 MB total content
    request_timeout: int = 30           # seconds

    # ── CORS / server ─────────────────────────────────────────────────────────
    frontend_origin: str = "http://localhost:5173"

    @property
    def gemma_configured(self) -> bool:
        return bool(self.gemma_api_url and self.gemma_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
