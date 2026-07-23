"""Application configuration loaded from environment variables / .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# The insecure default shipped for local dev. Must never be used in production.
DEFAULT_JWT_SECRET = "change-me-in-production-please"


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
    # Shared secret required to call the internal cron tick endpoint. When the
    # app runs serverless (no long-lived process), an external scheduler
    # (Vercel Cron / Supabase pg_cron) hits POST /api/internal/tick with this.
    internal_cron_secret: str = ""

    @property
    def is_serverless(self) -> bool:
        """True on Vercel (and similar) where background threads don't persist."""
        import os

        return bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

    @property
    def is_production(self) -> bool:
        """Only true when explicitly opted in via ENVIRONMENT=production.

        Deliberately NOT inferred from `is_serverless`, so turning on the strict
        secret checks is an explicit deploy decision and never silently breaks an
        existing environment.
        """
        return self.environment.strip().lower() in {"production", "prod"}

    def security_warnings(self) -> list[str]:
        """Human-readable list of insecure-config problems (empty = all good)."""
        problems: list[str] = []
        if not self.jwt_secret or self.jwt_secret == DEFAULT_JWT_SECRET:
            problems.append(
                "JWT_SECRET is unset or the shipped default — anyone could forge "
                "auth tokens. Set a strong random value."
            )
        if not self.encryption_key.strip():
            problems.append(
                "ENCRYPTION_KEY is unset — exchange API keys are encrypted with a "
                "key DERIVED FROM JWT_SECRET (dev-only). Set an independent Fernet "
                "key: python -c \"from cryptography.fernet import Fernet; "
                "print(Fernet.generate_key().decode())\""
            )
        return problems

    # --- Rate limiting ---
    # DB-backed fixed-window limiter on sensitive endpoints. Disabled in tests.
    rate_limit_enabled: bool = True

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
