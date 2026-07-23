"""Error tracking, structured logging, and an audit trail.

All three are best-effort and safe to leave unconfigured:
- **Sentry** is initialised only when ``SENTRY_DSN`` is set (the SDK is imported
  lazily, so it isn't even a hard dependency when unused).
- **Structured logging** emits one JSON object per line so Vercel's log drain
  (or any collector) can index by field. Toggle with ``LOG_JSON``.
- **Audit** events (trades, tick failures) go through a dedicated logger so they
  can be filtered/routed separately from ordinary app logs.

Nothing here may raise into a request or the tick: observability must never be
the reason a trade or a boot fails.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from .config import settings

logger = logging.getLogger("cryptotrader")
audit_logger = logging.getLogger("cryptotrader.audit")

_sentry_enabled = False
_configured = False


class _JsonFormatter(logging.Formatter):
    """Compact single-line JSON, with any ``extra={...}`` fields merged in."""

    _RESERVED = set(
        logging.makeLogRecord({}).__dict__.keys()
    ) | {"message", "asctime", "taskName"}

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        try:
            return json.dumps(payload, default=str)
        except Exception:
            return json.dumps({"level": record.levelname, "logger": record.name, "msg": record.getMessage()})


def configure_logging() -> None:
    """Install a stream handler (JSON or plain) on the app logger. Idempotent."""
    global _configured
    if _configured:
        return
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(
        _JsonFormatter()
        if settings.log_json
        else logging.Formatter("%(levelname)s [%(name)s] %(message)s")
    )
    root = logging.getLogger("cryptotrader")
    root.setLevel(level)
    root.handlers = [handler]
    # Don't double-emit through the root logger's default handler.
    root.propagate = False
    _configured = True


def init_observability() -> bool:
    """Initialise Sentry when a DSN is configured. Returns True if enabled."""
    global _sentry_enabled
    configure_logging()
    dsn = settings.sentry_dsn.strip()
    if not dsn:
        return False
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=dsn,
            environment=settings.environment,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            # Don't ship user PII (emails, IPs) to the error tracker by default.
            send_default_pii=False,
        )
        _sentry_enabled = True
        logger.info("Sentry error tracking enabled", extra={"environment": settings.environment})
    except Exception:
        # A missing package or bad DSN must not stop the app from booting.
        logger.exception("Failed to initialise Sentry; continuing without it")
        _sentry_enabled = False
    return _sentry_enabled


def capture_exception(exc: BaseException, **context: Any) -> None:
    """Log an exception (with context) and forward it to Sentry if enabled."""
    logger.error("exception: %s", type(exc).__name__, extra=context, exc_info=exc)
    if _sentry_enabled:
        try:
            import sentry_sdk

            with sentry_sdk.push_scope() as scope:
                for key, value in context.items():
                    scope.set_tag(key, value)
                sentry_sdk.capture_exception(exc)
        except Exception:
            pass


def audit(event: str, **fields: Any) -> None:
    """Emit a structured audit record (trades, tick failures, security events).

    Never include secrets or full exception strings in ``fields``.
    """
    audit_logger.info(event, extra={"event": event, "audit": True, **fields})
