# Tavo public demo deployment

The repository's `render.yaml` creates **two Render Free web services**: a Next.js frontend and a FastAPI backend. Neon Free supplies PostgreSQL; Resend Free supplies test email. No paid Render database is declared. Both web services may sleep after 15 minutes idle, so the first visit can take about a minute. This is acceptable for a portfolio demo.

Vercel Hobby is not used for this prospect-facing deployment because [its fair-use policy](https://vercel.com/docs/limits/fair-use-guidelines) limits Hobby deployments to noncommercial personal use. Render documents Free web services as suitable for portfolio previews.

## Required private values

Create a Neon Free project and copy its PostgreSQL connection URL with TLS (`sslmode=require`). The API normalizes Neon `postgresql://` to the installed `psycopg` driver. The API runs Alembic migrations before serving requests and `/api/health` checks the database with `SELECT 1`.

At Blueprint creation, provide these values **only in Render's secret prompts**:

| Service | Variable | Value |
| --- | --- | --- |
| `tavo-api` | `DATABASE_URL` | Neon connection URL, including TLS options |
| `tavo-api` | `DEMO_LOGIN_PASSWORD` | A new random password of at least 12 characters |
| `tavo-web` | `DEMO_LOGIN_PASSWORD` | Exactly the same demo password |
| `tavo-api` | `OPENROUTER_API_KEY` | Backend AI key; without it classification and drafts report failures |
| `tavo-api` | `RESEND_API_KEY` | Backend Resend key; without it email is disabled |

Render generates `JWT_SECRET` and connects the public service URLs. `DEMO_LOGIN_EMAIL=demo@example.com` is not a destination; it is just the login identifier. `EMAIL_FROM=Tavo Demo <onboarding@resend.dev>`, `OWNER_NOTIFICATION_EMAIL=delivered@resend.dev`, and `DEMO_EMAIL_OVERRIDE=delivered@resend.dev` are safe Resend test settings. Every outbound demo message is redirected to the test address. A provider receipt proves API acceptance, not delivery to a human inbox. Do not replace the override with a real address for public visitors.

If an account or Blueprint form cannot accept a missing optional provider key, set `EMAIL_TRANSPORT=log` and a nonempty fake `DEMO_EMAIL_OVERRIDE` for initial smoke testing; this captures email only on the ephemeral local filesystem. Switch back to the Resend test configuration once the key is available. The log transport is not persistent on Render Free.

## Create and verify

1. Connect the repository to Render and create a Blueprint from `render.yaml`. Confirm **both service plans say Free** and no database resource is included. Enter only the private values above. The demo account is created on API startup, after migrations; no shell is needed.
2. Confirm `https://<api>.onrender.com/api/health` returns `{"status":"ok"}`. A failure here means startup, migrations, or Neon connectivity failed. Check API deploy logs.
3. Open `https://<web>.onrender.com`. Enter the demo workspace and select **Reset demo data** once to populate the first five synthetic leads. All subsequent simulated inquiries use fake data.
4. Walk through simulate → lead detail and AI classification → pipeline status change → activity history → AI draft → human edit and Send. Confirm email's destination is `delivered@resend.dev`, repeated sends are reported as duplicates, and no real customer address was contacted.
5. Refresh the dashboard and lead page to verify PostgreSQL persistence. Test `/inquiry` redirects visitors to the sample workflow; a direct `POST /api/leads` must return 403 in demo mode. Test an `Origin` from the frontend URL and from an unrelated URL against API preflight; only the configured origin should receive `Access-Control-Allow-Origin`.
6. Check a phone-sized viewport and browser console. Review Render logs for unexpected errors. Keep `DEMO_MODE=true` and one API instance for this demo.

Render Free services cannot run one-off shell commands. Deployment therefore runs `alembic upgrade head && python -m app.bootstrap_demo` in the API container start command. The bootstrap refuses to turn an existing real user into a demo user. Neon data persists across Render sleep and redeploy; Render's local filesystem does not.

## Limits

This setup is a portfolio preview, not production hosting for a paying client. The in-process rate limiter can group visitors behind the frontend server address and resets on restart. AI and email use free or metered external accounts, so watch their usage. Resend's test address does not prove human inbox delivery. Before claiming hosted readiness, record actual public URLs and the hosted smoke results in `docs/VERIFICATION.md`.
