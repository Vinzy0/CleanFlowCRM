# CleanFlow CRM

Working cleaning-business CRM demo built incrementally from [the PRD](docs/PRD.md).

**Current stage: Phase 1 — Foundation.** Public inquiry submission, owner sign-in/out, a protected lead list, and lead CRUD API are implemented. AI, email automation, pipeline interactions, and public demo controls belong to later phases.

- [Implementation plan and phase map](docs/IMPLEMENTATION_PLAN.md)
- [Phase 1 local setup](docs/PHASE1_SETUP.md)
- `api/`: FastAPI, SQLAlchemy models, Alembic migration, auth and lead endpoints
- `web/`: Next.js TypeScript frontend

This phase is for local development. Do not expose it as a public demo until the PRD's rate limits, AI limits, and email safeguards are implemented.
