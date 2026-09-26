# Deployment and operations

The supplied Compose file is a local development stack. It is not a hardened Internet-facing deployment. It binds application and development consoles to loopback. Docker execution remains to be verified on a Docker-capable host.

For production, terminate TLS at a trusted reverse proxy, set `APP_ENV=production` and an exact HTTPS `FRONTEND_URL`, use independent database/S3 credentials, private bucket policies, encrypted storage and backups, and authenticated private network access to Redis. Restrict forwarded headers to trusted proxies. Avoid using the MinIO root identity as an application credential. Set the frontend's `BACKEND_URL` during image build; it is incorporated in Next.js rewrites.

Configure the edge request-body limit to match the 25 MiB application limit plus small multipart overhead, and bound slow uploads. The API validates declared body size and reads at most the upload limit, but infrastructure must also limit chunked multipart traffic before parsing. Disable proxy response buffering and allow at least 180 seconds for chat streams. Do not cache `/api`, session responses, or source downloads.

Install the vector extension with a privileged migration identity, then run the application with a narrower database identity. Run `alembic upgrade head` as a controlled release step before starting new workers. Rollback tests belong on disposable data. Do not use `create_all` for deployment.

Provide working SMTP delivery and monitor password reset delivery failures. No reset token is returned by an API response. The local Mailpit UI is only a development inbox.

Run workers with CPU/memory limits and monitor readiness, job failures, queue age, and pending storage deletion attempts. The current worker parses in process: deeply adversarial PDF workloads need stronger process isolation and hard resource deadlines before accepting untrusted public uploads at scale. A stalled worker eventually loses its heartbeat; operators must restart it and investigate.

Back up PostgreSQL and original objects together. Restore to a separate environment, run migration consistency checks, verify object access, and execute the browser smoke journey. Test Redis recovery separately; persisted database jobs are re-dispatched. Database/job reconciliation remains authoritative.

Release gates include all lint/type/unit/integration/browser tests, fresh migration and downgrade/upgrade validation against PostgreSQL/pgvector, an actual Compose build/start, storage failure/recovery checks, and one operator-approved live-provider acceptance run with non-sensitive sample documents. Do not claim production readiness until these checks and deployment-specific security review have passed.
