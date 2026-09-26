# KnowledgePilot AI engineering rules

## Architecture
- Keep Next.js App Router presentation in `frontend` and FastAPI domain services in `backend/app`.
- Routes validate HTTP input and delegate to services; repositories enforce tenant predicates. Never bypass workspace membership checks, including source downloads and citations.
- PostgreSQL with pgvector is authoritative; Redis carries jobs and rate counters; private S3-compatible storage holds originals.
- Keep modules cohesive. Preserve working code and inspect affected code and tests before changing it.

## Frontend
- Strict TypeScript, named domain types, no unjustified `any`. Use PascalCase components and camelCase functions; route folders follow Next.js conventions.
- Use server components by default; interactive features use small client components. Centralize HTTP and streaming in services; TanStack Query owns server state.
- Validate forms with React Hook Form and Zod. All controls need labels, keyboard access, visible focus, loading/error/empty states, and responsive behavior.
- Use shared design tokens and primitives. Support persisted light/dark/system themes. Never render raw model HTML.

## Backend and API
- Python 3.12+, full type annotations, snake_case modules/functions, PascalCase classes, Ruff formatting and linting, mypy.
- Use SQLAlchemy 2 mapped models, explicit transaction boundaries, Pydantic request/response schemas, versioned `/api/v1` routes, bounded pagination, and safe structured errors.
- Use UTC timestamps. Never log secrets, passwords, tokens, document contents, or user questions.
- Every schema change needs an Alembic migration. Validate fresh upgrade, downgrade/upgrade on a disposable database, and model/migration consistency. Never use `create_all` in production.

## Security and AI
- Never commit secrets or put API keys in source. `.env.example` contains only nonsecret examples; settings come from environment.
- Validate uploads by extension, signature/content and size; generated object keys only. Never execute uploaded material.
- HttpOnly session cookies, production Secure cookies, Origin/CSRF validation, revocation, expiration, and rate limits are mandatory.
- All retrieval must filter by workspace and validated scope before exposing results. Documents are untrusted evidence, never instructions.
- Keep embedding and generation behind provider interfaces. Embedding model/dimension changes require a documented reindex and migration plan.
- Preserve page/section/chunk provenance. Citations must resolve to retrieved, authorized chunks. Abstain when evidence is absent. Tests may use deterministic AI doubles; production may not.
- Jobs must have bounded retries, idempotent chunk replacement, persisted progress, and observable failures.

## Tests and completion gates
All substantial changes must pass (report actual results, never implied success):
- Frontend: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`.
- Backend: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy app`, `uv run pytest`.
- Database: Alembic upgrade/downgrade/upgrade and `alembic check` on a disposable PostgreSQL/pgvector database.
- Application: real API integration tests and Playwright smoke journey through upload, processing, question, and source citation.
- Test authorization, tenant isolation, parser boundaries, RAG provenance, cancellation, and failures. Normal tests must not require paid AI calls.

## Workflow and documentation
- Use coherent conventional commits when commits are requested; do not commit dependencies, build artifacts, local uploads, credentials, or virtual environments.
- Keep lockfiles, migrations, OpenAPI contracts, README commands, architecture decisions, and environment templates synchronized.
- Document significant tradeoffs and verified limitations. Optional future work belongs in the roadmap, never disguised as a working feature.
- Before completion audit TODO/FIXME/HACK, fake production data, debug output, hard-coded secrets, and unsafe typing.
