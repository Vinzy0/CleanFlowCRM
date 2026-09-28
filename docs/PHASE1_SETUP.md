# Phase 1 local setup and PostgreSQL verification

This phase provides the public inquiry form, owner authentication, a protected lead list, and lead CRUD endpoints. The [implementation plan](IMPLEMENTATION_PLAN.md) assigns AI and email to later phases.

## Requirements

- Python 3.11+ and Node 20+
- PostgreSQL 17 or compatible PostgreSQL server
- Docker Compose is optional and runs PostgreSQL plus the API together.

## Option A: Docker Compose for database and API

From the project root, copy `.env.example` to `.env`. Replace `JWT_SECRET` with a random string of at least 32 characters. Keep `POSTGRES_PASSWORD` and the password inside `DATABASE_URL` equal; URL-encode reserved characters in the URL password.

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
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m app.create_user owner@example.com 'Business Owner'
.\.venv\Scripts\uvicorn.exe app.main:app --reload
```

Set the URL to your actual PostgreSQL database and credentials. The app reads environment variables; copying `api/.env.example` alone does not load them into the shell.

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
