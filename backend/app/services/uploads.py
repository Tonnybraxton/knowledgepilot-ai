import hashlib
import io
import re
import uuid
import zipfile
from pathlib import PurePath

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.models.entities import AuditLog, Document, ProcessingJob, StorageDeletion
from app.repositories.access import validate_scope
from app.schemas.api import Scope
from app.services.storage import storage

MIMES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


def validate_upload(filename: str, content: bytes) -> tuple[str, str]:
    name = re.sub(r"[\x00-\x1f/\\]", "_", filename).strip()[:255]
    suffix = PurePath(name).suffix.lower()
    if suffix not in MIMES:
        raise AppError(415, "file_type", "Supported formats: PDF, DOCX, TXT, and Markdown.")
    if not content or len(content) > settings().max_upload_bytes:
        raise AppError(413, "file_size", "Upload a nonempty file no larger than 25 MB.")
    valid = True
    if suffix == ".pdf":
        valid = content.startswith(b"%PDF-")
    elif suffix == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                infos = archive.infolist()
                valid = (
                    "word/document.xml" in archive.namelist()
                    and "[Content_Types].xml" in archive.namelist()
                )
                valid = (
                    valid
                    and len(infos) < 3000
                    and sum(i.file_size for i in infos) < 100 * 1024 * 1024
                )
                valid = valid and not any(
                    "vbaProject" in i.filename or i.flag_bits & 1 for i in infos
                )
        except zipfile.BadZipFile:
            valid = False
    else:
        try:
            content.decode("utf-8-sig")
            valid = b"\x00" not in content
        except UnicodeDecodeError:
            valid = False
    if not valid:
        raise AppError(
            415,
            "invalid_content",
            "The file content does not match a supported, safe document format.",
        )
    return name, MIMES[suffix]


def create_document(
    db: Session,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    filename: str,
    content: bytes,
    collection_id: uuid.UUID | None,
) -> Document:
    name, mime = validate_upload(filename, content)
    validate_scope(db, workspace_id, Scope(collection_id=collection_id))
    checksum = hashlib.sha256(content).hexdigest()
    if db.scalar(
        select(Document.id).where(
            Document.workspace_id == workspace_id, Document.checksum == checksum
        )
    ):
        raise AppError(409, "duplicate", "This file is already in your workspace.")
    key = f"{workspace_id}/{uuid.uuid4().hex}"
    storage().save(key, content, mime)
    document = Document(
        workspace_id=workspace_id,
        uploaded_by=user_id,
        collection_id=collection_id,
        filename=name,
        original_filename=name,
        mime_type=mime,
        size_bytes=len(content),
        storage_key=key,
        checksum=checksum,
    )
    try:
        db.add(document)
        db.flush()
        db.add(ProcessingJob(document_id=document.id))
        db.add(AuditLog(user_id=user_id, action="document_upload", resource_id=str(document.id)))
        db.commit()
    except Exception as exc:
        db.rollback()
        # Durable compensation if storage or database cleanup is temporarily unavailable.
        db.add(StorageDeletion(storage_key=key))
        db.commit()
        if isinstance(exc, IntegrityError):
            raise AppError(409, "duplicate", "This file is already in your workspace.") from exc
        raise
    return document


def delete_document(db: Session, document: Document, user_id: uuid.UUID) -> None:
    db.add(StorageDeletion(storage_key=document.storage_key))
    db.add(AuditLog(user_id=user_id, action="document_delete", resource_id=str(document.id)))
    db.delete(document)
    db.commit()
