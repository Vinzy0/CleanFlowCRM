# Local setup and PostgreSQL verification

The app provides inquiries, owner authentication, the CRM, and Phase 3 AI classification and draft replies. Owner notification and customer email sending are later phases; see the [implementation plan](IMPLEMENTATION_PLAN.md).

## Requirements

- Python 3.11+ and Node 20+
- PostgreSQL 17 or compatible PostgreSQL server
- Docker Compose is optional and runs PostgreSQL plus the API together.

## Option A: Docker Compose for database and API

From the project root, copy `.env.example` to `.env`. Replace `JWT_SECRET` with a random string of at least 32 characters. Keep `POSTGRES_PASSWORD` and the password inside `DATABASE_URL` equal; URL-encode reserved characters in the URL password. Set `OPENROUTER_API_KEY` in this backend Compose environment to enable AI. `OPENROUTER_MODEL` defaults to `deepseek/deepseek-v4.1-flash` and can be changed without editing application code.

```powershell
Copy-Item .env.example .env
docker compose config
docker compose up --build -d db api
docker compose exec api python -m app.create_user owner@example.com 'Business Owner'
```

The API service waits for a healthy database and applies Alembic migrations before serving on `http://127.0.0.1:8000`. The sample Compose file is for local development. For production, provide `DATABASE_URL` and `JWT_SECRET` as deployment secrets, use a managed PostgreSQL URL (with SSL when required), and run `alembic upgrade head` as a deployment step.

## Option B: existing PostgreSQL server and local Python API

From `api/`:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:DATABASE_URL = 'postgresql+psycopg://cleanflow:<password>@localhost:5432/cleanflow'
$env:JWT_SECRET = '<random-secret-at-least-32-characters>'
$env:OPENROUTER_API_KEY = '<your-openrouter-key>'
$env:OPENROUTER_MODEL = 'deepseek/deepseek-v4.1-flash'
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m app.create_user owner@example.com 'Business Owner'
.\.venv\Scripts\uvicorn.exe app.main:app --reload
```

Set the URL to your actual PostgreSQL database and credentials. The app reads environment variables; copying `api/.env.example` alone does not load them into the shell.

## AI gateway and local behavior

All AI requests originate from the FastAPI backend and go to OpenRouter. Keep `OPENROUTER_API_KEY` in backend environment variables or the project root's untracked `.env` file; never put it in `web/.env.local` or a `NEXT_PUBLIC_` variable. For direct local FastAPI runs, the backend reads the root `.env` key and model before inherited machine settings. Production containers receive both through their backend environment. If `OPENROUTER_MODEL` is unset, the DeepSeek V4.1 Flash slug is the default. The backend-only endpoint and model routing live in `api/app/ai.py`.

Creating an inquiry stores the lead first, then requests structured classification. If OpenRouter is not configured or a request fails, the lead remains saved with a failed `ai_classified` activity; an authenticated owner can retry from the lead detail page. Draft replies are stored as activity entries and shown in an editable text area. They are **never sent** by Phase 3. Keep this build local until the public demo AI limits and rate limiting in Phase 5 are implemented.

Backend tests inject a fake AI provider and an HTTP mock transport. They neither need a key nor send live OpenRouter requests. The live OpenRouter workflow and PostgreSQL/Compose deployment can be checked separately when those services are available.

## Web frontend

In another terminal, from `web/`:

```powershell
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Open `http://localhost:3000`. Submit a fake inquiry, then sign in with the owner account to see the protected CRM.

## Exact remaining PostgreSQL verification

When Docker or a PostgreSQL server is available, run `docker compose config`, `docker compose up --build -d db api`, and `docker compose exec api alembic check`. Then submit a fake inquiry through the web form, sign in, confirm it appears in the CRM, restart the containers with `docker compose restart`, and confirm the lead still appears. This verifies the migration, PostgreSQL persistence, and retained volume. The current machine has no Docker or `psql`, so this specific check has not run.

Other checks:

```powershell
cd api
.\.venv\Scripts\python.exe -m pytest -q
cd ..\web
npm run typecheck
npm run build
```
