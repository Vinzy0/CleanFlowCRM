# CleanFlow CRM

Working cleaning-business CRM demo built incrementally from [the PRD](docs/PRD.md).

**Current stage: Phase 3 — AI.** The app includes public inquiry submission, owner sign-in/out, a dashboard, four-stage pipeline, lead detail, status changes, an activity timeline, OpenRouter-backed classification and summary, and editable draft replies. Email automation and public demo controls belong to later phases.

- [Implementation plan and phase map](docs/IMPLEMENTATION_PLAN.md)
- [Local setup](docs/PHASE1_SETUP.md)
- `api/`: FastAPI, SQLAlchemy models, Alembic migration, auth and lead endpoints
- `web/`: Next.js TypeScript frontend

Phase 1 was checkpointed in Git commit `5d496f1` before Phase 2 work began. The pipeline uses the PRD-approved status dropdown and button; changes are stored in the database and recorded in the activity timeline.

Set `OPENROUTER_API_KEY` in the backend environment for AI calls. `OPENROUTER_MODEL` defaults to `deepseek/deepseek-v4.1-flash`. See [local setup](docs/PHASE1_SETUP.md). This phase is for local development. Do not expose it as a public demo until the PRD's rate limits, AI limits, and email safeguards are implemented.
