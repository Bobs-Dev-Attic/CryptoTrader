"""Application configuration loaded from environment variables / .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- General ---
    app_name: str = "CryptoTrader"
    environment: str = "development"
    debug: bool = True

    # --- Database ---
    database_url: str = "sqlite:///./cryptotrader.db"

    # --- Auth ---
    # Secret used to sign JWTs. MUST be overridden in production.
    jwt_secret: str = "change-me-in-production-please"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 1 day

    # --- Encryption ---
    # Fernet key used to encrypt exchange API credentials at rest.
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # If empty, a key is derived deterministically from jwt_secret (dev only).
    encryption_key: str = ""

    # --- LLM (for LLM-powered agents) ---
    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-4-8"

    # --- Agent scheduler ---
    scheduler_enabled: bool = True
    # Global floor on how often any agent may evaluate (seconds).
    min_agent_interval_seconds: int = 30

    # --- CORS ---
    # Comma-separated list of allowed origins for the web/mobile client.
    cors_origins: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
