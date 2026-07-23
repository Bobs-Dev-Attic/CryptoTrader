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
- [ ] **Concurrency guard on agent execution.** `internal.tick` → `run_agent_once`
  has no lock. If a tick runs >60s (pg_cron fires again) or is invoked twice,
  an agent can be evaluated concurrently → **duplicate live orders**. Add a DB
  advisory lock / `SELECT … FOR UPDATE SKIP LOCKED` per agent, or an idempotency
  key on order placement. **[critical][M][security/correctness]**
- [ ] **Rate limiting.** No throttling on `/api/auth/login` or `/register`
  (credential stuffing / brute force, no lockout) or on the **unauthenticated**
  `/api/market/*` endpoints — `/api/market/volatility?metric=ret_vol` fans out
  to ~25 exchange calls per request (DoS amplification). Add per-IP + per-account
  limits (e.g. slowapi / Redis token bucket) and cache market scans.
  **[critical][M][security]**
- [ ] **Legal groundwork before any live trade.** Risk disclaimer + explicit
  consent, Terms of Service, Privacy Policy, and jurisdiction gating. An app that
  places real trades and custodies exchange API keys implicates money-transmission,
  investment-advice, and KYC/AML rules that vary by region; storing PII (email)
  triggers GDPR/CCPA (right to deletion/export). Get counsel before launch.
  **[critical][M][legal]**

## P1 — before beta / inviting users

- [ ] **Live-trading safety rails.** Market orders have no slippage guard,
  min-notional check, max-position cap, or exchange idempotency key; a wrong
  config can dump capital. Add pre-trade validation + a hard per-agent daily
  notional cap. **[high][M][engineering]**
- [ ] **Token handling.** JWT lives in `AsyncStorage` (→ `localStorage` on web):
  any XSS exfiltrates a 24h-valid token with no revocation (logout is
  client-only). Add a strict CSP, shorten access-token TTL + refresh tokens, and
  a server-side revocation/`token_version` check. Consider httpOnly cookies.
  **[high][M][security]**
- [ ] **Scanner performance.** `marketscan._candle_metric` builds a **new ccxt
  client per symbol**, each doing an implicit `load_markets()` → ~50 network
  calls per candle-metric scan. Reuse one client per exchange (cache markets),
  and cache scan results ~30–60s. **[high][S][perf]**
- [ ] **Unbounded queries / retention.** `portfolio.equity_history` loads *all*
  snapshots for *all* agents into memory then downsamples in Python; `signals`,
  `equity_snapshots`, `trades` grow forever. Aggregate/downsample in SQL, add
  `LIMIT`/time windows, and a retention job. **[high][M][perf/memory]**
- [x] **Continuous integration.** ✅ Done (#33). `.github/workflows/ci.yml`
  runs `pytest` (backend) and `tsc --noEmit` + `expo export` (frontend) on every
  PR and push to `main`. **[high][S][engineering]**
- [ ] **Real migrations.** Replace `create_all` + hand-maintained
  `_ADDED_COLUMNS` with **Alembic**; the current scheme silently drifts and has
  no down-path or history. **[high][M][engineering]**

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
