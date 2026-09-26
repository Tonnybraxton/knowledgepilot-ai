import time
from datetime import timedelta

import structlog
from sqlalchemy import or_, select

from app.db.session import SessionLocal
from app.models.entities import ProcessingJob, StorageDeletion, utcnow
from app.security.rate_limit import redis_client
from app.services.storage import storage
from app.workers.ingestion import process_job

log = structlog.get_logger()


def tick() -> None:
    redis = redis_client()
    redis.set("worker:heartbeat", utcnow().isoformat(), ex=180)
    with SessionLocal() as db:
        pending = db.scalars(
            select(ProcessingJob.id)
            .where(
                or_(
                    ProcessingJob.status == "pending",
                    (ProcessingJob.status == "running")
                    & (ProcessingJob.started_at < utcnow() - timedelta(minutes=20)),
                )
            )
            .order_by(ProcessingJob.created_at)
            .limit(50)
        ).all()
        for job_id in pending:
            # A short dispatch lease bounds duplicate queue entries; the DB claim is authoritative.
            if redis.set(f"dispatch:{job_id}", "1", nx=True, ex=30):
                redis.rpush("ingestion", str(job_id))
        deletions = db.scalars(
            select(StorageDeletion)
            .order_by(StorageDeletion.created_at)
            .limit(20)
            .with_for_update(skip_locked=True)
        ).all()
        for deletion in deletions:
            try:
                storage().delete(deletion.storage_key)
                db.delete(deletion)
            except Exception as exc:
                deletion.attempts += 1
                log.error(
                    "storage_deletion_failed",
                    error_type=type(exc).__name__,
                    attempts=deletion.attempts,
                )
        db.commit()
    queued = redis.lpop("ingestion")
    if isinstance(queued, bytes):
        process_job(queued.decode())
    elif isinstance(queued, str):
        process_job(queued)


def main() -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    )
    while True:
        try:
            tick()
        except Exception as exc:
            log.error("worker_tick_failed", error_type=type(exc).__name__)
        time.sleep(5)


if __name__ == "__main__":
    main()
