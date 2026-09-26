import re
from dataclasses import dataclass
from functools import lru_cache

import tiktoken

from app.ai.extraction import Passage
from app.core.config import settings


@lru_cache
def encoding() -> tiktoken.Encoding:
    return tiktoken.get_encoding("cl100k_base")


def token_count(text: str) -> int:
    return len(encoding().encode(text, disallowed_special=()))


@dataclass(frozen=True)
class Chunk:
    content: str
    token_count: int
    page_number: int | None
    section_title: str | None


def chunk_passages(passages: list[Passage]) -> list[Chunk]:
    cfg = settings()
    result: list[Chunk] = []
    for passage in passages:
        passage_start = len(result)
        text = passage.text.replace("\x00", "").replace("\r\n", "\n").strip()
        buffer: list[int] = []
        units = re.split(r"\n\s*\n|(?<=[.!?])\s+(?=[A-Z])", text)
        for unit in units:
            tokens = (
                encoding().encode(unit.strip() + "\n", disallowed_special=())
                if unit.strip()
                else []
            )
            while tokens:
                available = cfg.chunk_max_tokens - len(buffer)
                buffer.extend(tokens[:available])
                tokens = tokens[available:]
                if len(buffer) >= cfg.chunk_target_tokens:
                    decoded = encoding().decode(buffer).strip()
                    result.append(
                        Chunk(decoded, token_count(decoded), passage.page, passage.section)
                    )
                    buffer = buffer[-cfg.chunk_overlap_tokens :] if cfg.chunk_overlap_tokens else []
        if buffer and (
            len(result) == passage_start
            or encoding().decode(buffer).strip() not in result[-1].content
        ):
            decoded = encoding().decode(buffer).strip()
            if decoded:
                result.append(Chunk(decoded, token_count(decoded), passage.page, passage.section))
    return result
