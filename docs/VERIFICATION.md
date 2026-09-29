# Tavo verification record

Updated 2026-09-29. The public demo has not yet been deployed. Do not call it prospect-ready until the hosted checks below pass.

## Local checks

- Backend: 59 pytest cases pass with mocked AI/email providers. One dependency deprecation warning remains.
- Frontend: TypeScript typecheck and Next.js production build pass. The public pages and CRM routes build as dynamic server pages.
- Fresh SQLite migration and `alembic check` pass through revision 0003 after the deployment changes.
- PostgreSQL dialect SQL was reviewed, but no live PostgreSQL server was available locally. Neon migration and persistence are unproven.
- Prior local browser smoke tested demo login, dashboard, pipeline, stage persistence, activity, logout and narrow layout. The new Tavo branding and hosted path still need a browser pass.

## Hosted gate

Record the frontend and API URLs, then verify:

1. API `/api/health` returns 200 and `{"status":"ok"}` after an API restart or cold start; Neon contains the migrated tables and persists leads after restart.
2. Frontend loads, one-click demo login succeeds, and refresh/navigation keep the session. A demo account cannot list, open, mutate, or email a non-demo lead by ID.
3. `/inquiry` offers only the fake demo path. Direct public `POST /api/leads` returns 403 in demo mode.
4. Reset seeds five fake leads. Simulate creates a new fake lead, classifies it through the real AI provider, and records the owner notification outcome. If a provider fails, the lead remains and the timeline reports a retryable failure.
5. Move the lead through the pipeline, refresh, and confirm its stage and activity history. Generate a draft and confirm no email was sent by drafting alone.
6. Edit and approve a reply. With Resend configured, confirm provider acceptance to `delivered@resend.dev` and duplicate-send protection. This is a test address; human inbox delivery is intentionally unproven.
7. Confirm CORS allows the exact frontend origin and omits `Access-Control-Allow-Origin` for a different origin. Check mobile viewport, browser console and Render logs.

## Known limits

- Render Free web services sleep when idle and their local files are ephemeral; Neon stores persistent data.
- The rate limiter is in process memory and may group visitors behind the web server's address. One API instance is sufficient for this portfolio demo.
- No real customer email should be sent from the public demo. Resend test acceptance is not a delivery or bounce guarantee.
- A pending email after a process crash needs provider reconciliation before manual retry.
