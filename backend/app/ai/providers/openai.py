from collections.abc import AsyncIterator
from functools import lru_cache

from openai import AsyncOpenAI, OpenAI

from app.ai.providers.base import EmbeddingProvider, Embeddings, GenerationEvent, GenerationProvider
from app.core.config import settings
from app.core.errors import AppError


class OpenAIProvider:
    def __init__(self) -> None:
        cfg = settings()
        if not cfg.openai_api_key:
            raise AppError(
                503,
                "ai_configuration",
                "AI is not configured. Ask the workspace operator to configure the provider.",
            )
        self.client = OpenAI(api_key=cfg.openai_api_key, timeout=90, max_retries=2)
        self.async_client = AsyncOpenAI(api_key=cfg.openai_api_key, timeout=90, max_retries=1)

    def embed_batch(self, texts: list[str]) -> Embeddings:
        cfg = settings()
        response = self.client.embeddings.create(
            model=cfg.openai_embedding_model, input=texts, dimensions=cfg.embedding_dimensions
        )
        vectors = [item.embedding for item in sorted(response.data, key=lambda item: item.index)]
        if len(vectors) != len(texts) or any(len(v) != cfg.embedding_dimensions for v in vectors):
            raise ValueError("Embedding provider returned incompatible dimensions")
        return Embeddings(vectors, response.usage.total_tokens)

    async def stream(self, system: str, prompt: str) -> AsyncIterator[GenerationEvent]:
        stream = await self.async_client.responses.create(
            model=settings().openai_chat_model,
            instructions=system,
            input=prompt,
            stream=True,
            store=False,
            max_output_tokens=2200,
        )
        async with stream:
            async for event in stream:
                if event.type == "response.output_text.delta":
                    yield GenerationEvent(text=event.delta)
                elif event.type == "response.completed" and event.response.usage:
                    yield GenerationEvent(tokens=event.response.usage.total_tokens)
                elif event.type in {"error", "response.failed", "response.incomplete"}:
                    raise AppError(
                        502,
                        "provider_failed",
                        "The model could not complete this response. Please retry.",
                    )


@lru_cache
def openai_provider() -> OpenAIProvider:
    return OpenAIProvider()


def embedding_provider() -> EmbeddingProvider:
    return openai_provider()


def generation_provider() -> GenerationProvider:
    return openai_provider()
