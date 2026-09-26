import secrets
import uuid

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.ai.retrieval import retrieve
from app.core.config import settings
from app.core.errors import AppError
from app.models.entities import Citation, Conversation, Message
from app.repositories import access
from app.schemas.api import (
    CitationOut,
    ConversationIn,
    ConversationOut,
    MessageOut,
    Page,
    QuestionIn,
    SearchHit,
    SearchIn,
)
from app.security.rate_limit import rate_limit, redis_client
from app.security.sessions import CurrentUser, Db
from app.services.conversations import answer

router = APIRouter(tags=["Knowledge and conversations"])


@router.post("/workspaces/{workspace_id}/search", response_model=list[SearchHit])
def search(workspace_id: uuid.UUID, data: SearchIn, db: Db, user: CurrentUser) -> list[SearchHit]:
    access.membership(db, workspace_id, user.id)
    access.validate_scope(db, workspace_id, data.scope)
    rate_limit(f"search:{user.id}", 40)
    hits = retrieve(db, workspace_id, data.query, data.scope, data.mode, data.limit, data.mime_type)
    db.commit()
    return hits


@router.get("/workspaces/{workspace_id}/conversations", response_model=Page[ConversationOut])
def conversations(
    workspace_id: uuid.UUID,
    db: Db,
    user: CurrentUser,
    q: str = Query("", max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Page[ConversationOut]:
    access.membership(db, workspace_id, user.id)
    query = select(Conversation).where(
        Conversation.workspace_id == workspace_id, Conversation.user_id == user.id
    )
    if q:
        query = query.where(
            Conversation.title.ilike(f"%{q}%")
            | Conversation.id.in_(
                select(Message.conversation_id).where(Message.content.ilike(f"%{q}%"))
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(Conversation.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return Page(
        items=[ConversationOut.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/workspaces/{workspace_id}/conversations", response_model=ConversationOut, status_code=201
)
def create(
    workspace_id: uuid.UUID, data: ConversationIn, db: Db, user: CurrentUser
) -> Conversation:
    access.membership(db, workspace_id, user.id, write=True)
    access.validate_scope(db, workspace_id, data.scope)
    item = Conversation(
        workspace_id=workspace_id,
        user_id=user.id,
        title=data.title,
        retrieval_scope=data.scope.model_dump(mode="json"),
    )
    db.add(item)
    db.commit()
    return item


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
def detail(conversation_id: uuid.UUID, db: Db, user: CurrentUser) -> Conversation:
    return access.conversation(db, conversation_id, user.id)


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete(conversation_id: uuid.UUID, db: Db, user: CurrentUser) -> None:
    item = access.conversation(db, conversation_id, user.id)
    if redis_client().exists(f"chat:{conversation_id}"):
        raise AppError(409, "generating", "Stop the response before deleting this conversation.")
    db.delete(item)
    db.commit()


@router.get("/conversations/{conversation_id}/messages", response_model=Page[MessageOut])
def messages(
    conversation_id: uuid.UUID,
    db: Db,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
) -> Page[MessageOut]:
    access.conversation(db, conversation_id, user.id)
    query = select(Message).where(Message.conversation_id == conversation_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    # Pages are most-recent first, with chronological order within each page.
    # Batched question/answer inserts can share a timestamp. Sort the assistant
    # first here so reversing the page always places the question before it.
    rows = list(
        reversed(
            db.scalars(
                query.order_by(Message.created_at.desc(), Message.role.asc(), Message.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
    )
    citations = (
        list(
            db.scalars(
                select(Citation)
                .where(Citation.message_id.in_([row.id for row in rows]))
                .order_by(Citation.citation_number)
            )
        )
        if rows
        else []
    )
    items = [
        MessageOut.model_validate(row).model_copy(
            update={
                "citations": [
                    CitationOut.model_validate(citation)
                    for citation in citations
                    if citation.message_id == row.id
                ]
            }
        )
        for row in rows
    ]
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "SSE delta, done, and error events. Only done content has validated citation references.",
            "content": {"text/event-stream": {}},
        }
    },
)
def ask(
    conversation_id: uuid.UUID, data: QuestionIn, db: Db, user: CurrentUser
) -> StreamingResponse:
    item = access.conversation(db, conversation_id, user.id)
    access.membership(db, item.workspace_id, user.id, write=True)
    rate_limit(f"chat:{user.id}", 20)
    token = secrets.token_hex(16)
    if not redis_client().set(f"chat:{conversation_id}", token, nx=True, ex=300):
        raise AppError(
            409, "generating", "A response is already being generated in this conversation."
        )
    try:
        if data.regenerate:
            previous = db.scalar(
                select(Message)
                .where(Message.conversation_id == item.id, Message.role == "user")
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(1)
            )
            if previous is None:
                raise AppError(400, "no_question", "There is no question to regenerate.")
            question = previous.content
        else:
            question = data.content.strip()
            db.add(Message(conversation_id=item.id, role="user", content=question))
        if item.title == "New conversation":
            item.title = question[:160]
        assistant = Message(
            conversation_id=item.id,
            role="assistant",
            content="",
            status="streaming",
            model=settings().openai_chat_model,
        )
        db.add(assistant)
        db.commit()
    except Exception:
        redis_client().delete(f"chat:{conversation_id}")
        raise
    return StreamingResponse(
        answer(item.id, assistant.id, question, token),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
