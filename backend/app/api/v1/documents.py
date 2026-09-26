import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Response, UploadFile
from sqlalchemy import func, select

from app.core.config import settings
from app.core.errors import AppError
from app.models.entities import Document, DocumentChunk, ProcessingJob
from app.repositories import access
from app.schemas.api import ChunkOut, DocumentOut, DocumentPatch, Page, Scope
from app.security.rate_limit import rate_limit
from app.security.sessions import CurrentUser, Db
from app.services import uploads
from app.services.storage import storage

router = APIRouter(tags=["Documents"])


@router.get("/workspaces/{workspace_id}/documents", response_model=Page[DocumentOut])
def documents(
    workspace_id: uuid.UUID,
    db: Db,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str = Query("", max_length=200),
    status: str | None = None,
    collection_id: uuid.UUID | None = None,
    sort: str = Query("newest", pattern="^(newest|name|oldest)$"),
) -> Page[DocumentOut]:
    access.membership(db, workspace_id, user.id)
    query = select(Document).where(Document.workspace_id == workspace_id)
    if q:
        query = query.where(Document.filename.ilike(f"%{q}%"))
    if status:
        query = query.where(Document.status == status)
    if collection_id:
        query = query.where(Document.collection_id == collection_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    order = (
        Document.filename.asc()
        if sort == "name"
        else Document.created_at.asc()
        if sort == "oldest"
        else Document.created_at.desc()
    )
    rows = db.scalars(
        query.order_by(order, Document.id).offset((page - 1) * page_size).limit(page_size)
    )
    return Page(
        items=[DocumentOut.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/workspaces/{workspace_id}/documents", response_model=DocumentOut, status_code=201)
def upload(
    workspace_id: uuid.UUID,
    db: Db,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
    collection_id: Annotated[uuid.UUID | None, Form()] = None,
) -> Document:
    access.membership(db, workspace_id, user.id, write=True)
    rate_limit(f"upload:{user.id}", 20)
    content = file.file.read(settings().max_upload_bytes + 1)
    return uploads.create_document(
        db, workspace_id, user.id, file.filename or "document", content, collection_id
    )


@router.get("/documents/{document_id}", response_model=DocumentOut)
def detail(document_id: uuid.UUID, db: Db, user: CurrentUser) -> Document:
    return access.document(db, document_id, user.id)


@router.get("/documents/{document_id}/chunks", response_model=Page[ChunkOut])
def chunks(
    document_id: uuid.UUID,
    db: Db,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str = Query("", max_length=200),
    chunk_id: uuid.UUID | None = None,
) -> Page[ChunkOut]:
    access.document(db, document_id, user.id)
    query = select(DocumentChunk).where(DocumentChunk.document_id == document_id)
    if chunk_id:
        query = query.where(DocumentChunk.id == chunk_id)
    if q:
        query = query.where(DocumentChunk.content.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(DocumentChunk.chunk_index).offset((page - 1) * page_size).limit(page_size)
    )
    return Page(
        items=[ChunkOut.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/documents/{document_id}/source")
def source(document_id: uuid.UUID, db: Db, user: CurrentUser) -> Response:
    document = access.document(db, document_id, user.id)
    content = storage().read(document.storage_key)
    # Downloads are authorized on every request and never expose public object URLs.
    from urllib.parse import quote

    return Response(
        content,
        media_type=document.mime_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(document.original_filename)}",
            "Cache-Control": "private, no-store",
        },
    )


@router.patch("/documents/{document_id}", response_model=DocumentOut)
def update(document_id: uuid.UUID, data: DocumentPatch, db: Db, user: CurrentUser) -> Document:
    document = access.document(db, document_id, user.id, write=True)
    if data.filename:
        document.filename = data.filename.strip()
    if "collection_id" in data.model_fields_set:
        access.validate_scope(db, document.workspace_id, Scope(collection_id=data.collection_id))
        document.collection_id = data.collection_id
    db.commit()
    return document


@router.post(
    "/documents/{document_id}/processing-jobs", response_model=DocumentOut, status_code=202
)
def reprocess(document_id: uuid.UUID, db: Db, user: CurrentUser) -> Document:
    document = access.document(db, document_id, user.id, write=True)
    rate_limit(f"reprocess:{user.id}", 10)
    db.refresh(document, with_for_update=True)
    if document.status not in {"failed", "ready"}:
        raise AppError(409, "processing", "This document is already being processed.")
    document.status = "queued"
    document.processing_error = None
    db.add(ProcessingJob(document_id=document.id))
    db.commit()
    return document


@router.delete("/documents/{document_id}", status_code=204)
def delete(document_id: uuid.UUID, db: Db, user: CurrentUser) -> None:
    document = access.document(db, document_id, user.id, write=True)
    uploads.delete_document(db, document, user.id)
