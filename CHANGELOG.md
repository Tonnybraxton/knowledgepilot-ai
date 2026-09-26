# Changelog

## 0.1.0 — Unreleased

- Private workspace accounts, documents, collections, search, conversations, and preferences.
- Persistent ingestion with extraction provenance, pgvector embeddings, keyword and hybrid retrieval.
- Streaming generation, cancellation, validated source references, and authorized source downloads.
- Initial schema migration, development containers, deterministic API/frontend/browser tests, and CI configuration.
- Deterministic question/answer ordering when message timestamps tie, with pagination regression coverage.
- Streaming database work runs outside the async event loop; disconnect cancellation preserves partial answers and releases the chat lock.

Verification and deployment limitations are recorded in `docs/validation.md` and `docs/roadmap.md`.
