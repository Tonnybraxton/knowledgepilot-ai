# Implementation record

Initial inspection: empty directory, no Git repository, package files, environment files, or existing tests. Node 24 and Python 3.10 found. Python 3.12+ will be provisioned with uv. A running host PostgreSQL was detected and will not be modified without an isolated project database.

Dependency order: foundation and migrations → secure accounts and workspace isolation → private upload and durable ingestion → metadata-aware extraction and embeddings → scoped hybrid retrieval → streamed grounded conversations and citation viewer → connected frontend → security, integration, E2E, CI, documentation.

The acceptance milestone is a PDF uploaded through the browser, processed by the worker, retrieved from pgvector, and cited in a streamed answer. Test AI doubles are confined to test modules and separate test infrastructure. Production requires a configured OpenAI API key.
