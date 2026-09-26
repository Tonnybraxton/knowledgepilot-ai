import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator

import structlog
from anyio import CancelScope
from sqlalchemy import select

from app.ai.context import build_context, retrieval_query, validate_citations
from app.ai.prompts.grounding import SYSTEM
from app.ai.providers.openai import generation_provider
from app.ai.retrieval import retrieve
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.entities import Citation, Conversation, Message, UsageRecord, utcnow
from app.repositories.access import membership, validate_scope
from app.schemas.api import CitationOut, Scope, SearchHit
from app.security.rate_limit import redis_client


def event(kind: str, data: object) -> str:
    return f"event: {kind}\ndata: {json.dumps(data, default=str)}\n\n"


async def answer(
    conversation_id: uuid.UUID, assistant_id: uuid.UUID, question: str, lock_token: str
) -> AsyncIterator[str]:
    started = time.monotonic()
    content = ""
    status = "failed"
    tokens = 0
    citations: list[CitationOut] = []
    source_hits: list[SearchHit] = []
    error: str | None = None

    def load_history() -> tuple[uuid.UUID, uuid.UUID, Scope, list[Message]] | None:
        with SessionLocal() as db:
            conversation = db.get(Conversation, conversation_id)
            if conversation is None:
                return None
            recent = list(
                reversed(
                    db.scalars(
                        select(Message)
                        .where(
                            Message.conversation_id == conversation_id,
                            Message.id != assistant_id,
                            Message.status == "complete",
                        )
                        .order_by(Message.created_at.desc(), Message.role.asc(), Message.id.desc())
                        .limit(8)
                    ).all()
                )
            )
            return (
                conversation.workspace_id,
                conversation.user_id,
                Scope.model_validate(conversation.retrieval_scope),
                recent,
            )

    try:
        loaded = await asyncio.to_thread(load_history)
        if loaded is None:
            return
        workspace_id, user_id, scope, recent = loaded
        history = [{"role": item.role, "content": item.content[:2500]} for item in recent]
        recent_questions = [item.content for item in recent if item.role == "user"]
        if recent_questions and recent_questions[-1] == question:
            recent_questions.pop()

        def prepare() -> tuple[str, list[SearchHit]]:
            with SessionLocal() as db:
                membership(db, workspace_id, user_id)
                validate_scope(db, workspace_id, scope)
                hits = retrieve(
                    db,
                    workspace_id,
                    retrieval_query(question, recent_questions),
                    scope,
                    limit=settings().rag_top_k,
                )
                db.commit()
                return build_context(hits)

        context, source_hits = await asyncio.to_thread(prepare)
        if not source_hits:
            content = "I couldn’t find relevant evidence in the selected documents. Try a more specific question, broaden the selected sources, or upload a document with the information you need."
            yield event("delta", {"text": content})
        else:
            prompt = json.dumps(
                {"question": question, "recent_history": history, "untrusted_evidence": context}
            )
            async with asyncio.timeout(150):
                async for chunk in generation_provider().stream(SYSTEM, prompt):
                    if chunk.text:
                        content += chunk.text
                        yield event("delta", {"text": chunk.text})
                    tokens += chunk.tokens
            content, numbers = validate_citations(content, len(source_hits))
            if not numbers:
                content = "The available evidence did not support a verifiable cited answer. Try refining your question or selecting more relevant documents."
            citations = [
                CitationOut(
                    citation_number=number,
                    document_id=hit.document_id,
                    chunk_id=hit.chunk_id,
                    document_name=hit.document_name,
                    excerpt=hit.content,
                    page_number=hit.page_number,
                    section_title=hit.section_title,
                )
                for number, hit in enumerate(source_hits, 1)
                if number in numbers
            ]
        status = "complete"
    except (asyncio.CancelledError, GeneratorExit):
        status = "cancelled"
        raise
    except Exception as exc:
        error = "The answer could not be completed. Your question is saved; please retry."
        structlog.get_logger().error(
            "generation_failed", conversation_id=str(conversation_id), error_type=type(exc).__name__
        )
    finally:
        latency = int((time.monotonic() - started) * 1000)

        def persist() -> None:
            with SessionLocal() as db:
                message = db.get(Message, assistant_id)
                if message:
                    message.content = content
                    message.status = status
                    message.token_usage = tokens
                    message.latency_ms = latency
                    # Re-check sources in this transaction: deletion/reprocessing may have happened during generation.
                    from app.models.entities import Document, DocumentChunk

                    for citation in citations:
                        if citation.document_id and db.get(Document, citation.document_id) is None:
                            citation.document_id = None
                        if citation.chunk_id and db.get(DocumentChunk, citation.chunk_id) is None:
                            citation.chunk_id = None
                        db.add(Citation(message_id=assistant_id, **citation.model_dump()))
                    conversation = db.get(Conversation, conversation_id)
                    if tokens and conversation:
                        db.add(
                            UsageRecord(
                                workspace_id=conversation.workspace_id,
                                model=settings().openai_chat_model,
                                operation="generation",
                                tokens=tokens,
                                latency_ms=latency,
                            )
                        )
                    if conversation:
                        conversation.updated_at = utcnow()
                    db.commit()

        # A disconnected SSE client cancels its AnyIO scope. Still save the
        # partial answer and release its lease without blocking the event loop.
        with CancelScope(shield=True):
            try:
                await asyncio.to_thread(persist)
            finally:
                await asyncio.to_thread(
                    redis_client().eval,
                    "if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('DEL',KEYS[1]) end return 0",
                    1,
                    f"chat:{conversation_id}",
                    lock_token,
                )
    if error:
        yield event("error", {"message": error})
    else:
        yield event(
            "done",
            {
                "id": assistant_id,
                "content": content,
                "status": status,
                "citations": [citation.model_dump(mode="json") for citation in citations],
            },
        )
