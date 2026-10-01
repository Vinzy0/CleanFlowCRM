# Tavo Automation & Integrations

Implementation status: **Tavo-side functionality verified locally with offline providers. Make A/B and Google Calendar NOT VERIFIED.** The user confirmed no Make/Google credentials are available. No production services were changed. Do not claim real Make, Zapier, n8n, Sheets, or Calendar experience from this milestone alone.

## Architecture

Tavo remains a single-business CRM. All normal users are trusted business owners and share non-demo leads, as in the existing CRM. Integration configuration belongs to the owner who creates it; another owner's session cannot inspect/revoke it. This is not tenant isolation or a multi-business platform. Every key grants scoped access to the same business workspace, never synthetic demo records.

```text
Owner session → /api/integrations → scoped key / encrypted webhook destination
External event → X-API-Key + Idempotency-Key → /api/v1/leads
                                            ↓ shared validated lead services
                       lead/activity + event + delivery + request snapshot
                                            ↓ one database transaction
                            existing AI classification + owner notification

CRM/public inquiry/email services → event outbox → delivery worker → HTTPS receiver
                                                  ↓ attempt/status/backoff
                                         Integrations UI → inspect / queue retry
```

The business transaction persists its event and subscribed deliveries. No network request occurs inside the event transaction. Events use immutable JSON bytes, UUID event IDs, schema version 1, and unique event/destination pairs. Activities record external creation, notes and workflow changes. Lead detail shows this owner's delivery history.

Classification and owner email keep the established synchronous processing path; they are not new background jobs. An interrupted create can leave a stored lead without completed AI processing. The existing authenticated lead-page AI retry repairs that state. A duplicate external create never spends on AI or repeats notification. Its stored response is the **creation snapshot**, so GET the lead for current analysis/stage. Email events retain `sandboxed: true` when captured locally; email.sent is provider acceptance or sandbox capture, never an inbox guarantee.

## Configuration and development

Install updated backend requirements and apply migration **0004**, which adds six integration tables and source/tags/next_action/next_follow_up/appointment_at to leads. Tags default to an empty JSON list so existing leads survive the upgrade. API and worker must use the same database and Fernet encryption key.

New settings:

| Variable | Purpose |
| --- | --- |
| `INTEGRATION_ENCRYPTION_KEY` | Fernet key for webhook URL and signing-secret encryption. Required for destination registration/delivery. Separate from JWT secret. |
| `RATE_LIMIT_INTEGRATION` | External API requests per address; default 120. |
| `RATE_LIMIT_INTEGRATION_WINDOW_SECONDS` | Window; default 60 seconds. |

Generate the encryption key directly into the git-ignored root `.env`, without printing it. Run this from `api/` with its virtualenv Python (skip when already configured):

```python
from pathlib import Path
from cryptography.fernet import Fernet
from dotenv import dotenv_values
path = Path('../.env')
if not dotenv_values(path).get('INTEGRATION_ENCRYPTION_KEY'):
    with path.open('a', encoding='utf-8') as file:
        file.write('\nINTEGRATION_ENCRYPTION_KEY=' + Fernet.generate_key().decode() + '\n')
```

Keep a protected backup of that key with the database backup. Changing it without re-encrypting existing rows makes destinations unreadable. No rotation tool is implemented; remove/register destinations if replacing it intentionally. Never paste credentials into source, screenshots, query examples, or logs.

Use an isolated development database, `DEMO_MODE=false`, and `EMAIL_TRANSPORT=log`. The known old Resend credential is not needed and must not be used. An actual AI run needs your own development OpenRouter credential; unit tests replace both AI and email. The public production demo has demo mode on, so it deliberately cannot run these integrations.

Run API and frontend using the existing README instructions. In a third terminal, from `api/`, run:

```bash
python -m app.webhook_worker          # polls due deliveries every two seconds
python -m app.webhook_worker --once   # bounded one-batch operator run
```

The UI's Process queued deliveries is a development/operator alternative: it processes up to five due deliveries for the current owner. Automatic retries require a running worker (or repeated operator dispatch). Nothing deploys or schedules the worker automatically. A future authorized hosted rollout needs a separate worker process/job with the same settings, not a second database or microservice.

## API authentication and endpoints

Sign in as an owner, open `/crm/integrations`, and generate a key with `leads:read` and/or `leads:write`. The full random credential is returned once and stored only as a SHA-256 digest plus a display prefix. Revocation is immediate on subsequent authentication. Use HTTPS for remote callers.

