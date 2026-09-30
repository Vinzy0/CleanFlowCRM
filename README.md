# Tavo

**Automation & Integrations milestone (local branch):** scoped external API keys, a versioned lead API, signed persistent webhooks with delivery logs/retries, an owner Integrations area, and source/tags/follow-up/appointment fields. See [integration architecture and API](docs/INTEGRATIONS.md) and [Make setup and evidence requirements](docs/MAKE_WORKFLOWS.md). The public deployment below is the previous baseline; this milestone has not been deployed. **Live Make A/B and Google Calendar are NOT VERIFIED** because credentials were unavailable. Zapier/n8n are compatible with the HTTP contract; no executed workflows or experience are claimed.

A working CRM and inquiry-automation demo built for a **fictional cleaning business**. Tavo is the software product; Acme Cleaning Services is the sample business. This is a portfolio piece that can be tailored to another service business.

**Live demo:** [Open Tavo](https://tavo-web-6d8p.onrender.com) · [API health](https://tavo-api.onrender.com/api/health). The full synthetic inquiry workflow has passed on the public deployment with Neon PostgreSQL, OpenRouter, and Resend's safe test address. See [verification](docs/VERIFICATION.md) for the exact checks and limits.

---

## The business problem

A small cleaning business loses leads in a manual loop: an inquiry arrives by email or phone, someone retypes it somewhere, decides by feel how urgent it is, and may or may not remember to follow up.

Tavo turns that into one pipeline:

```text
Customer submits inquiry          (public form, validated)
        ↓
Lead saved in the database        (plus a lead_created activity)
        ↓
AI classifies the inquiry         (service category from a fixed list)
AI picks a priority               (high only when a listed rule matches)
AI writes a short summary         (stored bullets + rationale)
        ↓
Owner gets an email notification  (customer, service, priority, CRM link)
        ↓
Lead appears in the pipeline      (New → Contacted → Booked → Completed)
        ↓
Owner opens the lead, changes status, reads the AI analysis
        ↓
AI drafts a suggested reply       (stored, never sent)
        ↓
Owner reviews and edits it, then presses Send   ← the only path to an email
        ↓
Resend delivers the email when configured; the sandbox captures it locally
```

Two product rules shape the whole build:

- **Classification is constrained.** The model may only use the configured service categories and priority rules; anything else is rejected and the lead stays saved with a retry available.
- **AI never sends anything.** Drafting an AI reply cannot send an email. A human approves every outbound customer message, and the recipient is always the lead's own address.

Cleaning is the first-class implementation. `api/app/business.py` holds a small configuration layer (business name, stages, service categories, property types, priority rules) so a future client customization is a config change plus deep work in the workflow — **not** a generic CRM builder, and not a HubSpot replacement.

---

## Architecture

| Layer | Choice | Notes |
| --- | --- | --- |
| Frontend | Next.js (App Router) + TypeScript | Server components read the CRM; server actions perform writes. The session token stays in an HTTP-only cookie and never reaches the browser. |
| Backend | FastAPI + Pydantic + SQLAlchemy | Validation, business rules, AI and email orchestration, activity logging. |
| Database | PostgreSQL via Alembic migrations | SQLite is supported for local development and tests only. |
| AI | OpenRouter → `deepseek/deepseek-v4.1-flash` | Structured JSON-schema output; provider isolated behind a small interface. |
| Email | Resend | Backend-only; plus a `log` sandbox transport for local/demo runs. |

```text
repository/
├─ api/                    FastAPI backend
│  ├─ app/
│  │  ├─ main.py           HTTP routes (thin)
│  │  ├─ leads.py          lead pipeline: create, classify, status, demo seed/reset
│  │  ├─ ai.py             AI provider boundary + constrained classification schema
│  │  ├─ email.py          Resend adapter + sandbox transport
│  │  ├─ email_flow.py     tracked sends, owner notification, idempotency
│  │  ├─ demo.py           fixed synthetic demo scenarios
│  │  ├─ ratelimit.py      per-address limits for demo safety
│  │  ├─ business.py       business configuration layer
│  │  ├─ models.py         SQLAlchemy models
│  │  ├─ schemas.py        request/response validation
│  │  ├─ auth.py           Argon2 password hashing + signed session tokens
│  │  └─ settings.py       environment handling
│  ├─ alembic/             migrations (0001 foundation, 0002 automation/demo, 0003 demo-user isolation)
│  └─ tests/               pytest suite, fully offline
├─ web/                    Next.js frontend
│  ├─ app/                 public pages (/ , /inquiry, /login) and the CRM
│  └─ lib/                 API client, formatting, notice messages
├─ compose.yaml            PostgreSQL + API containers
├─ render.yaml              Reviewable hosted demo configuration (not deployed)
└─ docs/                   PRD, plan, setup, verification notes
```

---

## Getting started

Prerequisites: Python 3.11+, Node 20+, and either Docker (for PostgreSQL) or nothing at all (SQLite is fine for a look around).

### 1. Backend

```bash
cd api
python -m venv .venv
./.venv/Scripts/python -m pip install -r requirements-dev.txt     # Windows
# source .venv/bin/activate && pip install -r requirements-dev.txt # macOS/Linux
```

Create the environment file (never commit it):

```bash
cp ../.env.example ../.env      # then edit ../.env
```

Set at minimum:

```ini
DATABASE_URL=postgresql+psycopg://cleanflow:replace-with-local-password@localhost:5432/cleanflow
JWT_SECRET=<at least 32 characters>
OPENROUTER_API_KEY=<your key>
```

The backend reads the repository-root `.env` for local JWT and email settings when process variables are absent. The AI adapter prefers the project `.env` key over an inherited machine key. `DATABASE_URL` must be set in the process environment for direct runs.

Apply migrations and create the first user:

```bash
export DATABASE_URL="postgresql+psycopg://cleanflow:replace-with-local-password@localhost:5432/cleanflow"
./.venv/Scripts/python -m alembic upgrade head
./.venv/Scripts/python -m app.create_user owner@example.com "Owner Name"   # prompts for a password
./.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd web
npm install
cp .env.example .env.local       # API_URL=http://127.0.0.1:8000
npm run dev                      # http://localhost:3000
```

Then open `/inquiry` to submit a request, and `/login` to reach the CRM.

### SQLite quick start (no Docker)

```bash
cd api
export DATABASE_URL="sqlite:///./cleanflow.db"
./.venv/Scripts/python -m alembic upgrade head
./.venv/Scripts/python -m app.create_user owner@example.com "Owner"
./.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

SQLite is for local development and the offline test suite. Claiming the PRD's PostgreSQL requirement satisfied requires the real database — see below.

### PostgreSQL with Docker Compose

```bash
cp .env.example .env             # set POSTGRES_PASSWORD, DATABASE_URL, JWT_SECRET
docker compose up --build
docker compose exec api python -m app.create_user owner@example.com "Owner"
docker compose exec api python -m app.create_user --demo demo@example.com "Public Demo"
```

The API container runs `alembic upgrade head` before starting. The database is health-gated, so the API waits for PostgreSQL.

---

## Environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | yes | SQLAlchemy URL. PostgreSQL in production; SQLite locally. |
| `JWT_SECRET` | yes | Signs session tokens. Minimum 32 characters. |
| `OPENROUTER_API_KEY` | for AI | Backend-only key. Without it the app still works; AI states show as failed with a retry. |
| `OPENROUTER_MODEL` | no | Defaults to `deepseek/deepseek-v4.1-flash`. |
| `OPENROUTER_MAX_ATTEMPTS` | no | Defaults to `2` and is capped at `2` (one retry). Set `1` to disable the retry. |
| `RESEND_API_KEY` | for email | Backend-only key. |
| `EMAIL_FROM` | for email | Verified sender, e.g. `Acme Cleaning Services <no-reply@yourdomain>` |
| `OWNER_NOTIFICATION_EMAIL` | for email | Where new-lead notifications go. Missing → the attempt is recorded as failed, not silently dropped. |
| `EMAIL_TRANSPORT` | no | `resend` (default) or `log` (sandbox sink for local/demo runs). |
| `EMAIL_LOG_PATH` | no | Where the sandbox transport writes JSON-lines messages. |
| `CRM_PUBLIC_URL` | no | Base URL used in the notification's "Open in the CRM" link; wired to the web service URL on Render. |
| `FRONTEND_ORIGIN` | hosted | Exact public frontend origin allowed by API CORS; wired by the Render Blueprint. |
| `DEMO_MODE` | no | `true` enables the simulate/reset endpoints and the demo panel. |
| `DEMO_EMAIL_OVERRIDE` | demo | Safe destination for all demo messages. The Blueprint uses Resend's `delivered@resend.dev` test address. Required before demo mode sends anything. |
| `DEMO_REUSE_AI_RESULTS` | no | Defaults to `true`: identical fixed scenarios reuse a stored result instead of paying again. |
| `RATE_LIMIT_*` | no | Per-bucket limits: `INQUIRY`, `SIMULATE`, `CLASSIFY`, `DRAFT`, `EMAIL`, `LOGIN`, `RESET`, each with an optional `_WINDOW_SECONDS`. |
| `TRUST_PROXY_HEADERS` | no | Leave `false` unless a trusted proxy overwrites `X-Forwarded-For`. |
| `API_URL` (web) | hosted | Public backend base URL for the Next.js server; wired by the Render Blueprint. |
| `DEMO_LOGIN_EMAIL` / `DEMO_LOGIN_PASSWORD` (API and web) | demo | Server-side only. The API creates or updates the restricted demo account on startup; the web uses the same values for one-click entry. |

---

## Migrations

```bash
cd api
./.venv/Scripts/python -m alembic upgrade head      # apply
./.venv/Scripts/python -m alembic downgrade -1      # step back
./.venv/Scripts/python -m alembic check             # detect model/schema drift
./.venv/Scripts/python -m alembic revision --autogenerate -m "message"
```

`alembic check` is the guard that the models and the migration history agree.

---

## Running the tests

```bash
cd api
./.venv/Scripts/python -m pytest -q
```

The suite is **fully offline**: AI and email providers are replaced by fakes, and no test needs OpenRouter, Resend, a network connection or a paid key. Coverage includes authentication and authorization, lead creation and validation, status changes and the activity timeline, AI structured output (valid, invalid, category and priority constraints, failure keeping the lead, retry), draft replies never sending, owner notification success/failure/missing configuration, explicit customer sends, duplicate-send protection, retry after failure, demo simulation and reset, fake-data-only rules, rate limits, recipient tampering rejection and demo email redirection.

Frontend checks:

```bash
cd web
npm run typecheck     # tsc --noEmit
npm run build
```

---

## AI configuration

Classification asks for a JSON-schema-constrained object and validates it again with Pydantic: the service category must be one of the configured services, the priority must be `high` or `normal`, every matched rule must come from the configured rule list, and `high` must agree with at least one matched rule. Anything else is rejected — the lead is kept and the failure is visible in the timeline with a retry button.

Two provider quirks are handled deliberately:

- **Reasoning tokens share the completion budget.** A budget that is too small returns an *empty* completion with `finish_reason: "length"`. The structured call therefore asks for 4000 tokens and the draft for 2000.
- **Responses are occasionally unusable.** Empty or unparsable answers are retried once, with a doubled budget, before the classification is marked failed. HTTP and configuration errors are never retried.

## Email configuration

Outbound email is backend-only. Recipients are never taken from a request body:

- **Owner notification** — sent after AI analysis, containing the customer, service, priority, preferred date and a CRM link. Wrapped so an email failure can never prevent lead creation; a failure is recorded as an `email_failed` activity with a reason and a retry endpoint.
- **Customer reply** — only from `POST /api/leads/{id}/send-email`, which accepts a subject and body and always targets the lead's own address. Draft generation stores text and nothing else.
- **Duplicate protection** — each email is one activity row behind a unique idempotency key. Repeating the same subject/body to the same lead address returns `duplicate: true`; changing the text or correcting the lead address permits a new send. A pending send cannot start a second provider call. Resend also receives an idempotency key for retries. Failed sends are retried in place with an attempt counter. Identical text cannot be intentionally resent to the same address; this is the MVP boundary. A process crash during a pending send requires checking the provider before manually clearing that state.
- **Sandbox transport** — `EMAIL_TRANSPORT=log` writes messages to a JSON-lines file instead of delivering them. It is a development/demo convenience; production uses Resend.

---

## Demo mode

Enable with `DEMO_MODE=true`. It adds a prominent **Simulate new inquiry** action (dashboard and pipeline) and **Reset demo data**.

- **Simulate** picks one of six fixed fake scenarios and runs it through the *same* pipeline the public form uses: lead created, AI classified, notification sent, lead shown in the CRM. Nothing bypasses the real code path.
- **Public inquiries are closed while demo mode is on.** The `/inquiry` page points visitors to the synthetic workflow, and `POST /api/leads` rejects direct submissions. Turn demo mode off to accept real customer inquiries.
- **Reset** deletes demo records only (`lead.is_demo`) and reseeds a populated workspace: five synthetic leads spread across all four stages, each with AI analysis and an activity history.
- **Fake data only** — every scenario uses `@example.com` addresses and `555` numbers, validated at import so the pool cannot drift.
- **AI cost control** — per-address limits, a fixed scenario pool, and reuse of an already-stored result for an identical scenario on the same day, so repeated resets do not re-pay for the same classification.
- **Email safety** — with demo mode on and no `DEMO_EMAIL_OVERRIDE`, the backend refuses to send *anything*. With an override set, every recipient is rewritten to that inbox, the record stores both the intended and delivered address, and only demo leads can be emailed at all.
- **Authentication and isolation** — CRM pages stay behind the session cookie. The hosted API bootstraps a restricted demo account from `DEMO_LOGIN_EMAIL`/`DEMO_LOGIN_PASSWORD` after migrations. The backend filters the lead list and rejects every real-lead detail or mutation for demo users, even when they guess an ID. Demo users can change pipeline status but cannot edit customer fields or delete leads, and lose CRM access when demo mode is off. Existing demo accounts created before migration 0003 remain ordinary users until explicitly marked `is_demo=true`; bootstrap refuses to convert them automatically.
- **Rate limits** — sign-in, public inquiries, simulation, AI calls, drafts, emails and resets have in-process per-address counters, with clear messages and a `Retry-After` header. Next.js server actions may appear to the API as one server address, so deploy as one API instance and verify the forwarded client address at the trusted proxy before claiming per-visitor limits. The shared bucket conservatively caps AI spend but can throttle visitors together.

---

## API

```text
GET    /api/config                      public business + demo configuration
POST   /api/auth/login                  sign in (rate limited)
GET    /api/auth/me                     current user
POST   /api/leads                       public inquiry → lead (rate limited; closed in demo mode)
GET    /api/leads                       list leads                (auth)
GET    /api/leads/{id}                  lead detail + activities + analysis (auth)
PATCH  /api/leads/{id}                  update lead fields        (auth)
PATCH  /api/leads/{id}/status           change pipeline stage     (auth)
DELETE /api/leads/{id}                  delete a lead             (auth)
POST   /api/leads/{id}/classify         retry AI analysis         (auth, rate limited)
POST   /api/leads/{id}/draft-reply      generate a draft (never sends) (auth, rate limited)
POST   /api/leads/{id}/send-email       owner-approved send       (auth, rate limited)
POST   /api/leads/{id}/notify-owner     retry the owner notification (auth, rate limited)
POST   /api/demo/simulate-inquiry       create a fake lead        (auth, demo mode, rate limited)
POST   /api/demo/reset                  restore the demo state    (auth, demo mode, rate limited)
```

## Data model

```text
users         id, email, password_hash, name, is_demo, created_at
leads         id, inquiry_key, inquiry_fingerprint, name, email, phone, service_type,
              property_type, preferred_date, message, pipeline_stage, priority,
              is_demo, demo_scenario, created_at, updated_at
ai_analyses   id, lead_id, service_category, priority, summary, matched_priority_rules,
              classification_rationale, model, created_at
activities    id, lead_id, type, status, content (JSON), idempotency_key, created_at
```

Activity types: `lead_created`, `status_changed`, `ai_classified`, `reply_generated`, `email_sent`, `email_failed`.

---

## Security notes

- Secrets live in environment variables / the git-ignored `.env`; no key is exposed to the browser or committed.
- Passwords use Argon2; sessions are signed, expiring tokens in an HTTP-only cookie.
- All CRM endpoints require authentication; demo users can access only synthetic leads; all public input is validated; database access goes through the ORM.
- Email recipients are server-determined; the send endpoint rejects unknown fields outright.
- Failure paths are visible rather than silent: AI and email failures are stored with a reason and offer a retry.
- Rate-limit counters live in process memory. A multi-instance deployment needs a shared limiter; a single-instance portfolio demo can use the current implementation after proxy-address verification.

## Known limitations

- **Render Free services sleep when idle.** The first page or API request after a cold start can take around a minute. Docker was not run locally; its deployed image passed the hosted workflow.
- **The demo uses Resend's test destination.** Hosted owner notifications and a human-approved reply were accepted for `delivered@resend.dev`; no customer address was contacted.
- **Resend acceptance is not inbox delivery.** The API records a provider receipt as sent; downstream delivery and bounce handling are outside this MVP. The `log` transport reports captured, not delivered.
- **Usage is shared on Free tiers.** The in-memory rate limiter may group visitors behind the frontend service, and AI/email calls consume provider quotas.
- Drag-and-drop was deliberately not built; the PRD's approved status dropdown is used instead.

Exact remaining verification steps, with commands, are in [docs/VERIFICATION.md](docs/VERIFICATION.md).

## Documentation

- [PRD](docs/PRD.md) — the source of truth for scope
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md) — phase map and per-phase verification notes
- [Local setup detail](docs/PHASE1_SETUP.md) — environment walkthrough
- [Remaining verification](docs/VERIFICATION.md) — what still needs real infrastructure
- [Free deployment plan](docs/DEPLOYMENT.md) — Render Free web services, Neon Free database, and Resend test delivery
