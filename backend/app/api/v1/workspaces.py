import uuid

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.core.errors import AppError
from app.models.entities import (
    Collection,
    Conversation,
    Document,
    UsageRecord,
    Workspace,
    WorkspaceMember,
)
from app.repositories.access import membership
from app.schemas.api import CollectionIn, CollectionOut, NameIn, Page, StatsOut, WorkspaceOut
from app.security.sessions import CurrentUser, Db

router = APIRouter(tags=["Workspaces"])


@router.get("/workspaces", response_model=list[WorkspaceOut])
def workspaces(db: Db, user: CurrentUser) -> list[Workspace]:
    return list(
        db.scalars(
            select(Workspace)
            .join(WorkspaceMember)
            .where(WorkspaceMember.user_id == user.id)
            .order_by(Workspace.created_at)
            .limit(100)
        )
    )


@router.post("/workspaces", response_model=WorkspaceOut, status_code=201)
def create_workspace(data: NameIn, db: Db, user: CurrentUser) -> Workspace:
    workspace = Workspace(name=data.name.strip(), owner_id=user.id)
    db.add(workspace)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    db.commit()
    return workspace


@router.get("/workspaces/{workspace_id}/stats", response_model=StatsOut)
def stats(workspace_id: uuid.UUID, db: Db, user: CurrentUser) -> StatsOut:
    membership(db, workspace_id, user.id)
    docs = db.execute(
        select(
            func.count(Document.id),
            func.count(Document.id).filter(Document.status == "ready"),
            func.count(Document.id).filter(Document.status.not_in(["ready", "failed"])),
            func.coalesce(func.sum(Document.size_bytes), 0),
        ).where(Document.workspace_id == workspace_id)
    ).one()
    conversations = (
        db.scalar(
            select(func.count())
            .select_from(Conversation)
            .where(Conversation.workspace_id == workspace_id, Conversation.user_id == user.id)
        )
        or 0
    )
    usage = db.execute(
        select(func.count(), func.coalesce(func.sum(UsageRecord.tokens), 0)).where(
            UsageRecord.workspace_id == workspace_id
        )
    ).one()
    return StatsOut(
        documents=docs[0],
        ready=docs[1],
        processing=docs[2],
        storage_bytes=docs[3],
        conversations=conversations,
        ai_requests=usage[0],
        tokens=usage[1],
    )


@router.get("/workspaces/{workspace_id}/collections", response_model=Page[CollectionOut])
def collections(
    workspace_id: uuid.UUID,
    db: Db,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> Page[CollectionOut]:
    membership(db, workspace_id, user.id)
    query = select(Collection).where(Collection.workspace_id == workspace_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(Collection.name).offset((page - 1) * page_size).limit(page_size)
    )
    return Page(
        items=[CollectionOut.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/workspaces/{workspace_id}/collections", response_model=CollectionOut, status_code=201
)
def create_collection(
    workspace_id: uuid.UUID, data: CollectionIn, db: Db, user: CurrentUser
) -> Collection:
    membership(db, workspace_id, user.id, write=True)
    collection = Collection(
        workspace_id=workspace_id, name=data.name.strip(), description=data.description
    )
    db.add(collection)
    db.commit()
    return collection


@router.patch("/collections/{collection_id}", response_model=CollectionOut)
def update_collection(
    collection_id: uuid.UUID, data: CollectionIn, db: Db, user: CurrentUser
) -> Collection:
    collection = db.get(Collection, collection_id)
    if collection is None:
        raise AppError(404, "not_found", "Collection not found.")
    membership(db, collection.workspace_id, user.id, write=True)
    collection.name, collection.description = data.name.strip(), data.description
    db.commit()
    return collection


@router.delete("/collections/{collection_id}", status_code=204)
def delete_collection(collection_id: uuid.UUID, db: Db, user: CurrentUser) -> None:
    collection = db.get(Collection, collection_id)
    if collection is None:
        raise AppError(404, "not_found", "Collection not found.")
    membership(db, collection.workspace_id, user.id, write=True)
    db.delete(collection)
    db.commit()
