# Deployment (Vercel + Supabase, git auto-deploy)

This project deploys as **two Vercel projects from the same repo** — the FastAPI
backend (Python serverless) and the Expo web app — backed by a **Supabase
Postgres** database. Once linked, every push to `main` auto-deploys both.

```
GitHub (main)
   ├── Vercel project "cryptotrader-api"   ── rootDir: backend/  ── Python serverless + Cron
   │        └── DATABASE_URL ─────────────────► Supabase Postgres
   └── Vercel project "cryptotrader-web"   ── rootDir: mobile/   ── Expo web static
            └── EXPO_PUBLIC_API_URL ──────────► the API project's URL
```

---

## 1. Provision the database (Supabase)

1. Create a Supabase project (any region). Wait for it to finish provisioning.
2. In **Project Settings → Database → Connection string**, copy the **URI**
   (looks like `postgresql://postgres:<password>@db.<ref>.supabase.co:5432/postgres`).
3. Keep it handy — it's the backend's `DATABASE_URL`.

> Tables are created automatically on the API's first cold start
> (`Base.metadata.create_all`). No manual migration is required to start.

## 2. Deploy the backend (Vercel project #1)

1. In Vercel: **Add New → Project → import the GitHub repo**.
2. Set **Root Directory** to `backend`.
3. Framework preset: **Other** (the included `backend/vercel.json` handles routing
   — all paths rewrite to the ASGI function in `backend/api/index.py`).
4. Add **Environment Variables**:

   | Name | Value |
   | --- | --- |
   | `DATABASE_URL` | the Supabase URI from step 1 |
   | `JWT_SECRET` | a long random string |
   | `ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
   | `INTERNAL_CRON_SECRET` | a long random string (see step 4) |
   | `CRON_SECRET` | **same value** as `INTERNAL_CRON_SECRET` (Vercel Cron sends this as a Bearer token) |
   | `ANTHROPIC_API_KEY` | optional — enables LLM agents |
   | `CORS_ORIGINS` | the web app's URL (set after step 3), or `*` while testing |

5. Deploy. Verify `https://<api>.vercel.app/health` returns `{"status":"ok"}`.

## 3. Deploy the web app (Vercel project #2)

1. **Add New → Project → import the same repo** again.
2. Set **Root Directory** to `mobile`.
3. The included `mobile/vercel.json` builds it with `expo export --platform web`
   (output `dist`, SPA rewrites).
4. Add **Environment Variable**:

   | Name | Value |
   | --- | --- |
   | `EXPO_PUBLIC_API_URL` | the backend URL from step 2, e.g. `https://cryptotrader-api.vercel.app` |

5. Deploy. Open the URL, register, and create a paper agent.
6. Go back to the API project and set `CORS_ORIGINS` to this web URL, then redeploy
   the API (or leave `*` for now).

## 4. Scheduling the agent tick

Running agents are evaluated by calling `POST|GET /api/internal/tick`, guarded by
`INTERNAL_CRON_SECRET`. Two options:

### Option A — Vercel Cron (already configured)
`backend/vercel.json` declares a cron on `/api/internal/tick` every minute. Vercel
automatically sends `Authorization: Bearer $CRON_SECRET`, which the endpoint
verifies.

> ⚠️ **Plan limits:** Vercel's **Hobby** plan runs cron jobs at most **once per
> day**. For minute-level evaluation you need the **Pro** plan, or use Option B.

### Option B — Supabase pg_cron (minute-level on any plan)
In the Supabase SQL editor:

```sql
create extension if not exists pg_cron;
create extension if not exists pg_net;

select cron.schedule(
  'cryptotrader-tick',
  '* * * * *',
  $$
  select net.http_post(
    url     := 'https://<api>.vercel.app/api/internal/tick',
    headers := jsonb_build_object('x-cron-secret', '<INTERNAL_CRON_SECRET>')
  );
  $$
);
```

## 5. Auto-deploy on every update

Once both projects are imported from GitHub, **every push/merge to `main`
triggers a fresh production deploy of each** — no further action needed. Feature
branches get preview deployments automatically.

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
- **Secrets**: never commit `.env`. Rotate `JWT_SECRET`/`ENCRYPTION_KEY` only with
  care — changing `ENCRYPTION_KEY` invalidates stored exchange credentials.
