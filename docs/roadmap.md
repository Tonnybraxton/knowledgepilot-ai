# Limitations and roadmap

The current delivery focuses on the complete private-document-to-citation flow. These limitations are explicit rather than simulated features:

- No OCR, legacy DOC parsing, image understanding, or spreadsheet ingestion. Text PDFs, DOCX, Markdown, and UTF-8 text are supported.
- Source inspection displays exact extracted text and downloads originals; there is no embedded PDF renderer with highlighted bounding boxes.
- Source references are checked against retrieved chunks; automated claim entailment and adversarial prompt-injection evaluation are not implemented.
- Retrieval uses fusion ranking. Learned cross-encoder reranking and a curated relevance benchmark are future work.
- Membership roles exist and are enforced, but invitation, role-management, SSO, MFA, and email-verification UIs are not implemented.
- Collection pickers display the first 100 collections; workspace listing is bounded at 100. Large-account navigation needs cursor pagination throughout.
- Usage is token/operation accounting, not billing, budgets, or charge enforcement.
- Parser subprocess isolation, extraction hard deadlines, stale-worker fencing, and a storage-deletion dead-letter policy are production-hardening follow-ups.
- Interrupted generation is saved as incomplete; recovery after an abrupt process termination still requires operational reconciliation.
- Docker/MinIO runtime validation and paid-provider acceptance are separate pending deployment checks; deterministic tests do not validate model answer quality.
