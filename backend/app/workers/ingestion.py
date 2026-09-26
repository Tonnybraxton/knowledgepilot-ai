import time
import uuid
from datetime import timedelta

import structlog
from sqlalchemy import delete, func, select

from app.ai.chunking import chunk_passages
from app.ai.extraction import extract
from app.ai.providers.openai import embedding_provider
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.entities import Document, DocumentChunk, ProcessingJob, UsageRecord, utcnow
from app.services.storage import storage

log = structlog.get_logger()


def stage(document_id: uuid.UUID, status: str) -> bool:
    with SessionLocal() as db:
        document = db.get(Document, document_id)
        if document is None:
            return False
        document.status = status
        db.commit()
        log.info("ingestion_stage", document_id=str(document_id), stage=status)
        return True


def process_job(job_id: str) -> None:
    with SessionLocal() as db:
        job = db.scalar(
            select(ProcessingJob).where(ProcessingJob.id == uuid.UUID(job_id)).with_for_update()
        )
        if job is None or job.status in {"complete", "failed"}:
            return
        if (
            job.status == "running"
            and job.started_at
            and job.started_at > utcnow() - timedelta(minutes=20)
        ):
            return
        if job.attempts >= 3:
            job.status = "failed"
            document = db.get(Document, job.document_id)
            if document:
                document.status = "failed"
                document.processing_error = (
                    "Processing timed out repeatedly. Please reprocess the document."
                )
            db.commit()
            return
        job.attempts += 1
        job.status = "running"
        job.started_at = utcnow()
        document_id = job.document_id
        document = db.get(Document, document_id)
        if document is None:
            return
        storage_key, mime = document.storage_key, document.mime_type
        db.commit()
    started = time.monotonic()
    try:
        if not stage(document_id, "extracting"):
            return
        passages = extract(storage().read(storage_key), mime)
        stage(document_id, "chunking")
        chunks = chunk_passages(passages)
        if not chunks:
            raise ValueError("No indexable text was found in this file.")
        stage(document_id, "embedding")
        vectors: list[list[float]] = []
        tokens = 0
        for offset in range(0, len(chunks), 64):
            result = embedding_provider().embed_batch(
                [chunk.content for chunk in chunks[offset : offset + 64]]
            )
            vectors.extend(result.vectors)
            tokens += result.tokens
        if len(vectors) != len(chunks):
            raise ValueError("Embedding response did not contain all document chunks.")
        stage(document_id, "indexing")
        with SessionLocal() as db:
            # Lock against deletion/reprocessing; replace chunks atomically only after successful embedding.
            document = db.scalar(
                select(Document).where(Document.id == document_id).with_for_update()
            )
            job = db.get(ProcessingJob, uuid.UUID(job_id))
            if document is None or job is None:
                return
            db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
            for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True)):
                db.add(
                    DocumentChunk(
                        document_id=document_id,
                        workspace_id=document.workspace_id,
                        chunk_index=index,
                        content=chunk.content,
                        token_count=chunk.token_count,
                        page_number=chunk.page_number,
                        section_title=chunk.section_title,
                        embedding=vector,
                        search_vector=func.to_tsvector("english", chunk.content),
                    )
                )
            document.status = "ready"
            document.processing_error = None
            document.chunk_count = len(chunks)
            document.page_count = max((p.page or 0 for p in passages), default=0) or None
            document.processed_at = utcnow()
            document.embedding_model = settings().openai_embedding_model
            job.status = "complete"
            job.completed_at = utcnow()
            db.add(
                UsageRecord(
                    workspace_id=document.workspace_id,
                    model=settings().openai_embedding_model,
                    operation="document_embedding",
                    tokens=tokens,
                    latency_ms=int((time.monotonic() - started) * 1000),
                )
            )
            db.commit()
    except Exception as exc:
        log.error("ingestion_failed", document_id=str(document_id), error_type=type(exc).__name__)
        with SessionLocal() as db:
            job = db.get(ProcessingJob, uuid.UUID(job_id))
            document = db.get(Document, document_id)
            if job and document:
                permanent = isinstance(exc, ValueError)
                message = (
                    str(exc)[:300]
                    if permanent
                    else "Processing service unavailable. Retrying automatically; reprocess if the failure persists."
                )
                job.status = "failed" if permanent or job.attempts >= 3 else "pending"
                job.error_message = message
                document.status = "failed" if job.status == "failed" else "queued"
                document.processing_error = message
                db.commit()
