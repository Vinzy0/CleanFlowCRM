# Make workflows: setup and live acceptance

**Scenario A: NOT VERIFIED. Scenario B: NOT VERIFIED. Calendar: NOT VERIFIED.** No Make or Google credentials were available. No scenarios were created, executed or represented as completed. These are implementation instructions, not execution evidence.

## Prerequisites

Use a separate Tavo development workspace reachable over public HTTPS, with migrated database, normal owner login, `DEMO_MODE=false`, development OpenRouter key, `EMAIL_TRANSPORT=log`, and the integration encryption key. Do not use the public production demo, the old Resend key, or a production database. Start the webhook worker. A hosted development environment/tunnel needs the user's setup and authorization; none was created here.

In Tavo Integrations, generate a read/write API key. Store it in Make's HTTP API-key credential connection, using header name `X-API-Key`. Keep keys and webhook paths out of exported blueprints/screenshots. Make's current [HTTP documentation](https://apps.make.com/http) supports API-key credentials and recommends its dedicated credential field.

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

1. Create **Tavo dev — CRM events to Sheets**. Add **Webhooks / Custom webhook**. Enable **Get request headers** and **JSON pass-through** to retain the exact signed JSON text. Register its generated HTTPS URL in Tavo and subscribe to `lead.created` (optionally `lead.classified`). Save the one-time signing secret in a protected Make configuration. These settings are described in the [Make webhook module documentation](https://apps.make.com/gateway).
2. Validate the `X-Tavo-Signature` header before downstream actions. Extract timestamp from `t=...` and digest from `v1=...`; require timestamp within five minutes. Hash `timestamp + "." + raw JSON` with HMAC-SHA256 and compare to the received hex digest. In Tools, set a variable named signature_input by mapping the timestamp token, typing one literal period, then mapping the original raw JSON token, with no added spaces. Make documents HMAC using `sha256(signature_input; "hex"; signing_secret; "text")`. Use mapped tokens rather than those literal variable names. Verify against Tavo's test/reference signer before relying on the filter. Raw JSON must not be parsed/re-serialized before verification. Make formula/filter execution is **NOT VERIFIED** here. [Hash function reference](https://help.make.com/text-and-binary-functions#sha256).
3. Parse the authenticated raw JSON using a JSON module. Filter event type to `lead.created`. Use sequential scenario processing and a Make data store keyed by `event.id` to detect processed events. Duplicates return success without another side effect. Keep dedupe state durably; never record an event as completed before the downstream action succeeds.
4. Connect a development Google account. Create a Sheet with columns: `event_id`, `lead_id`, `name`, `email`, `service`, `stage`, `source`, `occurred_at`. Use **Google Sheets / Search Rows** for exact event_id; update the existing row if found, otherwise **Add a Row**. Map event_id from `id`, business fields from `data.lead`, and occurred_at from the envelope. Then record completion in the data store. If Sheets succeeded but a later step crashed, searching by event_id prevents a duplicate on retry. The scenario must emit bundles for the no-match route; enable the Search Rows continuation option where available or use a configured no-match route. [Sheets module reference](https://apps.make.com/google-sheets).
5. Put **Webhooks / Webhook response** last, with status 200. Add an error route returning 500 when possible and preserve incomplete execution evidence. Keep work within Tavo's 10-second socket timeout or expect a retry; dedupe must handle that case. A default Make 200 can merely acknowledge the queue. It does **not** prove a Sheets row was created. [Make receipt/response behavior](https://help.make.com/webhooks).
6. Start the scenario, create a new synthetic lead through Scenario A after registering the destination, and run the Tavo worker (or owner dispatch). Check all three systems. Test a duplicate with the same event ID and raw bytes in the receiver; no extra row may appear. Do not manufacture a second success screenshot by editing Tavo's delivery records.

Acceptance proof required: Tavo event ID and actual recorded HTTP 2xx attempt/time; Make webhook input with that same ID and successful execution record; matching row actually visible in Google Sheets; duplicate handling; one captured failure/retry if practical. A Tavo 2xx record alone is insufficient. Publish screenshots only with webhook paths, keys, headers and real personal details redacted.

## Optional Calendar recipe

The Tavo-side `appointment.booked` event is implemented and tested; a live Calendar scenario is not. After A and B work, register a separate Make destination/subscription, validate signature/dedupe as above, and use **Google Calendar / Create an Event**. Map the lead name and appointment_at, choose an explicit business timezone and duration (for example 60 minutes), and store the resulting Calendar event ID against the Tavo lead. Repeated event IDs must reuse that Calendar event; a later appointment change should update it. No cancellation event or appointment duration field is implemented. Verify the actual calendar entry and Tavo attempt before making a portfolio claim.

## Zapier and n8n

The design uses ordinary HTTPS JSON, `X-API-Key`, idempotency headers and signed webhook envelopes. Zapier **Webhooks / Custom Request** and **Catch Raw Hook**, and n8n **HTTP Request** and **Webhook**, can be configured for this contract. Receivers must verify raw bytes and dedupe event IDs. This is a compatibility statement, not proof that a workflow was built in either platform. Their actual configuration is **NOT VERIFIED**. [Zapier HTTP options](https://help.zapier.com/hc/en-us/articles/44391646192397-Ways-to-make-API-requests-in-Zapier), [n8n webhook reference](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/).

## Evidence ledger

| Item | Status | Evidence |
| --- | --- | --- |
| Tavo external creation + classification | VERIFIED offline | pytest fake-provider persisted-lead tests |
| Tavo outbound delivery + retries/HMAC | VERIFIED offline | injected sender, real persisted outbox and attempts |
| Make A live execution | NOT VERIFIED | No account credentials |
| Make B reception + Sheets action | NOT VERIFIED | No Make/Google credentials |
| Optional Calendar action | NOT VERIFIED | Recipe only |
| Zapier/n8n | Compatible design; NOT VERIFIED | HTTP contract and official module documentation |

Do not replace NOT VERIFIED with VERIFIED until the live evidence above is captured. The exact portfolio claim requested by the user remains gated on actual Make A and B executions.
