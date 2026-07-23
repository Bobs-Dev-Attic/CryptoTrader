# Deployment (Vercel + Supabase, git auto-deploy)

This project deploys as a **single Vercel project from the repo root**, backed by
a **Supabase Postgres** database. The one project serves the Expo web app as
static files **and** the FastAPI backend at `/api/*` (same origin), so there's no
second project, no `EXPO_PUBLIC_API_URL`, and no CORS to configure. Every push to
`main` auto-deploys.

```
GitHub (main)
   └── ONE Vercel project (repo root)
         ├── web:  cd mobile && expo export  →  mobile/dist   (static, served at /)
         └── api:  api/index.py (ASGI)        →  /api/*        (Python serverless + Cron)
                        └── DATABASE_URL ───────────────────► Supabase Postgres
```

How it fits together (all already in the repo):
- Root `vercel.json` builds the web app, routes `/api/*` to the Python function,
  everything else to the SPA, and declares the cron.
- `api/index.py` is the ASGI entrypoint; it bundles `backend/**` (via
  `functions.includeFiles`) and serves the FastAPI app.
- The web client calls the API at its **own origin** under `/api/*`
  (`getBaseUrl()` in `mobile/src/api.ts`), so no API URL needs configuring.

---

## 1. Database (Supabase) — already provisioned

A project named **`cryptotrader`** is provisioned (region `us-east-1`, ref
`wjqbouylzsijrlkynfsa`), the schema is applied, and Row Level Security is enabled
on every table. You only need its **connection string**:

1. Supabase dashboard → project **cryptotrader** → **Connect** (top bar).
2. **Connection string → URI**, and pick the **Transaction pooler** (the IPv4
   "Shared Pooler" — required because Vercel functions are IPv4-only and the
   direct `db.<ref>.supabase.co` host is IPv6-only).
3. If it shows `[YOUR-PASSWORD]`, reset it under **Settings → Database → Reset
   database password** and paste the new password in.

Result (this is your `DATABASE_URL`):

```
postgresql://postgres.wjqbouylzsijrlkynfsa:<password>@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require
```

> **Why it's already secure:** the backend connects as the `postgres` role, which
> owns the tables and bypasses RLS — while the enabled RLS blocks the anon
> Supabase REST API. The schema is pre-created, so no migration runs on boot.

## 2. Configure the single Vercel project

The repo is already imported as the **`crypto-trader`** project (repo-root). All
that's left is adding environment variables:

**Settings → Environment Variables** (Production), then **Redeploy**:

| Name | Value |
| --- | --- |
| `DATABASE_URL` | the Supabase URI from step 1 |
| `JWT_SECRET` | a long random string |
| `ENCRYPTION_KEY` | a Fernet key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `INTERNAL_CRON_SECRET` | a long random string |
| `CRON_SECRET` | **same value** as `INTERNAL_CRON_SECRET` (Vercel Cron sends it as a Bearer token) |
| `ANTHROPIC_API_KEY` | optional — enables LLM agents |

After it redeploys:
- `https://<your-app>.vercel.app/health` → `{"status":"ok"}`
- `https://<your-app>.vercel.app/` → the app; register and create a paper agent.

> No `EXPO_PUBLIC_API_URL` and no `CORS_ORIGINS` are needed — the web app and API
> share one origin. (`CORS_ORIGINS` defaults to `*`, which is harmless since the
> app uses Bearer tokens, not cookies.)

### Troubleshooting
- **404 at `/`** → the deployment built the empty repo root without the root
  `vercel.json`. Push to `main` / hit **Redeploy** so the build picks it up.
- **`/api/...` returns 500** → check **Runtime Logs**; almost always a missing or
  wrong `DATABASE_URL` (must be the **pooler** URI, not `db.<ref>.supabase.co`).
- **Login shows "Can't reach the API … localhost"** → you're on an old web build;
  redeploy so the same-origin default takes effect.
- **A merge to `main` didn't auto-deploy** → occasionally a push webhook is
  missed. Push any commit, or use the Vercel dashboard's **Redeploy** on the
  latest commit, to build it.

