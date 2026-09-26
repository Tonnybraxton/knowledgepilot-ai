# Contributing

Read `AGENTS.md` before changing code. Keep tenant predicates and source authorization intact; use provider doubles only in tests. Never log document text, questions, passwords, or tokens.

Use the locked environments (`npm ci`, `uv sync --frozen`). Run the frontend and backend checks from the README, then migrations and the Playwright journey against disposable services. Explain any skipped check in your change description. Every schema change needs a migration and a reindex plan if embeddings are affected.

Describe the user-visible problem, resulting behavior, and actual validation. Prefer cohesive conventional commits when committing. Exclude local credentials, dependencies, uploads, caches, test reports, and build output.
