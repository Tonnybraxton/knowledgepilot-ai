# Security

Do not include credentials, private document content, or user questions in public issue reports. Use the repository owner's private security reporting channel when one is configured. This local workspace has no published reporting address.

Sessions use HttpOnly cookies, production Secure cookies, explicit expiration, hashed bearer tokens, CSRF tokens, and exact Origin validation. Passwords use Argon2. Downloads, citations, and retrieval require workspace membership. Provider inputs include authorized document passages; using AI means those passages are sent to the configured provider.

Deleting a document removes it from retrieval and queues original deletion, but saved conversation excerpts remain until the conversation is deleted. Backup retention is an operator responsibility.

See `docs/deployment.md` for production requirements and remaining hardening constraints. Do not deploy example credentials or expose development inbox/storage consoles publicly.
