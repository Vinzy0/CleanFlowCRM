# Tavo verification record

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
