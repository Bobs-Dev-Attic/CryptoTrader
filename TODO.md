# CryptoTrader — TODO (prioritized)

Findings from a review across engineering, security/pentest, UX, memory/perf,
and legal/compliance perspectives. Ordered so each tier unblocks or de-risks the
next. Tags: **[sev]** critical/high/med/low · **[effort]** S/M/L · **[lens]**.

The rationale behind each item is in [`docs/REVIEW.md`](./docs/REVIEW.md).

> ⚠️ **Do not enable live trading for real users, or make the app publicly
> reachable, until every P0 is done.** Today the app is only safe because Vercel
> Deployment Protection hides it — that is a config accident, not a control.

---

## P0 — must fix before real money or public exposure

- [x] **Mandatory, independent secrets in production.** ✅ Done (#33).
  `config.security_warnings()` flags a default `JWT_SECRET` / unset
  `ENCRYPTION_KEY`; `main.py` refuses to start when `ENVIRONMENT=production` and
  either is insecure (warns otherwise). `ENCRYPTION_KEY` is now an independent
  primary key via `MultiFernet`, with the legacy JWT-derived key kept only as a
  decrypt fallback — safe rotation, no data loss. **Action for the operator:**
  set `JWT_SECRET` + `ENCRYPTION_KEY` in Vercel, *then* set
  `ENVIRONMENT=production` to turn on enforcement. **[critical][S][security]**
- [x] **Concurrency guard on agent execution.** ✅ Done (#35). `run_agent_once`
  takes a per-agent Postgres **transaction-level advisory lock**
  (`pg_try_advisory_xact_lock`, pooler-safe) and re-checks due-ness *inside* the
  lock (`respect_interval`), so overlapping ticks can't double-run an agent or
  place duplicate live orders; manual `/run` returns 409 if one is already in
  flight. No-op on SQLite. **[critical][M][security/correctness]**
- [x] **Rate limiting.** ✅ Done (#35). DB-backed fixed-window limiter
  (`ratelimit.py`, no Redis needed) on `/api/auth/login` (10/min/IP),
  `/register` (10/hr/IP), and the unauthenticated `/api/market/volatility`
  (30/min/IP), which is also now cached ~30s to remove the fan-out
  amplification. Fail-open on store errors. **[critical][M][security]**
- [ ] **Legal groundwork before any live trade.** Risk disclaimer + explicit
  consent, Terms of Service, Privacy Policy, and jurisdiction gating. An app that
  places real trades and custodies exchange API keys implicates money-transmission,
  investment-advice, and KYC/AML rules that vary by region; storing PII (email)
  triggers GDPR/CCPA (right to deletion/export). Get counsel before launch.
  **[critical][M][legal]**

## P1 — before beta / inviting users

- [x] **Live-trading safety rails.** ✅ Done (#36). `risk.live_buy_guard`
  vets every LIVE buy: max-slippage abort (live vs. signal price), min-notional
  floor ($5 hard + configurable), max-position cap (clamps to headroom), and a
  per-UTC-day notional cap — all in `agent.risk_config`, surfaced in the New
  Agent "Live-trading limits" section. Exits are never gated. (Exchange
  client-order-id idempotency still a nice-to-have; the advisory lock from #35
  already prevents duplicate placement.) **[high][M][engineering]**
- [x] **Token handling.** ✅ Done (#37). Access-token TTL cut to 30 min and
  paired with a 30-day rotating **refresh token**; both carry a `type` claim and
  a per-user `token_version`, checked server-side in `deps.py` so
  `/logout-all` and password change **revoke** every outstanding session (logout
  is no longer client-only). Frontend does a single-flight **silent refresh** on
  401. A strict **CSP** (`script-src 'self'`) plus HSTS/X-Frame-Options/nosniff/
  Referrer-Policy/Permissions-Policy ship in `vercel.json`, validated against the
  real web build in headless Chromium. (httpOnly cookies deferred — would require
  reworking the same-origin fetch flow; the CSP + short TTL + revocation close the
  XSS-exfiltration window in the meantime.) **[high][M][security]**
- [ ] **Scanner performance.** `marketscan._candle_metric` builds a **new ccxt
  client per symbol**, each doing an implicit `load_markets()` → ~50 network
  calls per candle-metric scan. Reuse one client per exchange (cache markets),
  and cache scan results ~30–60s. **[high][S][perf]**
- [x] **Unbounded queries / retention.** ✅ Done (#38). New `retention.py`
  prunes aged `equity_snapshots` and `signals` on every tick (batched
  `id IN (SELECT … LIMIT n)`, configurable `*_retention_days`; **trades are
  never pruned** — they're the P&L record). `portfolio.stats` win/loss is now a
  SQL conditional-aggregation (no more loading every trade); `equity_history`,
  `agent_equity`, and `optimize` select only the scalar columns they need, add
  time-window / `LIMIT` bounds, and downsample — `equity_history` seeds each
  agent's carry-in equity from its last pre-window snapshot so the total stays
  correct at the left edge. **[high][M][perf/memory]**
- [x] **Continuous integration.** ✅ Done (#33). `.github/workflows/ci.yml`
  runs `pytest` (backend) and `tsc --noEmit` + `expo export` (frontend) on every
  PR and push to `main`. **[high][S][engineering]**
- [x] **Real migrations.** ✅ Done (#39). **Alembic** now owns the schema.
  `migrations/` holds a create_all-based baseline (`0001_baseline`, autogenerate
  confirms zero drift vs. the models) and `env.py` wired to the app's engine +
  metadata. `migrations_runtime.run_migrations()` self-applies on startup (no
  serverless migration step): a brand-new DB upgrades from zero; the existing
  prod DB — built by the old path, so no `alembic_version` — is **adopted in
  place** (backfill columns once, then *stamp* the baseline, never re-create),
  preserving all data. Future schema changes are real migrations, not
  `_ADDED_COLUMNS` entries. **[high][M][engineering]**

## P2 — hardening & polish

- [ ] **Config hygiene.** `DEBUG=true` and `CORS_ORIGINS=*` are the defaults;
  `_run_validation` returns raw `type(exc).__name__: exc` to clients (info leak).
  Default DEBUG off, tighten CORS, and return generic auth-failure messages.
  **[med][S][security]**
- [ ] **Account security features.** Email-ownership verification on
  register/change, password strength + breach (HIBP k-anon) check, optional TOTP
  2FA, and audit logging of security events. **[med][M][security]**
- [ ] **Observability.** No error tracking or structured logs. Add Sentry (or
  equivalent) + request/trade audit logs; alert on tick failures. **[med][S][eng]**
- [ ] **Secret-leak review.** Ensure ccxt exceptions (which can embed request
  details) are never logged verbatim where they might include key material.
  **[med][S][security]**
- [ ] **UX/accessibility.** Status is color-only (add text/icons); `MiniButton`
  touch targets are <44px; inputs lack a show-password toggle; going **live**
  deserves a typed confirm, not just a warning line; consolidate the several
  30–45s pollers (dashboard, alerts, movers, notifier) into one shared,
  visibility-aware refresh to cut battery/requests; add loading skeletons +
  aria labels on web. **[med][M][ux]**
- [ ] **Notification hygiene.** De-dupe/rate-limit pushes, coalesce repeat
  triggers, and add quiet-hours so a flapping metric can't spam. **[med][S][ux]**

## P3 — growth & depth

- [ ] Offline **backtesting** (vectorbt) so users can validate a strategy on
  history before going live — the single biggest trust-builder. **[low][L][founder]**
- [ ] Frontend tests (Jest + RTL) and an E2E smoke (Playwright) for the core
  flows. **[low][M][engineering]**
- [ ] WebSocket price streaming (replace polling), more exchanges, per-agent
  logs/export, i18n, light theme. **[low][L][engineering/ux]**
- [ ] **Positioning** (marketer/founder): lead with "paper-first, you hold the
  keys, transparent rationale on every trade"; publish the risk model and a
  changelog; the version badge is a nice trust signal — surface a public status
  page too. **[low][M][marketing]**

---

## Quick wins (high value / low effort — do first within their tier)
1. Fail-fast on default secrets in prod + decouple the Fernet key. *(P0)*
2. Cache the volatility scan + reuse one ccxt client per exchange. *(P1)*
3. Add the CI workflow. *(P1)*
4. Default `DEBUG=false`, generic auth errors. *(P2)*
