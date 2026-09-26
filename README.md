# KnowledgePilot AI

A private document workspace built with Next.js, FastAPI, PostgreSQL/pgvector, Redis, and S3-compatible storage. Upload PDF, DOCX, Markdown, or UTF-8 text; organize collections; search by meaning or keyword; and ask questions with references to retrieved passages.

The application uses real provider interfaces. Normal tests replace AI calls with deterministic providers contained only in `backend/tests`; production images exclude those modules.

## See the project

A working tour of the document workspace: upload files, organize a collection, find a passage, ask a question, and open its source.

**Real browser captures, fictional demo data.** These screenshots use the local test server with deterministic AI, an isolated PGlite/pgvector database, test Redis, and temporary file storage. The answer shown is a retrieved excerpt returned by the test provider. See the [full walkthrough](docs/walkthrough.md) for all 13 screenshots and the verified steps.

### Workspace overview

Track indexed documents, processing, recent files, and saved conversations.

[![KnowledgePilot dashboard showing three indexed documents and a saved conversation](docs/screenshots/02-dashboard.png)](docs/screenshots/02-dashboard.png)

### Upload and organize documents

Upload PDF, Word, Markdown, or text files. Processing runs in the background, and the library shows when each file is ready.

[![Document upload dialog with three successfully uploaded sample files](docs/screenshots/03-upload.png)](docs/screenshots/03-upload.png)

[![Document library with ready PDF, Markdown, and text files](docs/screenshots/04-documents.png)](docs/screenshots/04-documents.png)

### Ask a question and follow the evidence

Choose the source documents, ask a question, and inspect the cited passage with its page reference.

[![Conversation scoped to the Orion specification with an answer and page citation](docs/screenshots/07-chat.png)](docs/screenshots/07-chat.png)

[![Citation dialog displaying the original passage, page number, and download controls](docs/screenshots/08-citation.png)](docs/screenshots/08-citation.png)

**Explore more:** [Collections](docs/walkthrough.md#5-organize-collections) · [Search](docs/walkthrough.md#6-search-the-knowledge-base) · [Source inspection](docs/walkthrough.md#9-inspect-the-source-document) · [Dark mode](docs/walkthrough.md#12-switch-to-dark-mode) · [Mobile](docs/walkthrough.md#13-continue-on-mobile)

## Run with Docker Compose

Requirements: Docker Engine with Compose v2 and an OpenAI API key for embeddings and generation.

1. Copy `.env.example` to `.env` (`Copy-Item .env.example .env` in PowerShell, or `cp .env.example .env` on macOS/Linux).
2. Set `OPENAI_API_KEY` in `.env`. The remaining example values are for isolated local development only.
3. Run `docker compose up --build -d`.
4. Open `http://localhost:3000`, register, upload a document, wait for Ready, and start a conversation with that document selected.

Compose starts the frontend, API, worker, PostgreSQL with pgvector, Redis, private MinIO storage, and Mailpit. A one-shot service runs Alembic before the API and worker start. Password reset mail appears at `http://localhost:8025`. API documentation is at `http://localhost:8000/docs` in development.

Use `docker compose logs -f backend worker` for metadata-only application logs and `docker compose down` to stop. Named volumes retain documents and database records. Do not remove volumes containing data you want to keep.

**Verification status:** see [the validation record](docs/validation.md). The Docker stack must be validated on a Docker-capable host; successful host builds and tests do not establish that Compose deployment works.

## Host development

Use Node.js 24 and Python 3.12+ with uv. Provide a dedicated PostgreSQL database with pgvector, Redis, and private S3 storage. Configure `.env` using host-accessible addresses. An explicit `STORAGE_BACKEND=local` adapter is available for development only.

```text
cd backend
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

In another terminal, run `uv run python -m app.workers.main` from `backend`. In a third terminal:

```text
cd frontend
npm ci
npm run dev
```

The frontend proxies `/api` to `BACKEND_URL`, defaulting to `http://127.0.0.1:8000`. Docker builds explicitly use `http://backend:8000`. `FRONTEND_URL` must match the browser origin exactly; use `http://localhost:3000` consistently for local development. `.env` is read by the backend; frontend build-time configuration comes from the shell or Docker build arguments.

To serve a production build on the host, run `npm run build` followed by `npm start` from `frontend`. The start script copies static assets into the standalone bundle and starts its generated server. Set `PORT` or `HOSTNAME` to override the defaults of 3000 and `0.0.0.0`.

The tokenizer downloads its public vocabulary on first host use. Container images preload it during build. Tests use `.cache/tiktoken`; initialize it once with `TIKTOKEN_CACHE_DIR` pointing there and `uv run python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"`.

## Quality checks

From `frontend`:

```text
npm run lint
npm run typecheck
npm test
npm run build
```

From `backend`:

```text
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
uv run python scripts/export_openapi.py --check
```

The saved API contract is `docs/api/openapi.json`. After an intentional API change, regenerate it with `uv run python scripts/export_openapi.py` and review the resulting contract changes.

Without `TEST_DATABASE_URL`, integration tests are explicitly skipped. For full tests, start disposable services with `docker compose -f compose.test.yml up -d --wait`. Set these variables in the shell:

| Variable | Disposable local value |
| --- | --- |
| `TEST_DATABASE_URL` | `postgresql+psycopg://pilot_test:test_only@127.0.0.1:55432/pilot_test` |
| `DATABASE_URL` | Same value, for Alembic |
| `TEST_REDIS_URL` | `redis://127.0.0.1:56379/0` |
| `APP_ENV` | `test` |

In PowerShell use `$env:NAME='value'`; in Bash use `export NAME='value'`. The database name must end in `_test`. Never run the downgrade validation against development or production data.

```text
cd backend
uv run alembic upgrade head
uv run alembic downgrade base
uv run alembic upgrade head
uv run alembic check
uv run pytest
cd ../frontend
npx playwright install chromium
npm run build
npm run test:e2e
```

Playwright starts its own local API and frontend on ports 8000 and 3000. Its test server processes persisted jobs with the real ingestion code, uses temporary local storage, and substitutes only AI and optionally Redis. Set `TEST_REDIS_URL` for a real Redis instance; otherwise tests use fakeredis. The browser tests cover desktop and mobile registration, PDF upload, processing, selected-document chat, page citation, source download, and exact-passage navigation. They do not require paid AI calls.

## Configuration

`.env.example` documents the local configuration. Deployment must set `APP_ENV=production`, an HTTPS `FRONTEND_URL`, database and Redis URLs, S3 endpoint/bucket/credentials, SMTP configuration, and `OPENAI_API_KEY`. Never expose the provider key to browser code. See [deployment guidance](docs/deployment.md) for constraints and unverified checks.

The schema requires 1,536-dimensional embeddings. Changing the embedding model requires reprocessing affected documents; changing dimensions requires a migration and reindex. See [architecture and AI decisions](docs/architecture.md).

## Product scope

Implemented: accounts and reset flows, revocable cookie sessions, workspace boundaries, collection management, document upload/rename/move/delete/reprocess, processing status, semantic/keyword/hybrid search, conversation history, streaming and cancellation, citation excerpts and original downloads, usage, theme persistence, responsive navigation, and a command palette.

Citations validate source membership and reference numbers, not the truth of every model claim. Read the source passage before relying on an answer. Scanned PDFs require OCR before upload. See [limitations and roadmap](docs/roadmap.md).
