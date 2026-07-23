# CryptoTrader — agent guide (Claude Code / Codex)

Read this first. It exists to save you tokens and rework. `AGENTS.md` points here.

## What this is
A cross-platform app to configure **agents** that trade crypto (paper or live)
on Kraken, Binance, Coinbase, Robinhood. Monorepo:

```
backend/        FastAPI + SQLAlchemy 2.0 + Pydantic v2 (Python 3.11)
  app/
    api/        route modules: auth, accounts, agents, market, portfolio,
                watchlist, push, internal
    agents/     strategy framework: base, registry, rule_based, technical,
                llm_agent, indicators, risk, runner
    exchanges/  ccxt_adapter, coinbase_ed25519, robinhood, paper, base, factory
    marketscan.py   volatility scanner (curated universe)
    push.py         Web Push / VAPID
    models.py schemas.py security.py database.py config.py deps.py main.py
  tests/        pytest (fixtures in conftest.py: temp sqlite, FakeAdapter)
mobile/         Expo SDK 52 + React Native 0.76 + expo-router (file-based)
  app/          screens (file = route). (tabs)/ = dashboard/agents/accounts
  src/          api.ts, auth.tsx, menu.tsx, components.tsx, charts.tsx,
                theme.ts, notifications.ts, marketscan types, VersionBadge
  public/sw.js  service worker (served at /sw.js)
  app.json      expo config incl. `version` (shown as an on-screen badge)
  app.config.js injects git commit into expo `extra` at build time
api/index.py    Vercel Python entry: adds backend/ to sys.path, imports app.main:app
vercel.json     single project: static web + /api/* serverless; cache headers
docs/           ARCHITECTURE.md, DEPLOYMENT.md
```

## How it's deployed (important context)
- **Single Vercel project**: Expo web static export + FastAPI as a Python
  serverless function at `/api/*` (same origin, no CORS needed in prod).
- **DB**: Supabase Postgres via the transaction pooler; `NullPool` on serverless.
- **Cron**: Supabase **pg_cron** hits `POST /api/internal/tick` every minute
  (serverless has no long-lived scheduler). The tick evaluates due running
  agents **and** volatility alert watches.
- **Vercel Deployment Protection is ON**: the whole app+API is gated behind
  Vercel auth, so it is not publicly reachable and endpoints can't be probed
  unauthenticated from outside the team. This is a project setting, not code.
- The Supabase project visible via MCP is **not** the app's runtime DB — do not
  assume you can read/migrate prod from here. Schema changes must self-apply
  (see below).

## Schema changes (no Alembic)
`init_db()` runs on every startup: `create_all()` (creates missing **tables**)
plus `_ensure_columns()` — idempotent `ALTER TABLE … ADD COLUMN IF NOT EXISTS`
for columns added to **existing** tables (create_all never adds columns). So:
- New table → just define the model; `create_all` makes it on next deploy.
- New column on an existing table → add the model field **and** an entry in
  `database.py::_ADDED_COLUMNS` (postgres + sqlite DDL). Otherwise prod 500s.

## Commands (run from the right dir — the shell keeps cwd between calls)
```
# Backend tests (fast, authoritative):
cd backend && python -m pytest -q
# Frontend typecheck + web build (both must pass before shipping):
cd mobile && npx tsc --noEmit
cd mobile && npx expo export --platform web --clear
```
CI (`.github/workflows/ci.yml`) runs these on every PR, but run them locally
before pushing too — they are the gate.

## Ship workflow (this repo's established pattern)
1. Work on branch `claude/crypto-trading-bot-app-ht4bhj`.
2. Bump `mobile/app.json` `version` (the badge is how the user confirms a fresh
   build vs. a cached one).
3. Because PRs are **squash-merged**, the branch diverges after each merge.
   Before a new change: `git fetch origin main && git checkout -B <branch>
   origin/main` (stash/pop local edits). Then commit, `git push -u
   --force-with-lease`, open a PR, squash-merge.
4. After merge, verify the Vercel prod deploy is READY (Vercel MCP
   `list_deployments`), and for backend/schema changes check `get_runtime_logs`
   for 5xx / errors. A frontend-only change: confirm READY + badge version.

## Conventions / gotchas
- **Layout**: wrap screen `ScrollView`s with `contentContainerStyle={screenContent}`
  (centered, max-width 980) and tile card lists with `<CardGrid>`.
- **Secrets never leave the server**: exchange keys are Fernet-encrypted at rest
  and never returned by the API (`has_credentials` boolean only).
- **Strategies** are pure `decide(ctx) -> StrategyDecision`; execution + risk
  overlays live in `runner.py` + `risk.py`. Add a strategy: new class in
  `technical.py`, register in `registry.py` (`_REGISTRY` + `available_strategies`
  with `kind/difficulty/best_for/avoid_when`), add the `StrategyType` enum.
- **Coinbase** keys can be ECDSA (stock ccxt) or Ed25519 (custom EdDSA signer in
  `coinbase_ed25519.py`). Don't "simplify" that away.
- **Deferred MCP tools** (github, Vercel, Supabase): load via ToolSearch
  `select:<name>` before calling.
- Known open issues and priorities live in `TODO.md`; the rationale/critique is
  in `docs/REVIEW.md`. Read those before proposing large changes.

## Do-not-break list
- The `_ensure_columns` DDL list and `create_all` on startup.
- Same-origin `/api/*` routing + the SPA rewrite in `vercel.json` (static files
  like `/sw.js`, `/_expo/*` must still be served, not rewritten).
- The internal tick's defensive try/except around agent runs and watch eval.
