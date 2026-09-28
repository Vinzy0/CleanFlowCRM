# CleanFlow CRM implementation plan

Source of truth: [PRD.md](PRD.md). This plan records delivery order and verification; it does not add features.

## Repository inspection (2026-09-28)

- The supplied Codex task directory contained no repository or application files.
- No existing CleanFlow/cleaning CRM project was found under Documents.
- This new project starts in `C:\Users\VINZ\Documents\CleanFlow CRM`.
- Node 24 and Python 3.11 are available. Docker and `psql` are not installed, so PostgreSQL integration cannot be run locally until a server or container runtime is available.

## Architecture

- `web/`: Next.js App Router with TypeScript. Server actions submit forms to the backend and keep the auth token in an HTTP-only cookie.
- `api/`: FastAPI, Pydantic validation, SQLAlchemy ORM, Alembic migrations, PostgreSQL through psycopg, Argon2 password hashes and signed expiring JWTs.
- `api/business.py`: cleaning-specific configuration for name, stages, service categories, and lead field choices. This stays a small configuration object, not a CRM builder.
- The public inquiry path is a single backend lead-creation operation. Later demo simulation will reuse that operation and add AI/notification steps.

## Phase map and acceptance criteria

| Phase | Deliverable | PRD acceptance criteria and verification |
| --- | --- | --- |
| 1 — Foundation | Authentication, schema/migration, lead CRUD, public inquiry form, protected CRM shell | User logs in/out; inquiry creates a lead; lead persists in PostgreSQL. Verify unauthorized reads fail, invalid inquiries fail, duplicate form retries do not create another lead, and created lead can be fetched. |
| 2 — Core CRM | Dashboard counts/recent leads, pipeline, lead detail, status updates, activity timeline | Lead appears in pipeline; owner changes status; detail page and history exist. Test each stage transition and activity entry. |
| 3 — AI | DeepSeek 4.1 through OpenRouter: structured categories/priority, stored summary and rationale, draft reply | Fixed labels, rule-based priority, persisted analysis, editable suggested reply. Mock the provider in tests; test structured parsing and failure state. |
| 4 — Automation | Resend owner notification, human-approved customer email, failure/retry | Owner notified; email only after human approval; failed attempts logged and retryable. |
| 5 — Demo Mode | Simulated fake inquiry, demo-safe AI/email, rate limits, reset | Visitor can simulate; AI use limited; arbitrary email blocked; reset restores fake data. |
| 6 — Polish | Responsive/loading/error states, deployment, README, video | Public HTTPS app, setup instructions, 60–90 second video, full definition-of-done sequence. |

## Phase 1 implementation order

1. Create backend package, configuration, typed models, migration, and user bootstrap command.
2. Add login and protected lead CRUD endpoints. Keep public creation separate from protected reads and updates.
3. Add Next.js login, public inquiry page, authenticated CRM shell and lead list. Phase 2 will supply dashboard, pipeline, detail, and status controls.
4. Add focused backend checks for validation, auth, lead persistence, idempotency, and CRUD, then run frontend type/build checks.

## Phase 1 boundary

The inquiry form stores a lead. AI processing and owner notification are not claimed as implemented in Phase 1; those are Phase 3 and 4 work. The activity and AI tables can be migrated now without exposing unfinished workflows. Public deployment waits for Phase 5 safety controls.

## Phase 1 progress (2026-09-28)

- Implemented: authentication and logout, protected CRM lead list, public inquiry form, lead CRUD API, configuration, PostgreSQL schema and Alembic migration, duplicate submission key, initial `lead_created` activity.
- Verified: backend flow test passed; Alembic migration and schema check passed against a temporary SQLite database; Next.js typecheck and production build passed; a browser smoke check saved a fake inquiry, displayed it after sign-in, signed out, and rejected unauthenticated CRM access.
- Pending external verification: run the migration and persistence flow on PostgreSQL. No PostgreSQL server, Docker, or `psql` is available on this machine.

## Phase 1 audit and checkpoint (2026-09-28)

- Fixed whitespace-only inquiry text passing validation, duplicate-key retries after a staff edit, lost form values after failed submission, misleading login/API outage messages, and an unusable inquiry form when service configuration is unavailable.
- Added a local API Docker image, health-gated PostgreSQL Compose service, environment examples, and an exact PostgreSQL persistence check in [PHASE1_SETUP.md](PHASE1_SETUP.md).
- Rechecked the API test, migration/schema check, TypeScript, production build, and browser flow from failed validation through successful inquiry, login, sign-out, and protected-route redirect. PostgreSQL execution remains pending because the required runtime is absent.
- Git checkpoint: `5d496f1` (`Complete Phase 1 foundation and audit`).

## Phase 2 progress (2026-09-28)

- Implemented: dashboard counts and recent leads; four-stage Kanban-style pipeline with the PRD-approved status dropdown; complete lead detail; authenticated status endpoint; chronological activity timeline. The existing AI analysis table and a nullable detail response reserve the Phase 3 data shape without generating or displaying fake AI output.
- Status changes update the lead and add a `status_changed` activity in one database transaction. Dashboard and pipeline pages read the current persisted state; a successful change refreshes their routes.
- Verified in the browser: login → dashboard → pipeline → lead detail → change to Contacted → activity entry → pipeline placement → dashboard count → reload persistence. A second update from the pipeline moved the lead to Booked. Desktop and mobile layouts were inspected.
- Before Phase 3: run the documented PostgreSQL/Compose verification when its runtime is available, then implement only the PRD's constrained classification, stored summary/rationale, and human-reviewed draft reply. Owner notification remains Phase 4.

## Phase 3 progress (2026-09-28)

- The production AI gateway is OpenRouter. Backend-only `OPENROUTER_API_KEY` authenticates requests; `OPENROUTER_MODEL` defaults to the currently listed DeepSeek V4.1 Flash slug, `deepseek/deepseek-v4.1-flash`.
- Business logic calls a small AI provider interface. The OpenRouter adapter owns the endpoint, transport, structured-response request, and credentials. Tests replace the provider and never use a live key.
- Inquiry creation commits the lead before requesting AI analysis. Structured output is checked against configured service categories, priority labels, and priority rules, then summary/rationale and model ID are stored. Failed analysis keeps the lead and a failed activity; the lead page offers an authenticated retry. Draft replies are generated on request, recorded in activity, and shown in an editable text area without sending email.
- Verified: seven backend tests with a fake provider or mock HTTP transport; TypeScript check; production web build; fresh SQLite migration and Alembic schema check. A local browser inquiry and lead-detail smoke test displayed a stored classification through OpenRouter because the local API process inherited an existing key. Live draft generation and PostgreSQL/Compose remain unverified.
- Owner notification and email sending remain Phase 4. Public demo rate limits and paid AI controls remain Phase 5; the app is still for local development.

## OpenRouter credential verification (2026-09-28)

- The project-local, ignored `.env` supplies the backend key and DeepSeek V4.1 Flash model for direct FastAPI runs. The secret is absent from tracked files and frontend assets.
- A manual live call using that project key returned a valid structured classification and draft reply. The first structured attempt returned invalid JSON; the adapter now requests a larger response budget and OpenRouter's response-healing plugin. The mocked backend suite still makes no live requests.
- A local browser check using fake data then completed inquiry submission → saved lead → displayed AI analysis → generated editable draft reply → recorded `ai_classified` and `reply_generated` activities. The test used the project key through the backend. PostgreSQL/Compose remains unverified.
