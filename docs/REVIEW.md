# CryptoTrader — Review & Critique

A multi-perspective review of the codebase as of app **v0.6.0**. Findings feed
the prioritized [`../TODO.md`](../TODO.md). This is analysis, not a changelog —
nothing here is fixed yet unless TODO says so.

**Overall:** a genuinely impressive, coherent product for its stage — clean
strategy abstraction, paper-first safety, encrypted key storage, same-origin
serverless deploy, self-healing schema, and thoughtful onboarding copy. The gaps
below are the ones that matter before real money or a public audience.

---

## 1. Software engineer

**Strengths**
- Clear separation: pure `Strategy.decide()` vs. execution/risk in `runner.py`;
  exchange access behind a single adapter interface; pydantic schemas at the edge.
- Pure-Python indicators/portfolio math keep the serverless bundle lean (a
  deliberate, correct call over TA-Lib/vectorbt/cvxpy).
- Tests are meaningful (67) and use a `FakeAdapter`, not live network.

**Issues**
- **No migrations.** `create_all` + a hand-maintained `_ADDED_COLUMNS` ALTER list
  is clever but drifts silently, has no down-path, and couples correctness to
  "did someone remember to add the DDL." Move to Alembic.
- **No CI.** The three-command gate (pytest / tsc / expo export) is enforced only
  by discipline. One GitHub Action removes a whole class of regressions.
- **Blocking I/O in a sync serverless path.** Agent ticks and market scans call
  ccxt synchronously; the tick loops agents sequentially. Fine at small N, but a
  handful of running agents × a slow exchange can approach the function timeout.
- **`get_adapter` builds a fresh ccxt client every call** (and the scanner does it
  per symbol) → repeated implicit `load_markets()`. Cache clients/markets.
- **No frontend tests** and no shared data-fetching layer (each screen hand-rolls
  `useFocusEffect` + `setInterval`), so polling logic and error handling are
  duplicated and inconsistent.

## 2. Security analyst / penetration tester

Assume Deployment Protection is eventually turned off (it must be, for a public
product). Then:

- **Forgeable auth + decryptable secrets (critical).** Default `JWT_SECRET` ships
  in `config.py`/`.env.example`; `ENCRYPTION_KEY` falls back to
  `sha256(JWT_SECRET)`. If the default reaches prod, an attacker forges any
  user's JWT *and* decrypts every stored exchange API key. The two secrets must
  be independent and mandatory. This is the top finding.
- **Exchange API keys are the crown jewels.** They're encrypted at rest (good)
  and never returned (good), but a single Fernet key in one env var is the whole
  perimeter — add rotation, and scope guidance is right (Trade+View, never
  Withdraw) but should be enforced/validated where the exchange API allows.
- **No rate limiting / lockout** on `/auth/login`,`/register` → credential
  stuffing, user enumeration (distinct 400 "already registered"), brute force.
- **DoS amplification.** Unauthenticated `/api/market/volatility` (candle metrics)
  fans out to ~25–50 exchange calls per request; trivially abusable.
- **Token theft blast radius.** JWT in `localStorage`, 24h TTL, no revocation →
  one XSS = 24h of full account access. Needs CSP + short TTL + refresh/revoke.
- **Info leakage.** Validation errors echo `type(exc).__name__: exc`; `DEBUG=true`
  default; verbose messages help an attacker fingerprint internals.
- **SSRF/injection surface is low** (exchange is an enum; ccxt targets fixed
  hosts; ORM parameterizes) — good. Keep symbols validated against a known set.
- **Cron endpoint** is fail-closed (empty secret → 401) — correct; keep the
  secret strong and rotate it.

## 3. UX designer

**Strengths**
- Excellent lay-person onboarding: strategy "best for / avoid when" panels,
  ⓘ tooltips, paper-by-default, explicit live-mode warnings, a version badge that
  demystifies "am I on the new build?".
- The recent max-width + 2-column pass fixed the desktop "everything stretches"
  problem.

**Issues**
- **Accessibility:** status is conveyed by color alone; several touch targets
  (`MiniButton`, chips) are below the 44px guideline; web is missing aria labels;
  no focus-visible styling. Password fields have no show/hide toggle.
- **Risk affordance:** switching an agent to **live** (real money) is a pill +
  a warning line — it should require a deliberate confirm (type the symbol, or a
  modal) to prevent fat-finger live trading.
- **Polling sprawl:** dashboard, alerts, movers, and the global notifier each run
  their own 30–45s timers regardless of tab visibility — battery/data drain and
  redundant requests. One shared, `visibilitychange`-aware fetch layer would fix
  it and make data feel more consistent.
- **Feedback:** some errors surface raw API strings; add friendly copy + loading
  skeletons instead of "Loading…" text.

## 4. Memory / performance

- **Unbounded reads:** `equity_history` pulls every snapshot for every agent into
  memory and downsamples in Python; `signals`/`trades`/`equity_snapshots` grow
  without bound or retention. Downsample/aggregate in SQL, window queries, prune.
- **Per-request ccxt churn** (see §1) — the dominant avoidable cost.
- **Serverless connection use** is handled well (`NullPool` + pooler), and
  pure-Python math avoids heavy native deps — both good calls.

## 5. Marketer

- The story writes itself and is under-told: **"paper-first. You keep custody of
  your keys. Every trade shows its reasoning."** Put that on the landing view.
- Trust artifacts to add: the risk model, a public changelog/status page, and
  "how your keys are protected." The version badge is already a subtle trust cue.
- Differentiators vs. generic bots: transparent per-signal rationale, an
  LLM-analyst option, and a volatility radar. Lead with those.

## 6. Founder / executive

- **Biggest risk isn't code, it's liability.** A tool that places real trades and
  holds exchange keys, aimed at laypeople, needs disclaimers, ToS/Privacy, and a
  compliance view *before* growth — one bad loss + no disclaimer is existential.
- **Highest-leverage feature:** backtesting. It converts "trust me" into "see for
  yourself" and is the difference between a toy and a product.
- **Moat:** the clean strategy/risk framework + transparency. Keep paper-first as
  the default funnel; make going live a deliberate, gated step.

## 7. Legal / compliance

- **Regulatory:** automated trading and key custody can implicate money
  transmission, investment-adviser/broker rules, and KYC/AML depending on
  jurisdiction and whether you ever touch funds/flow. Geo-gate and get counsel.
- **Data protection:** email is PII → GDPR/CCPA obligations (consent, export,
  deletion, breach notification). There is no account-deletion or data-export
  path today.
- **Consumer protection:** clear, prominent risk disclaimer ("you can lose
  money", "not financial advice") and honest performance framing (paper ≠ live)
  are table stakes.
- **Third-party terms:** confirm each exchange's API ToS permits automated
  trading via a third-party app, and that Anthropic API usage terms are met.

---

## What's already right (keep it)
Paper-first defaults · encrypted, never-returned keys · least-privilege key
guidance · same-origin serverless (no CORS attack surface in prod) · defensive
tick (a failing agent/watch never breaks the loop) · self-healing schema for
zero-downtime column adds · lean pure-Python compute · strong onboarding copy.
