# Architecture and AI decisions

The Next.js App Router supplies server-rendered routes and small interactive feature boundaries. TanStack Query owns remote state, React Hook Form and Zod validate major forms, and the service client owns HTTP, CSRF, upload progress, and SSE parsing. Markdown is rendered without raw HTML or remote images.

FastAPI validates requests, checks session and workspace access, and delegates ingestion, storage, authentication, retrieval, and generation to cohesive modules. Simple resource CRUD currently lives in route modules; complex operations live in services. PostgreSQL is authoritative. Redis carries dispatch entries, short leases, conversation locks, and rate counters. Originals are private objects accessed through authorized API downloads.

## Data and transactions

Migration `0001_initial` installs pgvector and creates users, hashed sessions, password resets, workspaces, memberships, collections, documents, chunks, processing jobs, conversations, messages, citations, usage, audit records, and pending storage deletions. Tenant and full-text indexes support scoped queries; HNSW uses cosine distance on 1,536-dimensional vectors. Document checksums are unique within a workspace.

Upload validation checks extension, size and content. DOCX archive entry counts and expanded size are bounded; encrypted and macro-bearing archives are rejected. Keys are generated identifiers rather than user filenames. Document creation commits its processing job in the same transaction. A dispatcher recovers pending jobs after a Redis interruption. Jobs have three attempts, persisted stages, a running lease, and atomic chunk replacement. Failed original cleanup is persisted for retry.

Deleting a document cascades chunks and jobs, queues original-object deletion, and nulls source foreign keys on saved citations. The conversation retains quoted excerpts and explicitly labels deleted sources. Deleting a source therefore does not erase excerpts already included in conversations.

## Retrieval and generation

1. Extract PDF text with page numbers, DOCX paragraphs/tables with section headings, or text/Markdown sections. Reject unreadable documents and enforce extracted-size limits.
2. Split passages at paragraph/sentence boundaries with token ceilings and overlap. Never merge provenance across pages.
3. Embed batches through `EmbeddingProvider`; save all vectors atomically with chunk metadata and the model identifier.
4. Validate workspace membership and document/collection scope before retrieval. Semantic candidates use cosine distance; keyword candidates use PostgreSQL text search. Reciprocal rank fusion deduplicates and ranks candidates. This is a deterministic fusion ranker, not a cross-encoder.
5. Pack JSON evidence under a context token budget. A bounded prior-question expansion helps pronoun follow-ups. Document content is untrusted evidence in a separate prompt field.
6. Stream through `GenerationProvider`, bound duration, persist completed/failed/cancelled state, and release the conversation lock. Check final citation numbers against the selected hits. Abstain when evidence is absent or the answer lacks valid references.
7. Return source excerpts, document IDs, chunk IDs, page numbers, and headings. Each download and passage lookup rechecks authorization.

Streaming deltas are provisional. The final `done` event supplies the validated content and citations. Reference validation does not establish entailment or defeat all prompt injection; the UI makes source review available and labels incomplete responses.

## Embedding migration procedure

For a model change at 1,536 dimensions, schedule reprocessing and keep the configured model consistent across API and workers. Semantic retrieval excludes chunks whose document model differs. Search coverage will temporarily shrink during reindexing; perform a controlled maintenance window for consistent results.

For a dimension change, first add an Alembic migration for a replacement vector column/index, update schema and configuration invariants together, re-embed originals with the new model, verify tenant-filtered retrieval and source provenance, then switch readers and remove the old index. Back up the database and originals first. Never reinterpret old vectors under a new model or dimension.

## Operations

`/health` is process liveness. `/ready` checks migrations, vector extension, Redis, recent worker heartbeat, and storage. Structured logs include request identifiers and error types, not document bodies, credentials, or questions. Run Uvicorn without access logging so query strings do not enter generic request logs. Usage captures reported tokens; interrupted calls may still incur provider charges that are absent from local totals.
