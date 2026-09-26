import os
from collections.abc import Iterator
from pathlib import Path

import pytest

os.environ["APP_ENV"] = "test"
os.environ["OPENAI_API_KEY"] = ""
os.environ.setdefault(
    "TIKTOKEN_CACHE_DIR", str(Path(__file__).resolve().parents[2] / ".cache/tiktoken")
)
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]


@pytest.fixture
def test_services(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    if not os.environ.get("TEST_DATABASE_URL"):
        pytest.skip("Set TEST_DATABASE_URL to a migrated disposable PostgreSQL/pgvector database")
    from sqlalchemy.engine import make_url

    assert (make_url(os.environ["TEST_DATABASE_URL"]).database or "").endswith("_test"), (
        "Use a database name ending in _test"
    )
    import fakeredis
    from redis import Redis

    from app.ai import retrieval
    from app.core.config import settings
    from app.security import rate_limit
    from app.services import conversations, storage
    from app.workers import ingestion
    from tests.doubles import TestAI

    cfg = settings()
    monkeypatch.setattr(cfg, "storage_backend", "local")
    monkeypatch.setattr(cfg, "storage_local_path", str(tmp_path / "uploads"))
    storage.storage.cache_clear()
    redis = (
        Redis.from_url(os.environ["TEST_REDIS_URL"])
        if os.environ.get("TEST_REDIS_URL")
        else fakeredis.FakeRedis()
    )
    monkeypatch.setattr(rate_limit, "redis_client", lambda: redis)
    # Modules import the factory directly; all use the same isolated Redis instance.
    monkeypatch.setattr(conversations, "redis_client", lambda: redis)
    from app.api.v1 import conversations as routes
    from app.workers import main as worker

    monkeypatch.setattr(routes, "redis_client", lambda: redis)
    monkeypatch.setattr(worker, "redis_client", lambda: redis)
    provider = TestAI()
    monkeypatch.setattr(retrieval, "embedding_provider", lambda: provider)
    monkeypatch.setattr(ingestion, "embedding_provider", lambda: provider)
    monkeypatch.setattr(conversations, "generation_provider", lambda: provider)
    yield
    storage.storage.cache_clear()
    redis.close()
