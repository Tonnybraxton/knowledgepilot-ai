import uuid
from collections import defaultdict
from typing import Protocol

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.ai.providers.openai import embedding_provider
from app.core.config import settings
from app.models.entities import Document, DocumentChunk, UsageRecord
from app.schemas.api import Scope, SearchHit


class Reranker(Protocol):
    def rank(self, hits: list[SearchHit], limit: int) -> list[SearchHit]: ...


class FusionReranker:
    def rank(self, hits: list[SearchHit], limit: int) -> list[SearchHit]:
        return sorted(hits, key=lambda hit: (-hit.score, str(hit.chunk_id)))[:limit]


def reciprocal_rank_fusion(rankings: list[list[uuid.UUID]]) -> dict[uuid.UUID, float]:
    scores: dict[uuid.UUID, float] = defaultdict(float)
    for ranking in rankings:
        for index, chunk_id in enumerate(dict.fromkeys(ranking), start=1):
            scores[chunk_id] += 1 / (60 + index)
    return dict(scores)


def scoped_query(
    workspace_id: uuid.UUID, scope: Scope, mime: str | None = None
) -> Select[tuple[DocumentChunk, str]]:
    query = (
        select(DocumentChunk, Document.filename)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(
            DocumentChunk.workspace_id == workspace_id,
            Document.workspace_id == workspace_id,
            Document.status == "ready",
        )
    )
    if scope.collection_id:
        query = query.where(Document.collection_id == scope.collection_id)
    if scope.document_ids:
        query = query.where(Document.id.in_(scope.document_ids))
    if mime:
        query = query.where(Document.mime_type == mime)
    return query


def retrieve(
    db: Session,
    workspace_id: uuid.UUID,
    query: str,
    scope: Scope,
    mode: str = "hybrid",
    limit: int = 8,
    mime: str | None = None,
) -> list[SearchHit]:
    base = scoped_query(workspace_id, scope, mime)
    rankings: list[list[uuid.UUID]] = []
    candidates: dict[uuid.UUID, SearchHit] = {}
    # No query embedding request when there is no indexed content in the selected scope.
    if db.execute(base.limit(1)).first() is None:
        return []
    if mode in {"semantic", "hybrid"}:
        embedded = embedding_provider().embed_batch([query])
        db.add(
            UsageRecord(
                workspace_id=workspace_id,
                model=settings().openai_embedding_model,
                operation="query_embedding",
                tokens=embedded.tokens,
            )
        )
        distance = DocumentChunk.embedding.cosine_distance(embedded.vectors[0])
        rows = db.execute(
            base.where(
                Document.embedding_model == settings().openai_embedding_model, distance < 0.8
            )
            .order_by(distance)
            .limit(limit * 4)
        ).all()
        rankings.append([chunk.id for chunk, _ in rows])
        for chunk, name in rows:
            candidates[chunk.id] = hit(chunk, name)
    if mode in {"keyword", "hybrid"}:
        tsquery = func.websearch_to_tsquery("english", query)
        rows = db.execute(
            base.where(DocumentChunk.search_vector.op("@@")(tsquery))
            .order_by(func.ts_rank_cd(DocumentChunk.search_vector, tsquery).desc())
            .limit(limit * 4)
        ).all()
        rankings.append([chunk.id for chunk, _ in rows])
        for chunk, name in rows:
            candidates[chunk.id] = hit(chunk, name)
    scores = reciprocal_rank_fusion(rankings)
    for chunk_id, candidate in candidates.items():
        candidate.score = scores[chunk_id]
    return FusionReranker().rank(list(candidates.values()), limit)


def hit(chunk: DocumentChunk, name: str) -> SearchHit:
    return SearchHit(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        document_name=name,
        content=chunk.content,
        page_number=chunk.page_number,
        section_title=chunk.section_title,
        score=0,
    )
