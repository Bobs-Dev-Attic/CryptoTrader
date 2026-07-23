# AGENTS.md

Canonical agent guide is **[CLAUDE.md](./CLAUDE.md)** — read it first (repo map,
commands, deploy model, schema-change rules, ship workflow). This file repeats
only the highest-leverage rules so Codex doesn't have to rediscover them.

## The 60-second version
- Monorepo: `backend/` (FastAPI + SQLAlchemy, Python 3.11), `mobile/` (Expo /
  React Native web+native), deployed as **one Vercel project** (static web +
  `/api/*` Python serverless) against **Supabase Postgres**. A **pg_cron** job
  hits `POST /api/internal/tick` every minute to run agents + evaluate alerts.

## Gate before shipping (CI runs these on every PR — run them locally too)
```
cd backend && python -m pytest -q
cd mobile && npx tsc --noEmit
cd mobile && npx expo export --platform web --clear
```
The shell keeps its working directory between commands — `cd` deliberately.

## Ship workflow
Branch `claude/crypto-trading-bot-app-ht4bhj`; bump `mobile/app.json` `version`;
PRs are **squash-merged**, so re-base the branch on `origin/main`
(`git checkout -B <branch> origin/main`) before starting new work; push with
`--force-with-lease`; verify the Vercel prod deploy is READY after merge.

## Traps that cause prod 500s or wasted cycles
- **Schema**: `create_all` makes new *tables* but not new *columns*. Adding a
  column to an existing table requires an entry in
  `backend/app/database.py::_ADDED_COLUMNS` (self-applied ALTER on startup).
- The MCP-visible Supabase project is **not** the runtime DB; migrations must
  self-apply, not be run by hand.
- Vercel **Deployment Protection** gates the app — you cannot probe endpoints
  unauthenticated from outside; verify via Vercel MCP logs, not curl.
- Exchange secrets are Fernet-encrypted and never returned by the API.

## Where to look
- Open issues, prioritized: **[TODO.md](./TODO.md)**
- Full multi-perspective critique: **[docs/REVIEW.md](./docs/REVIEW.md)**
- System design: **[docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)**
