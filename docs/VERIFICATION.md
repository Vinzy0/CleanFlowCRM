# Remaining verification

The items below have not been verified or delivered. Docker and a PostgreSQL server are unavailable locally; live Resend delivery, hosting, HTTPS and a real-device UI pass were not exercised.

Last updated: 2026-09-28, after the final local audit.

## Verified in the final local audit

- 53 backend tests passed with mocked AI/email providers; one dependency deprecation warning remains.
- Frontend `npm run typecheck` and `npm run build` passed. No lint script is configured.
- A fresh SQLite database upgraded through migration 0003, passed `alembic check`, downgraded to base, and upgraded to head again.
- A local browser smoke pass on a temporary database confirmed demo login, dashboard and pipeline rendering at a narrow viewport, status persistence, lead activity, sign-out, and the protected-route redirect. It made no paid AI calls or real email sends. This is not real-device validation.
- Static review and PostgreSQL-dialect offline SQL generation for migrations 0001–0003 found no likely type/default/JSON incompatibility. This is not a PostgreSQL run.

## 1. Real PostgreSQL

Everything database-related so far was verified on SQLite (fresh migration, schema drift check, the whole test suite and the local smoke run). What still needs a real server:

```bash
# with Docker
cp .env.example .env                     # set POSTGRES_PASSWORD, DATABASE_URL, JWT_SECRET
docker compose up --build
docker compose exec api python -m app.create_user owner@example.com "Owner"
# then in another shell
curl -s localhost:8000/api/config

# with an existing PostgreSQL instead of Docker
cd api
export DATABASE_URL="postgresql+psycopg://cleanflow:replace-with-local-password@localhost:5432/cleanflow"
./.venv/Scripts/python -m alembic upgrade head
./.venv/Scripts/python -m alembic check
./.venv/Scripts/python -m app.create_user owner@example.com "Owner"
```

Then confirm on PostgreSQL specifically:

1. `alembic upgrade head` applies 0001, 0002 and 0003 cleanly, and `alembic check` reports no drift.
2. An inquiry submitted through `/inquiry` is committed and readable after a restart.
3. The pending → sent/failed transition on `activities.idempotency_key` behaves with a real unique constraint, including repeated sends and a pending concurrent request.
4. `DELETE /api/leads/{id}` removes the lead's analyses and activities (cascade).
5. Dashboard counts and pipeline grouping match the rows in the database.
6. The demo account sees only `is_demo=true` rows, including on direct lead-ID requests.

SQLite-specific caveats worth re-testing on PostgreSQL: JSON column behaviour, `Boolean` server default, and multiple `NULL` values in the unique `idempotency_key` index.

## 2. Live Resend delivery

**No email was sent through Resend in this audit.** To verify live delivery:

```ini
EMAIL_TRANSPORT=resend
RESEND_API_KEY=<key>
EMAIL_FROM=Acme Cleaning Services <no-reply@your-verified-domain>
OWNER_NOTIFICATION_EMAIL=<a mailbox you control>
```

Then confirm:

1. Submitting an inquiry delivers the owner notification, and the lead's timeline shows `email_sent` (not `email_failed`).
2. Clicking **Send email** on a lead delivers the reply, and the timeline shows the customer-reply email.
3. A deliberately broken key produces `email_failed` with a readable reason and a working retry — the lead is never lost.
4. Clicking Send twice with unchanged content does **not** deliver twice.
5. Check provider delivery/bounce status separately from its accepted-send receipt. If a process stops with an email activity in `pending`, reconcile it with Resend before manually retrying.

## 3. Public deployment

The PRD's deployment requirements (HTTPS, environment variables, production PostgreSQL, logs, secrets outside the source) are unimplemented. Before deploying:

1. Provision the API and frontend hosts plus a managed PostgreSQL instance.
2. Set every variable in `README.md` on the host — `JWT_SECRET`, `DATABASE_URL`, `OPENROUTER_API_KEY`, `RESEND_API_KEY`, `EMAIL_FROM`, `OWNER_NOTIFICATION_EMAIL`, `CRM_PUBLIC_URL`, `API_URL`.
3. Run `alembic upgrade head` against the production database, then create the owner and demo accounts. Create the demo account with `python -m app.create_user --demo demo@example.com "Public Demo"`; set matching `DEMO_LOGIN_EMAIL` and `DEMO_LOGIN_PASSWORD` on the web host. If a demo account already exists from before migration 0003, explicitly set only that user's `is_demo` column to true before exposing its credentials.
4. Decide the demo configuration. For a public demo, set `DEMO_MODE=true` and `DEMO_EMAIL_OVERRIDE` to an inbox you control; `EMAIL_TRANSPORT=log` avoids delivery entirely but writes to the host filesystem.
5. Keep the API to one instance for this portfolio demo. Verify the address seen by the API from Next.js server actions; otherwise visitors share one conservative bucket. Set `TRUST_PROXY_HEADERS=true` **only** if the platform's proxy overwrites `X-Forwarded-For` and direct clients cannot spoof it. A multi-instance deployment needs a shared limiter.
6. Seed the demo state with `POST /api/demo/reset` once, so a first-time visitor sees a populated workspace.
7. Re-run the smoke journey against the deployed URL: sign in → simulate → change status → draft → send (redirected) → reload.
8. Verify a demo token cannot list, open, change, email, or delete a real lead by guessing its ID.

## 4. Demo video and portfolio assets

The PRD's 60–90 second video and the live "Try Live Demo" link do not exist yet. The interface is ready for the sequence the PRD describes (simulate → lead appears → AI analysis → pipeline move → draft → send).

## 5. Deliberately not built

Confirmed out of scope for the MVP, and untouched: SMS, WhatsApp, Twilio, payments, invoicing, calendar booking, chatbot, RAG, autonomous agents, multi-organization support, enterprise RBAC, marketing automation, complex analytics, drag-and-drop, a generic CRM builder.
