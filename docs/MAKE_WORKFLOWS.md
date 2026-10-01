# Make workflows: setup and live acceptance

**Scenario A and Scenario B / Google Sheets: VERIFIED. Calendar: optional, not executed.** On 2026-10-01, real Make scenario `6468861` created staging lead #5 and actual OpenRouter classification completed. Its signed lead.created event reached scenario `6468884`, which wrote eight matching fields to Google Sheets. Replaying intake retains one lead/analysis/event; replaying the outbound event returns `duplicate` and leaves the actual sheet unchanged. [Execution IDs, screenshots and exact evidence](STAGING_VERIFICATION.md).

## Prerequisites

Use a separate Tavo development workspace reachable over public HTTPS, with migrated database, normal owner login, `DEMO_MODE=false`, OpenRouter key, `EMAIL_TRANSPORT=log`, and the integration encryption key. Do not use the public production demo or a production database. The authorized staging API and frontend are now deployed to Render Free and separate Neon PostgreSQL 18.6. Staging explicitly runs `python -m app.staging_server`, which migrates the database and supervises the API and webhook worker. The old Resend key is revoked; staging email remains captured in the log transport.

In Tavo Integrations, generate a read/write API key. Store it in Make's HTTP API-key credential connection, using header name `X-API-Key`. Keep keys and webhook paths out of exported blueprints/screenshots. Make's current [HTTP documentation](https://apps.make.com/http) supports API-key credentials and recommends its dedicated credential field.

The executed Scenario A currently uses Make's legacy HTTP module with the key in its private header configuration, with confidential execution data enabled. Its intake webhook also requires `x-make-apikey`. The body uses `escapeJSON` for mapped strings and fixed synthetic verification tags. No credential-bearing blueprint is published. Prefer the current HTTP module's credential store for client deployments; exported legacy header configuration contains the key and must stay private. Earlier executions acknowledged the queue with `200 Accepted` and had a response-module scheduling warning. After setting instant execution and disabling sequential processing, the final duplicate replay returned 201 with the original lead ID and a clean Make run. Tavo's saved integration request, actual model analysis and CRM record establish creation/processing independently; a queue acknowledgment alone does not.

## Scenario A: Make → Tavo → AI

1. Create a scenario named **Tavo dev — intake to CRM**. Add **Webhooks / Custom webhook** and name it `tavo-dev-intake`. Use a separate webhook from Scenario B. Enable incoming request validation using a data structure if desired. Never expose its generated token URL in evidence.
2. Add **HTTP / Make a request**: POST `<TAVO_DEV_API>/api/v1/leads`; API-key credential from prerequisites; `Content-Type: application/json`; `Idempotency-Key` mapped to the trigger's stable `source_event_id`. Send a JSON body containing the remaining fields below. Do not regenerate the source event ID on retry. Set the HTTP timeout longer than the existing synchronous AI/email pipeline (for example 120 seconds); retries use the same idempotency token.
3. Add **HTTP / Make a request**: GET `<TAVO_DEV_API>/api/v1/leads/<created id>` using the same credential. The POST response is the saved creation snapshot; this GET shows current AI analysis and processing activities. If classification failed, inspect Tavo and use its existing owner retry before calling the scenario verified.
4. Run once. Send the synthetic payload below to the intake webhook using a trusted HTTP client. Save and activate only in the development account. Repeat with the same source_event_id; the stored lead ID must stay unchanged.

```json
{
  "source_event_id": "tavo-make-a-20260930-001",
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

Map source_event_id only to the header; it is not a Tavo lead field. Map tags as a JSON array using the HTTP body editor/data structure, preserving proper escaping. A Google Form source can replace the custom webhook when an authorized Google connection exists; the response's unique identifier must remain the request identity.

Acceptance proof required: actual Make execution ID/time, POST 201 and lead ID, GET with stored analysis/model, Tavo lead visible after refresh, duplicate replay producing the same ID and no second lead. An offline fake classification is not proof of a real OpenRouter run. Redact credentials and personal data from screenshots.

## Scenario B: Tavo → Make → Google Sheets

The executed scenario uses Google Sheets **Make an API Call** with a managed Google connection. This runs a real Sheets operation through Make; no direct Google credential or external substitute writes the row. Sheets-only OAuth is sufficient when using the spreadsheet ID and this API call. Drive access was not granted.

1. Add **Webhooks / Custom webhook**, enabling **Get request headers** and **JSON pass-through**. The exact raw JSON is `1.value`; headers are in `1.__IMTHEADERS__`. Register the private HTTPS receiver URL in Tavo and subscribe to `lead.created`. Save the one-time signing secret privately. [Webhook settings](https://apps.make.com/gateway).
2. **Tools / Set multiple variables** extracts `signature` and `header_event_id` using `get(map(1.__IMTHEADERS__; "value"; "name"; "x-tavo-signature"); 1)` and the same expression for `x-tavo-event-id`. Split the signature on comma, remove `t=` and `v1=`. Require a ten-digit timestamp within ±300 seconds and a 64-character digest.
3. **Tools / Set variable** builds `timestamp + "." + 1.value`. Its output is `4.value`, regardless of its displayed name. Verify `sha256(4.value; "hex"; signing_secret; "text")` equals the received digest before parsing or taking business actions. Invalid signatures, stale timestamps, tampered bytes and missing signatures return **401**. These cases were actually executed and rejected. The secret belongs in protected scenario configuration; never export the populated blueprint. [HMAC function](https://help.make.com/text-and-binary-functions#sha256).
4. **JSON / Parse JSON** reads the authenticated raw value. Validate `type == lead.created`, `schema_version == 1`, envelope ID matches the header, ID length 36, and a positive numeric lead ID within the configured sheet capacity (Tavo emits integer IDs). Authenticated malformed JSON returns **400**; unsupported events/identity/capacity return **422**. The deployed template has 1,000 rows and accepts lead IDs 1–999. Increase sheet capacity and update this guard before a larger deployment.
5. **Data store / Check the existence of a record** uses `event.id` as key. The actual output field is **`8.exist`**, not the displayed label “Exists.” An already completed event returns **200**, `{"event_id":"…","lead_id":5,"result":"duplicate"}`, without running Sheets again.
6. For a new event, **Google Sheets / Make an API Call** uses the managed Google connection. Its base is `https://sheets.googleapis.com/v4/`; relative URL `/spreadsheets/<SPREADSHEET_ID>/values/Leads!A<lead_id+1>:H<lead_id+1>`, method **PUT**, query `valueInputOption=RAW`, JSON body `{"values":[[event_id, lead_id, name, email, service_type, pipeline_stage, source, occurred_at]]}`. Use Make's `escapeJSON` for mapped strings. Initialize row 1 with headers `event_id, lead_id, name, email, service, stage, source, occurred_at`. Use the actual field **pipeline_stage**, not `stage`. [Sheets API module](https://apps.make.com/google-sheets-modules).
7. **Data store / Add or replace a record** saves event ID, lead ID, sheet range and completion time **after** the Sheets action succeeds. Then **Webhook response** returns 200 with `result=upserted`. Google/store failures have an error route returning **503**, followed by Ignore; this lets Tavo persist failure and retry. These live receiver failure routes are configured; the core sender's timeout/non-2xx/backoff/manual retry behavior is verified offline. A live Google outage/manual retry was not deliberately induced.
8. Enable instant execution and turn **sequential processing off** so the explicit final response reaches the original HTTP request. In this account, sequential mode returned default `200 Accepted` before downstream completion. Parallel deliveries are safe from duplicate rows because the row address derives from the stable lead ID. The data store skips already completed events; concurrent copies may both PUT the same immutable row. This is not a general exactly-once guarantee. Keep execution data confidential after synthetic evidence capture.

For lead #5 the actual range is `Leads!A6:H6`. Fixed row addressing prevents append duplication if a process crashes after Sheets succeeds but before recording completion. Blank rows for unused IDs are expected. This demonstration projects **lead.created snapshots** only; expanding subscriptions to stage/classification updates needs a separately designed update/ordering policy. Sorting/deleting these reserved rows changes the mapping and must be avoided. A production receiver should use an explicit stable row index or external-ID search/upsert appropriate to its volume.

Run a fresh lead through A only after the destination is registered and B is active. Match the Tavo event and actual HTTP attempt, Make input/execution, and actual Sheets export. Re-sign the same raw bytes with a current timestamp for replay; do not edit Tavo's delivery records. A default Make acknowledgment alone does not prove downstream success. Keep work within Tavo's ten-second socket timeout or expect retry. [Response behavior](https://help.make.com/webhooks).

The [sanitized blueprint template](examples/make-b-blueprint.template.json) preserves the tested modules/formulas but replaces the hook, Google connection, data structure/store IDs, spreadsheet ID and signing secret. Recreate those resources and set every placeholder before activation. Importing it alone does not produce a verified workflow. This reusable template contains no live credential or receiver URL.

## Optional Calendar recipe

The Tavo-side `appointment.booked` event is implemented and tested; a live Calendar scenario is not. After A and B work, register a separate Make destination/subscription, validate signature/dedupe as above, and use **Google Calendar / Create an Event**. Map the lead name and appointment_at, choose an explicit business timezone and duration (for example 60 minutes), and store the resulting Calendar event ID against the Tavo lead. Repeated event IDs must reuse that Calendar event; a later appointment change should update it. No cancellation event or appointment duration field is implemented. Verify the actual calendar entry and Tavo attempt before making a portfolio claim.

## Zapier and n8n

The design uses ordinary HTTPS JSON, `X-API-Key`, idempotency headers and signed webhook envelopes. Zapier **Webhooks / Custom Request** and **Catch Raw Hook**, and n8n **HTTP Request** and **Webhook**, can be configured for this contract. Receivers must verify raw bytes and dedupe event IDs. This is a compatibility statement, not proof that a workflow was built in either platform. Their actual configuration is **NOT VERIFIED**. [Zapier HTTP options](https://help.zapier.com/hc/en-us/articles/44391646192397-Ways-to-make-API-requests-in-Zapier), [n8n webhook reference](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/).

## Evidence ledger

| Item | Status | Evidence |
| --- | --- | --- |
| Tavo external creation + classification | VERIFIED offline | pytest fake-provider persisted-lead tests |
| Tavo outbound delivery + retries/HMAC | VERIFIED offline | injected sender, real persisted outbox and attempts |
| Make A live execution | VERIFIED | Lead #5, real model/CRM; creation `819b22d3e7544065aa5a1d3c77eb6b11`, clean replay `91095e28c37b4f71881a2fa18326f91f`, HTTP 201 |
| Make B reception + Sheets action | VERIFIED | Event `7077b785-79b2-44f6-89a7-bf87d7874798`; run `6583906d0a50454c9a388028cf8de1b2`; actual row A6:H6; unchanged duplicate replay |
| Optional Calendar action | NOT VERIFIED | Recipe only |
| Zapier/n8n | Compatible design; NOT VERIFIED | HTTP contract and official module documentation |

Both required scenarios now have independent live evidence. The verified portfolio statement is: “I built a custom CRM with authenticated external APIs, secure event-driven webhooks, integration logging and retries, AI lead processing, and real Make.com workflows connecting CRM events with external business tools.” Calendar and Zapier/n8n remain outside that execution claim.