External authentication is `X-API-Key`; normal bearer sessions do not authenticate `/api/v1`. API keys cannot authenticate the CRM, send customer emails, generate drafts, delete leads, or manage integrations. Demo mode disables the external API and integration settings for all accounts; demo users are always prohibited. API key owners converted to demo are rejected.

| Method / path | Permission | Result |
| --- | --- | --- |
| `GET /api/v1/leads?after_id=0&limit=50` | read | Ascending ID cursor; maximum 100 records |
| `GET /api/v1/leads/{id}` | read | Current lead, latest analysis and activity timeline |
| `POST /api/v1/leads` | write | Create and process lead; returns saved creation snapshot |
| `PATCH /api/v1/leads/{id}` | write | Supported customer and workflow fields |
| `PATCH /api/v1/leads/{id}/stage` | write | Validated pipeline stage and timeline/event |
| `POST /api/v1/leads/{id}/notes` | write | Add an integration-labelled activity note |

Every external write requires a stable `Idempotency-Key`, 8–64 characters using letters, numbers, `.`, `_`, `:`, or `-`. Reuse the source event ID for network retries. The identity is scoped to the credential across all write endpoints; reuse with another method/path/payload returns 409. Matching retries return the original response. A unique database reservation prevents concurrent duplicate work. Failed validation/rolled-back transactions can be corrected and retried. Idempotency snapshots are retained; do not reuse tokens for unrelated future events. Switching credentials changes the namespace.

Use environment-held secrets in your HTTP client, without logging the headers. Example request body (synthetic data, no public-form `inquiry_key`):

```json
{
  "name": "Morgan Lee",
  "email": "morgan@example.com",
  "phone": "+1 555 0100",
  "service_type": "Deep Cleaning",
  "property_type": "House",
  "preferred_date": "2026-10-05",
  "message": "Please clean the kitchen and bedrooms next week.",
  "source": "Make custom webhook",
  "tags": ["website", "automation-demo"]
}
```

Fetch `/api/config` for available services, property types and stages. Writes reject unsupported fields, invalid categories and invalid stages. Patch workflow example:

```json
{
  "next_action": "Call to confirm the quote",
  "next_follow_up": "2026-10-04T10:00:00+08:00",
  "appointment_at": "2026-10-05T09:00:00+08:00",
  "tags": ["website", "quoted"]
}
```

Times require a timezone offset and are normalized to UTC. `null` clears source, next_action, next_follow_up and appointment_at; required customer fields cannot be cleared. Tags: maximum 20 unique nonempty labels, each at most 40 characters. Stage body: `{"stage":"Booked"}`. Note body: `{"note":"Called; customer requested a quote."}`. Assignment/routing was intentionally deferred: no assignment model or `lead.assigned` event is claimed.

Common errors: 401 invalid/revoked credential; 403 scope/demo restrictions; 404 missing/synthetic record; 409 conflicting idempotency token; 422 invalid payload/header; 429 rate limit with Retry-After. Session-only configuration APIs: GET `/api/integrations`; POST/DELETE `/api/integrations/keys`; POST/PATCH/DELETE `/api/integrations/webhooks`; GET `/api/integrations/deliveries` (optional lead_id); POST `/api/integrations/deliveries/{id}/retry`; POST `/api/integrations/dispatch`. OpenAPI is available at `/docs`.

## Webhook schema and signing

Register before creating events; subscriptions do not replay older events. Supported: `lead.created`, `lead.classified`, `lead.stage_changed`, `appointment.booked`, `email.sent`, `email.failed`. A stage change alone is not an appointment. Setting/changing an actual appointment time emits appointment.booked; clearing it does not. Unchanged stages/times and repeated requests do not emit duplicates. Changing subscriptions affects future events; previously queued snapshots keep their original subscription.

```json
{
  "id": "a UUID event ID",
  "type": "lead.created",
  "schema_version": 1,
  "occurred_at": "2026-09-30T12:00:00+00:00",
  "data": {"lead": {"id": 123, "name": "Morgan Lee", "pipeline_stage": "New"}}
}
```

The abbreviated example omits other LeadRead fields; the actual `data.lead` is a complete lead snapshot. Classification includes category/priority/reused, stage events include from/to, email events include activity_id/email_type/sandboxed/reason. Events contain customer data: send only to trusted destinations and retain according to your business policy.

