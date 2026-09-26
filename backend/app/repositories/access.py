import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models.entities import Collection, Conversation, Document, WorkspaceMember
from app.schemas.api import Scope


def membership(
    db: Session, workspace_id: uuid.UUID, user_id: uuid.UUID, write: bool = False
) -> WorkspaceMember:
    member = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user_id
        )
    )
    if member is None:
        raise AppError(404, "not_found", "Workspace not found.")
    if write and member.role == "viewer":
        raise AppError(403, "read_only", "This workspace is read-only.")
    return member


def document(
    db: Session, document_id: uuid.UUID, user_id: uuid.UUID, write: bool = False
) -> Document:
    item = db.get(Document, document_id)
    if item is None:
        raise AppError(404, "not_found", "Document not found.")
    membership(db, item.workspace_id, user_id, write)
    return item


def conversation(db: Session, conversation_id: uuid.UUID, user_id: uuid.UUID) -> Conversation:
    item = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user_id
        )
    )
    if item is None:
        raise AppError(404, "not_found", "Conversation not found.")
    membership(db, item.workspace_id, user_id)
    return item


def validate_scope(db: Session, workspace_id: uuid.UUID, scope: Scope) -> None:
    if scope.collection_id and not db.scalar(
        select(Collection.id).where(
            Collection.id == scope.collection_id, Collection.workspace_id == workspace_id
        )
    ):
        raise AppError(404, "invalid_scope", "Collection not found in this workspace.")
    if scope.document_ids:
        found = set(
            db.scalars(
                select(Document.id).where(
                    Document.workspace_id == workspace_id, Document.id.in_(scope.document_ids)
                )
            )
        )
        if found != set(scope.document_ids):
            raise AppError(404, "invalid_scope", "One or more selected documents are unavailable.")
