import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    page_size: int


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    display_name: str = Field(min_length=1, max_length=100, pattern=r".*\S.*")


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class EmailIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    password: str = Field(min_length=12, max_length=128)


class UserOut(ORMModel):
    id: uuid.UUID
    email: str
    display_name: str
    preferences: dict[str, str]


class ProfileIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=100, pattern=r".*\S.*")
    theme: Literal["light", "dark", "system"] = "system"


class SessionOut(BaseModel):
    user: UserOut
    csrf_token: str


class NameIn(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=r".*\S.*")


class WorkspaceOut(ORMModel):
    id: uuid.UUID
    name: str
    owner_id: uuid.UUID


class CollectionIn(NameIn):
    description: str = Field(default="", max_length=2000)


class CollectionOut(ORMModel):
    id: uuid.UUID
    name: str
    description: str
    workspace_id: uuid.UUID


class DocumentOut(ORMModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    collection_id: uuid.UUID | None
    filename: str
    mime_type: str
    size_bytes: int
    status: str
    chunk_count: int
    page_count: int | None
    processing_error: str | None
    created_at: datetime


class DocumentPatch(BaseModel):
    filename: str | None = Field(
        default=None, min_length=1, max_length=255, pattern=r"^[^/\\\x00-\x1f]+$"
    )
    collection_id: uuid.UUID | None = None


class Scope(BaseModel):
    document_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)
    collection_id: uuid.UUID | None = None


class ConversationIn(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=160)
    scope: Scope = Field(default_factory=Scope)


class ConversationOut(ORMModel):
    id: uuid.UUID
    title: str
    retrieval_scope: Scope
    updated_at: datetime


class QuestionIn(BaseModel):
    content: str = Field(min_length=1, max_length=6000, pattern=r".*\S.*")
    regenerate: bool = False


class CitationOut(ORMModel):
    citation_number: int
    document_id: uuid.UUID | None
    chunk_id: uuid.UUID | None
    document_name: str
    excerpt: str
    page_number: int | None
    section_title: str | None


class MessageOut(ORMModel):
    id: uuid.UUID
    role: str
    content: str
    status: str
    created_at: datetime
    citations: list[CitationOut] = Field(default_factory=list)


class SearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    mode: Literal["semantic", "keyword", "hybrid"] = "hybrid"
    scope: Scope = Field(default_factory=Scope)
    limit: int = Field(default=10, ge=1, le=30)
    mime_type: str | None = None


class SearchHit(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    content: str
    page_number: int | None
    section_title: str | None
    score: float


class ChunkOut(ORMModel):
    id: uuid.UUID
    content: str
    page_number: int | None
    section_title: str | None
    chunk_index: int


class StatsOut(BaseModel):
    documents: int
    ready: int
    processing: int
    conversations: int
    storage_bytes: int
    ai_requests: int
    tokens: int
