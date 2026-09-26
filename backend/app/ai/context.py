import json
import re

from app.ai.chunking import token_count
from app.core.config import settings
from app.schemas.api import SearchHit


def build_context(hits: list[SearchHit]) -> tuple[str, list[SearchHit]]:
    selected: list[SearchHit] = []
    blocks: list[str] = []
    used = 0
    for hit in hits:
        block = json.dumps(
            {
                "citation": len(selected) + 1,
                "document": hit.document_name,
                "page": hit.page_number,
                "section": hit.section_title,
                "excerpt": hit.content,
            },
            ensure_ascii=False,
        )
        size = token_count(block)
        if used + size > settings().context_max_tokens:
            continue
        selected.append(hit)
        blocks.append(block)
        used += size
    return "\n".join(blocks), selected


def validate_citations(answer: str, source_count: int) -> tuple[str, set[int]]:
    used: set[int] = set()

    def replace(match: re.Match[str]) -> str:
        number = int(match.group(1))
        if 1 <= number <= source_count:
            used.add(number)
            return match.group(0)
        return ""

    return re.sub(r"\[(\d+)\]", replace, answer), used


def retrieval_query(question: str, recent_questions: list[str]) -> str:
    # Deterministic bounded expansion avoids an extra model call on every turn.
    followup = re.search(
        r"\b(it|its|that|those|these|they|their|second|first|above|more|compare|summari[sz]e)\b",
        question,
        re.I,
    )
    if followup and recent_questions:
        return recent_questions[-1][:1500] + "\nFollow-up: " + question
    return question
