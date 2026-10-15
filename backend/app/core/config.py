"""SEC Financial Intelligence Engine — Core Configuration."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ────────────────────────────────────────────────────────────
    app_env: str = Field(default="development")
    app_log_level: str = Field(default="INFO")
    backend_port: int = Field(default=8000)
    cors_origins: str = Field(default="http://localhost:5173,http://localhost:3000")

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # ── Database ───────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://secfi:secfi_dev@localhost:5432/secfi"
    )
    database_url_sync: str = Field(
        default="postgresql://secfi:secfi_dev@localhost:5432/secfi"
    )

    # ── Qdrant ─────────────────────────────────────────────────────────
    qdrant_host: str = Field(default="localhost")
    qdrant_port: int = Field(default=6333)
    qdrant_collection: str = Field(default="sec_chunks")

    # ── SEC EDGAR ──────────────────────────────────────────────────────
    sec_user_agent: str = Field(default="SecFIEngine admin@example.com")
    sec_request_delay_ms: int = Field(default=120)

    # ── AI Providers ───────────────────────────────────────────────────
    ai_chat_provider: str = Field(default="gemini")
    ai_embedding_provider: str = Field(default="gemini")
    ai_rerank_provider: str = Field(default="none")

    gemini_api_key: str = Field(default="")
    gemini_chat_model: str = Field(default="gemini-2.0-flash")
    gemini_embedding_model: str = Field(default="text-embedding-004")

    openai_api_key: str = Field(default="")
    openai_chat_model: str = Field(default="gpt-4o-mini")
    openai_embedding_model: str = Field(default="text-embedding-3-small")

    # ── Retrieval ──────────────────────────────────────────────────────
    dense_top_k: int = Field(default=25)
    sparse_top_k: int = Field(default=25)
    rerank_top_k: int = Field(default=4)
    embedding_dimensions: int = Field(default=768)

    # ── Derived helpers ────────────────────────────────────────────────
    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_chat_provider(self) -> bool:
        if self.ai_chat_provider == "gemini":
            return self.has_gemini
        if self.ai_chat_provider == "openai":
            return self.has_openai
        return False

    @property
    def has_embedding_provider(self) -> bool:
        if self.ai_embedding_provider == "gemini":
            return self.has_gemini
        if self.ai_embedding_provider == "openai":
            return self.has_openai
        return False

    @property
    def limited_mode(self) -> bool:
        """True when no AI provider is configured — retrieval works, generation disabled."""
        return not self.has_chat_provider


@lru_cache()
def get_settings() -> Settings:
    """Cached singleton settings instance."""
    return Settings()