Headers:

```text
Content-Type: application/json
X-Tavo-Event-Id: <event UUID>
Idempotency-Key: <same event UUID>
X-Tavo-Signature: t=<Unix seconds>,v1=<hex HMAC-SHA256>
```

HMAC input is UTF-8 timestamp + literal `.` + **raw request bytes**. Verify before parsing or modifying JSON, reject timestamps outside five minutes, use a constant-time comparison, then persist/dedupe event IDs before business actions. `api/app/webhook_verify.py` contains a tested Python reference verifier. The signing secret is shown once on registration; destination URLs (which may contain tokens) and signing secrets are encrypted. The UI exposes only the destination hostname, not the full URL.

## Delivery reliability and security

Delivery statuses: pending, sending, succeeded, failed, cancelled. Each attempt persists before the HTTP request, then records HTTP status (if available), safe result/failure category, start/end times and attempt number. Only a real sender returning 2xx results in succeeded. Tests inject fakes explicitly. Redirects are failures and are never followed. Receiver response bodies and raw exception text are not stored.

Socket/connect/TLS timeout: 10 seconds per blocking operation. DNS uses the OS resolver timeout. HTTPS port 443 only; embedded user/password and fragments are rejected. Every attempt rejects nonpublic or mixed public/private DNS answers and pins the checked IP while retaining original-host TLS verification/SNI. Proxy environment settings are not used. Private IP/localhost receivers are unsupported by design.

Automatic attempts: at most five, with delays of 30, 60, 120, 240 seconds after failures. This applies to timeouts and all non-2xx responses. An owner can queue a failed attempt immediately, including one waiting for backoff. A successful/cancelled/sending delivery cannot be retried. Manual retry preserves event ID/body and increments the lifetime attempt count; after attempt five, another failure stops until an explicit manual retry.

Atomic database claims prevent concurrent senders. Sending claims expire after five minutes; a later worker detects an interrupted attempt, marks it failed with **receiver outcome unknown**, and leaves manual recovery to the owner. A late response from an expired attempt cannot overwrite recovery or a newer attempt's result. Check the receiver first. No exactly-once or strict event-ordering guarantee exists; receiver dedupe is essential because network failure can follow successful downstream work. Removed endpoints cancel queued/failed deliveries and erase their encrypted credential while preserving logs. A send already in flight cannot be recalled.

Missing encryption/configuration never becomes a fake success. Lead creation is independent of receiver availability. Database failures roll back the corresponding business transaction; external network failures stay in the outbox. Existing AI/email failure behavior remains visible. API keys do not expire automatically; revoke unused credentials. Integration rate limiting retains the existing single-process/shared-proxy limitation. Outbox/attempt/request data has no automatic retention cleanup; schedule policy-based maintenance before a larger client deployment.

## Local PostgreSQL verification

The default `python -m pytest -q` suite stays offline with SQLite and fake AI/email/HTTP providers. To repeat it against PostgreSQL, set **test-only** `TAVO_TEST_POSTGRES_URL` to a `postgresql+psycopg` URL for a dedicated database whose name starts with `tavo_test_`, hosted on localhost. Supply its password through your local environment without printing it or committing it. The test account needs permission to create/drop schemas. Do not use an application database.

Each API test creates a random isolated schema and drops it afterward. The optional PostgreSQL migration test exercises fresh upgrade, Alembic check, downgrade to 0003, synthetic populated upgrade/tag backfill, and another drift check. Without that setting, the PostgreSQL-specific case is skipped. The runtime test still mocks external providers and does not establish live Make or AI-provider verification.

## Verification and portfolio wording

See [verification record](VERIFICATION.md) for exact local checks and [Make setup](MAKE_WORKFLOWS.md) for live acceptance steps. [Desktop](evidence/integrations-desktop.jpg) and [mobile](evidence/integrations-mobile.jpg) images use a synthetic database and an **Offline receiver (mock)**. They prove presentation, not live delivery.

Honest current claim: “I built a custom CRM with scoped external APIs, signed webhooks, persisted delivery attempts and retries, and AI lead processing. It supports HTTP/webhook automation tools; live Make workflows still require verification.”

Only after both Make scenarios meet their evidence checklist may the claim include real Make workflows. Zapier and n8n are compatible with this HTTP/JSON design; no platform execution or professional experience is claimed.
