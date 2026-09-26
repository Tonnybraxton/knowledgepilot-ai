"""Deterministic provider doubles. Never imported by production app modules."""

import hashlib
import json
import math
import re
from collections.abc import AsyncIterator

from app.ai.providers.base import Embeddings, GenerationEvent


class TestAI:
    __test__ = False

    def embed_batch(self, texts: list[str]) -> Embeddings:
        vectors = []
        for text in texts:
            vector = [0.0] * 1536
            for word in re.findall(r"\w+", text.lower()):
                index = int.from_bytes(hashlib.sha256(word.encode()).digest()[:4]) % 1536
                vector[index] += 1
            norm = math.sqrt(sum(value * value for value in vector)) or 1
            vectors.append([value / norm for value in vector])
        return Embeddings(vectors, sum(len(text.split()) for text in texts))

    async def stream(self, system: str, prompt: str) -> AsyncIterator[GenerationEvent]:
        evidence = json.loads(prompt)["untrusted_evidence"]
        first = json.loads(evidence.splitlines()[0])
        yield GenerationEvent(text=first["excerpt"])
        yield GenerationEvent(text=" [1]", tokens=20)
