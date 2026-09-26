# Validation record

Verified on 2026-09-24 and 2026-09-25 on Windows with Node.js 24.19.0 and Python 3.12.11. The final backend checks were run after the streaming fix on September 25; the frontend application build and unit checks passed on September 24.

## Checks completed

| Check | Result |
| --- | --- |
| Frontend ESLint, warnings treated as errors | Passed |
| Frontend TypeScript (`tsc --noEmit`) | Passed |
| Frontend Vitest | 7 tests passed |
| Next.js production build | Passed |
| Backend Ruff lint and formatting | Passed; 36 files formatted correctly |
| Backend mypy | Passed; 27 source files |
| OpenAPI contract comparison | Passed |
| Alembic fresh upgrade, downgrade to base, second upgrade | Passed on disposable PGlite/pgvector |
| Alembic model/schema comparison | Passed; no new upgrade operations |
| Backend pytest, including real API integration tests | 24 passed; 2 dependency deprecation warnings |
| Playwright desktop and mobile smoke journeys | 2 passed in 28.3 seconds on September 25 |

The frontend checks invoked the installed Node entry points directly because `npm` was unavailable on this host. These execute the same programs and arguments as the package scripts. Playwright starts the production server through `node scripts/start.mjs`, the same entry point used by `npm start`.

The database was an isolated, in-memory PGlite 0.5.8 instance with the pgvector extension package 0.0.9, listening only on loopback port 55439. It contained only disposable test data. Integration tests exercised the actual API, migrations, SQL queries, parsing, ingestion, and citation persistence. AI providers and Redis used the existing deterministic test doubles; original files used temporary local storage. PGlite verification does not establish native PostgreSQL concurrency behavior.

Both browser projects completed registration, PDF upload, persisted ingestion, selected-document chat, page citation inspection, original download, and exact-passage navigation, with no captured browser exceptions or final-page horizontal overflow. An earlier run overlapped API tests and the browser worker on the same database and left the mobile upload queued. The final browser run used a freshly migrated disposable schema with no concurrent API suite. Run these suites sequentially, or give each separate database and storage resources.

Windows sandbox permissions initially prevented pytest temporary-directory access and Vitest subprocess startup. Approved runs outside the sandbox resolved those restrictions. Pytest also stalled creating a temporary symlink under OneDrive; using a fresh system temporary directory resolved that stall. The final backend run completed in 34.14 seconds. Its two warnings concern Starlette's deprecated httpx and AnyIO compatibility APIs.

## Fixes verified

A question and its assistant response can receive the same timestamp in a batched insert. Sorting only by timestamp allowed history to return the question last even though the answer and its citation had been saved correctly. History and generation context now use role and ID as deterministic tie breakers, keeping the question before its answer for equal timestamps. A regression test checks both chronological display and one-message pagination. Regeneration also uses ID to resolve tied question timestamps consistently.

The browser journey also exposed a streaming stall under concurrent database access. Synchronous history reads and answer persistence ran directly on the async event loop. Those operations, along with Redis lock release, now run in worker threads. Answer persistence and lease release are shielded from AnyIO disconnect cancellation. The integration suite verifies cancellation both by closing the generator normally and inside an already-cancelled AnyIO scope, checking the saved message status and released lock. AnyIO is now an explicit dependency, with the lockfile synchronized.

## Remaining deployment checks

- Run migrations and integration tests on disposable native PostgreSQL/pgvector with real Redis, using the documented Compose test stack or CI.
- Build and start the Docker stack; verify private MinIO/S3 operations and storage failure recovery.
- Run an explicitly authorized paid-provider acceptance test with non-sensitive documents. Deterministic tests do not establish model answer quality.

The source audit found no TODO/FIXME/HACK markers, frontend `any`, debug printing, production imports of test AI doubles, or embedded provider keys in the searched application sources. Existing Python `Any` annotations remain at JSONB and pgvector/TSVECTOR model boundaries. Local development credential defaults remain in settings and the environment template; this audit is not a production security certification.
