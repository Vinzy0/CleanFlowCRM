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
| 3 — AI | DeepSeek structured categories/priority, stored summary and rationale, draft reply | Fixed labels, rule-based priority, persisted analysis, editable suggested reply. Test structured parsing and failure state. |
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