## 4. Scheduling the agent tick

Running agents are evaluated by calling `GET|POST /api/internal/tick`, guarded by
`INTERNAL_CRON_SECRET`.

> **Why not Vercel Cron?** Vercel's **Hobby** plan only allows **once-per-day**
> cron jobs — an every-minute cron makes the deploy fail. So the root
> `vercel.json` ships **without** a cron; use Supabase pg_cron below (works on any
> plan and gives minute-level ticks). If you're on Vercel **Pro**, you can instead
> add `"crons": [{ "path": "/api/internal/tick", "schedule": "* * * * *" }]` back
> to `vercel.json`.

### Supabase pg_cron (recommended, minute-level on any plan)
In the Supabase SQL editor for the **cryptotrader** project, replacing the URL
with your deployment and the secret with your `INTERNAL_CRON_SECRET`:

```sql
create extension if not exists pg_cron;
create extension if not exists pg_net;

select cron.schedule(
  'cryptotrader-tick',
  '* * * * *',
  $$
  select net.http_post(
    url     := 'https://crypto-trader-alpha-lime.vercel.app/api/internal/tick',
    headers := jsonb_build_object('x-cron-secret', '<INTERNAL_CRON_SECRET>')
  );
  $$
);
```

## 5. Auto-deploy on every update

Once the project is imported from GitHub, **every push/merge to `main` triggers a
fresh production deploy** — no further action needed. Feature branches get
preview deployments automatically. (If a push is ever missed, use **Redeploy** in
the dashboard.)

---

## Local development (unchanged)

Locally the app uses SQLite and an in-process APScheduler (no cron needed):

```bash
# backend
cd backend && uvicorn app.main:app --reload --port 8000
# app
cd mobile && npm install && npm run web
```

The backend detects serverless environments (the `VERCEL` env var) and disables
the in-process scheduler there, relying on the cron tick instead.

## Notes & caveats

- **ccxt bundle size**: the backend function pulls `ccxt`, which is sizeable but
  within Vercel's function size limit. If you hit the limit, trim `ccxt` to the
  specific exchanges or move the backend to a container host (a `Dockerfile`
  path is a straightforward alternative).
- **Cold starts**: the first request after idle re-creates the DB session and
  ensures tables exist; expect a short delay.
- **Secrets**: never commit `.env`. `ENCRYPTION_KEY` is now safe to *introduce*
  (via `MultiFernet` the legacy JWT-derived key stays a decrypt fallback), but
  once set, *rotating it away* still requires re-encrypting stored credentials.

## Enabling production security enforcement

By default the backend runs with warnings-only. To make it **fail closed** on
insecure config (recommended before real users / public access):

1. Generate two independent secrets:
   ```
   # JWT signing secret
   python -c "import secrets; print(secrets.token_hex(32))"
   # Fernet key for encrypting exchange API credentials at rest
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
2. In **Vercel → Project → Settings → Environment Variables** (scope: **Production**),
   add — **secrets first**:
   - `JWT_SECRET` = the token_hex value
   - `ENCRYPTION_KEY` = the Fernet value
   - *(only after the two above)* `ENVIRONMENT` = `production`

   Or via the Vercel CLI:
   ```
   vercel env add JWT_SECRET production
   vercel env add ENCRYPTION_KEY production
   vercel env add ENVIRONMENT production      # value: production — do this LAST
   ```
3. Redeploy (pushing to `main`, or Vercel → Deployments → Redeploy).

**Ordering matters.** With `ENVIRONMENT=production` set, the app **refuses to
start** if `JWT_SECRET` is default/unset or `ENCRYPTION_KEY` is unset
(`app/main.py` → `config.security_warnings()`). Set the secrets first so the
next boot is already valid. Because of the MultiFernet fallback, adding
`ENCRYPTION_KEY` does **not** disturb already-stored exchange connections —
existing ciphertext keeps decrypting, new writes use the strong key.

> Changing `JWT_SECRET` invalidates existing login sessions (users re-login);
> it does not affect stored exchange credentials.
