from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol


@dataclass
class Embeddings:
    vectors: list[list[float]]
    tokens: int


@dataclass
class GenerationEvent:
    text: str = ""
    tokens: int = 0


class EmbeddingProvider(Protocol):
    def embed_batch(self, texts: list[str]) -> Embeddings: ...


class GenerationProvider(Protocol):
    def stream(self, system: str, prompt: str) -> AsyncIterator[GenerationEvent]: ...
