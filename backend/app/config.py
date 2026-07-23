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
    # Off by default; verbose error surfaces / docs should be an explicit opt-in.
    debug: bool = False

    # --- Database ---
    database_url: str = "sqlite:///./cryptotrader.db"

    # --- Auth ---
    # Secret used to sign JWTs. MUST be overridden in production.
    jwt_secret: str = "change-me-in-production-please"
    jwt_algorithm: str = "HS256"
    # Short-lived access tokens; long-lived refresh tokens exchanged at /auth/refresh.
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 60 * 24 * 30  # 30 days

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

    # --- Data retention ---
    # High-volume, derivable rows are pruned by age on the internal tick so the
    # tables don't grow forever. Trades are NEVER pruned (they're the financial
    # record win/loss stats are derived from). 0 disables that table's prune.
    retention_enabled: bool = True
    snapshot_retention_days: int = 90  # equity_snapshots older than this are dropped
    signal_retention_days: int = 90    # signals older than this are dropped
    # Max rows deleted per table per tick — keeps each prune cheap and bounded.
    retention_batch: int = 5000

    # --- CORS ---
    # Comma-separated list of allowed browser origins for the API. In production
    # the web app is served SAME-ORIGIN (single Vercel project), so no cross-
    # origin entry is needed; the default only opens local Expo web dev ports.
    # Set explicitly (e.g. a custom frontend domain) if you serve the UI from a
    # different origin. Auth uses Bearer tokens, not cookies, so credentials are
    # not enabled and a wildcard here does not expose credentialed requests.
    cors_origins: str = "http://localhost:8081,http://localhost:19006"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def config_warnings(self) -> list[str]:
        """Non-fatal config-hygiene problems worth logging (esp. in production)."""
        problems: list[str] = []
        if self.debug:
            problems.append("DEBUG is on — disable it in production (verbose errors / docs).")
        if "*" in self.cors_origin_list:
            problems.append(
                "CORS_ORIGINS is a wildcard (*) — restrict it to the origins that "
                "actually serve the UI."
            )
        return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
