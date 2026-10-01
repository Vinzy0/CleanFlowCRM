# Tavo verification record

## Automation & Integrations — 2026-10-01 local verification

Baseline cloned at `609776ae907aa8d2c8f961a9e29ee23d7861ed4c`, exactly matching the requested master baseline. README and this record were read before edits. Initial 59 backend tests, frontend typecheck and production build passed. Changes are on `feature/automation-integrations`; no production deployment, external service changes, secret rotation, or old Resend usage occurred.

- Backend default offline suite: **99 passed, 1 optional PostgreSQL case skipped**, in 53.03 seconds. The local PostgreSQL run: **100 passed**, in 107.24 seconds. Both include all 59 previous cases; one upstream Starlette/httpx deprecation warning remains. New coverage exercises hashed/revoked/scoped credentials, separate auth, creation/AI persistence, write idempotency, notes/stage/appointment workflows, subscriptions, transactional events, signatures/tampering/expiry, delivery status, non-2xx/timeout failures, backoff/manual retries, exhaustion, worker interruption, duplicate claims, encrypted config, missing configuration, authorization, demo blocking, URL and private DNS rejection. A new regression test proves an expired sender cannot overwrite recovery or a newer delivery attempt.
- SQLite and **local PostgreSQL 17.11** fresh upgrade through 0004, Alembic check, downgrade to 0003 then upgrade, and populated 0003 upgrade with lead preservation/tag backfill pass. PostgreSQL used portable binaries from the [official EDB archive page](https://www.enterprisedb.com/download-postgresql-binaries), a temporary SCRAM-authenticated cluster bound only to 127.0.0.1, and random per-test schemas. No persistent service was installed; the server was stopped afterward. All AI/email/webhook sender calls were mocked. PostgreSQL's session timezone exposed a response-format mismatch; lead timestamps now serialize consistently in UTC. Earlier Neon checks below concern the previous baseline only; the new migration has not been applied to hosted Neon.
- Frontend TypeScript and Next.js production build pass, including the new authenticated Integrations route. Browser QA uses a separate localhost database, fake AI/email and an explicitly named Offline receiver (mock). Desktop 1440×1000 and mobile 390×844 render checks show no horizontal overflow; delivery attempt history is visible. Screenshots in `docs/evidence/` are synthetic UI evidence, not real Make delivery evidence.
- Added configuration: INTEGRATION_ENCRYPTION_KEY, RATE_LIMIT_INTEGRATION, RATE_LIMIT_INTEGRATION_WINDOW_SECONDS. No credentials appear in the screenshots; destination paths/signing secrets are not listed by the API/UI.
- Make Scenario A: **NOT VERIFIED**, no credentials. Make Scenario B / Google Sheets: **NOT VERIFIED**, no credentials. Optional Google Calendar: **NOT VERIFIED**, documented recipe. Zapier/n8n: compatible design only, no executed workflow claim. Exact setup and acceptance evidence are in [MAKE_WORKFLOWS.md](MAKE_WORKFLOWS.md).

The historical hosted verification below remains a record of the previously deployed baseline, not a claim that these additions are deployed. A future rollout needs an authorized development environment, API/web migrations, encryption configuration and a running delivery worker before any production deployment.

Updated 2026-09-29. Public frontend: https://tavo-web-6d8p.onrender.com. Public API: https://tavo-api.onrender.com. Both run as Render Free web services backed by a separate Neon Free PostgreSQL 18 project in Singapore.

## Local checks

- Backend: 59 pytest cases pass with mocked AI/email providers. One dependency deprecation warning remains.
- Frontend: TypeScript typecheck and Next.js production build pass. The public pages and CRM routes build as dynamic server pages.
- Fresh SQLite migration and `alembic check` pass through revision 0003 after the deployment changes.
- Neon Free PostgreSQL 18 in Singapore: migrations and `alembic check` pass. A fake-provider smoke run passed database health, demo login, reset, simulated inquiry, classification, notification activity, stage update, draft without send, safe redirected send, duplicate suppression, and persistence in a new SQLAlchemy session. It made no OpenRouter or Resend network request.
- Tavo branding and demo indicator were checked in the local and hosted browser. Dashboard, pipeline, and lead detail were inspected at a 390 × 844 viewport.

## Hosted checks

- API `/api/health` returned 200 and `{"status":"ok"}` from the public URL. The Render Docker service ran Alembic migrations and bootstrapped the demo account. Leads persisted in Neon across local and hosted sessions and through browser refresh.
- The frontend loaded publicly; one-click demo login, dashboard, pipeline navigation, lead detail, and refresh worked. The public demo offered only synthetic inquiries, and a valid direct `POST /api/leads` returned 403.
- Hosted simulation created synthetic leads. OpenRouter classified them with `deepseek/deepseek-v4.1-flash`; the lead timeline recorded classification and owner notification. A stage change from New to Contacted persisted with an activity entry. An AI reply draft appeared without sending email.
- After explicit human approval in the UI, Resend accepted the reply for `delivered@resend.dev`; the page confirmed no customer email was sent. Sending the identical reply again returned a duplicate notice without another send. The owner notice also showed Sent.
- CORS preflight allowed exactly `https://tavo-web-6d8p.onrender.com`; an unrelated origin returned 400 with no allow-origin header. The hosted lead was usable at 390 × 844. The browser console showed no errors.
- The first simulation during initial rollout displayed a generic error after its lead was fully processed. A subsequent simulation completed with the expected success redirect. No repeat failure was observed. Render application logs showed no exception for the completed hosted flow; the transient cause was not confirmed.
- Demo isolation from non-demo records is covered by backend tests. The separate hosted Neon project contains only synthetic demo leads, so no real record was introduced solely to repeat that test on the public environment.

## Known limits

- Render Free web services sleep when idle and their local files are ephemeral; Neon stores persistent data.
- The rate limiter is in process memory and may group visitors behind the web server's address. One API instance is sufficient for this portfolio demo.
- No real customer email should be sent from the public demo. Resend test acceptance is not a delivery or bounce guarantee.
- A pending email after a process crash needs provider reconciliation before manual retry.
- The initial Resend API key appeared once in a tool readout during setup. Rotate it in Resend and update the Render `tavo-api` secret after the demo handoff.
