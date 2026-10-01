# Tavo live staging verification — 2026-10-01

**The milestone is partially verified. Scenario A passed; Scenario B is blocked at Google OAuth consent. The full portfolio claim has not been upgraded. Calendar is optional.**

## Authorized staging deployment

- Branch: `feature/automation-integrations`; deployed application commit `bf88f6323baf5e47b922a74e8f28b6b143f76e04`.
- API: [cleanflow-api-staging](https://cleanflow-api-staging.onrender.com/api/health), Render Free Docker service. It uses the separate staging Neon PostgreSQL 18.6 database, migrated to revision `0004`; hosted Alembic check passes.
- Frontend: [tavo-web-staging](https://tavo-web-staging.onrender.com), new Render Free Node service. Node 22.16.0; root `web`; build `npm ci && npm run build`; start `npm run start -- --hostname 0.0.0.0 --port $PORT`.
- Staging Docker override: `python -m app.staging_server`. It runs migrations/bootstrap, starts Uvicorn and the outbox worker, restarts an exited worker, and terminates children on shutdown. The production Docker command is unchanged. Free instances can sleep, so worker availability is not continuous.
- Configured staging settings: existing database/JWT/OpenRouter settings; `DEMO_MODE=false`; `EMAIL_TRANSPORT=log`; `EMAIL_LOG_PATH=/tmp/tavo-staging-outbox.jsonl`; cleared demo recipient override; `INTEGRATION_ENCRYPTION_KEY`; integration rate limit 120/60 seconds; `FRONTEND_ORIGIN` and `CRM_PUBLIC_URL` set to the staging frontend. Frontend `API_URL` points to the staging API. No credential values are published.
- A dedicated normal staging owner signs into the CRM. Scoped external API authentication works; invalid and revoked keys return 401. CORS accepts the staging frontend and rejects an unrelated origin.

## Scenario A — VERIFIED

Make scenario: **Tavo A - Make intake to CRM and AI (staging)**, ID `6468861`.

Flow: authenticated Make custom webhook → HTTP POST to Tavo with `X-API-Key` and stable `Idempotency-Key` → Tavo persistence and actual OpenRouter classification → webhook response. Current analysis is verified separately through Tavo's external GET and owner CRM.

- Source event: `tavo-live-f54eccf1-b27a-4f0d-95af-64d827a14133`.
- Make creation execution: `8dbf698db71542119b2b3f454998a0cb`, started `2026-10-01T06:38:08.439Z`, 3 operations, 14.894 seconds. Intake and HTTP processing completed; this early run carried a response-module scheduling warning.
- Tavo saved creation response: HTTP 201, lead **4**. The first Make endpoint acknowledgment was 200 Accepted; it alone is not treated as proof.
- Real AI model: `deepseek/deepseek-v4.1-flash`; analysis stored `2026-10-01T06:38:18.318749Z`; Commercial Cleaning, high priority, with persisted rationale and matched rules. Email activity is sandbox capture, not a live send.
- The owner CRM displays the saved lead, tags/source, classification and activity timeline after navigation/refresh.
- Final duplicate Make replay execution `7d811af25bb748089d3cee5ab50e9090` succeeded without warnings, 3 operations, 4.374 seconds, started `2026-10-01T06:59:32.007Z`. The webhook returned HTTP 201 and the original lead ID. Database checks confirm the same lead, exactly one AI analysis and one lead.created event; no second lead was inserted.
- An initial mapping attempt failed before lead creation; it was corrected. Earlier creation/replay completed the intake and HTTP operations but warned because the blueprint omitted instant execution metadata. That setting is corrected (`metadata.scenario.instant=true`; Scenario A can process in parallel because Tavo enforces idempotency). The final replay passed cleanly. Mapped text now uses Make's documented `escapeJSON` function.

[Machine-readable evidence](evidence/make-a-live.json) · [CRM screenshot](evidence/make-a-crm.jpg) · [Clean Make run](evidence/make-a-run.jpg)

## Scenario B — NOT VERIFIED

Make scenario: **Tavo B - CRM events to Google Sheets (staging)**, ID `6468884`, **inactive**. A custom webhook is configured with request headers and raw JSON pass-through. Tavo has an encrypted lead.created destination registered, named **Make Google Sheets - awaiting OAuth**; no new lead has been generated after registration. No delivery, receiver HMAC acceptance, downstream action, Sheets row, or successful full Scenario B run is claimed.

Google sign-in reached the additional OAuth consent screen. The pending selection is **Sheets only**; broad Drive access remains unchecked. Final Continue has not been clicked because this new data-access grant requires action-time approval. No Google Sheets connection has been verified and no spreadsheet has been created. A temporary receiver path was replaced after appearing on a canvas; the old Make hook was removed, and the fresh URL/signing secret remain private. Reload the Scenario B editor after consent before finishing its modules, so it uses the current saved receiver.

After consent: verify the connection, create a synthetic verification spreadsheet, use a manually specified spreadsheet ID if Drive browsing is unavailable, finish receiver HMAC/timestamp checks and durable event dedupe, configure Search/Add/Update Row, and put the success response after the actual row action. Then create a new lead via A, verify the matching Tavo event/attempt, Make run and actual Sheet row, and replay the event without a duplicate row. Keep this scenario inactive until those modules are configured. The complete setup contract remains in [MAKE_WORKFLOWS.md](MAKE_WORKFLOWS.md).

## Resend rotation — VERIFIED

The old **Onboarding** sending key and a discarded replacement are revoked. The final replacement **Tavo sending key — 2026-10-01 replacement** has sending-only access. Render production `tavo-api` persisted the replacement value, restarted the existing master baseline, and its health endpoint returns 200. Production feature code was not deployed.

An authenticated call using the replacement key returned HTTP 200 for Resend's delivered test sink, email ID `01a0f621-c51c-723c-8c03-c2a218748d40`, at `2026-10-01T06:23:23.253366Z`. This proves provider acceptance, not delivery to a human inbox. A replacement appeared in a tool log and was revoked before using the final unexposed replacement. Credentials are excluded from Git, exports and evidence. [Sanitized provider receipt](evidence/resend-rotation.json).

## Verification and limits

- Latest offline backend suite: **99 passed, 1 optional PostgreSQL case skipped**; all previous cases included. Previously completed isolated PostgreSQL 17.11 suite: **100 passed**, including fresh/populated migration, backfill, downgrade/upgrade and Alembic drift checks.
- Latest frontend typecheck and production build pass; the staging Render build/start also passed. An upstream Starlette deprecation warning and harmless Next.js notice about an ignored parent-directory lockfile remain.
- Real staging health, owner login, API-key auth/revocation, encrypted webhook registration and hosted migration/drift check pass. Staging email remains offline; Resend rotation was tested independently against its safe provider sink.
- Live outbound signatures/delivery/retries and Google Sheets remain unverified; offline sender/signature/retry tests still pass. A registered receiver or 2xx acknowledgment does not establish a downstream action.
- Zapier and n8n are compatible with the documented HTTP/webhook contract only. No separate execution or professional platform experience is claimed. Calendar was not executed and is not required for this milestone.
- Keep the complete two-scenario portfolio statement gated until Scenario B and the actual Sheet row are verified.
