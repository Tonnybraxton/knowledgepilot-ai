"""Local-only browser test server. Production images do not contain this module."""

import asyncio
import os
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from unittest.mock import patch

import fakeredis
from fastapi import FastAPI
from redis import Redis
from sqlalchemy.engine import make_url

if os.environ.get("APP_ENV") != "test" or not os.environ.get("TEST_DATABASE_URL"):
    raise RuntimeError("Set APP_ENV=test and TEST_DATABASE_URL to a migrated disposable database")
if not (make_url(os.environ["TEST_DATABASE_URL"]).database or "").endswith("_test"):
    raise RuntimeError("The browser test database name must end in _test")
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ["OPENAI_API_KEY"] = ""
os.environ.setdefault(
    "TIKTOKEN_CACHE_DIR", str(Path(__file__).resolve().parents[2] / ".cache/tiktoken")
)

from app.ai import retrieval  # noqa: E402
from app.api.v1 import conversations as routes  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.security import rate_limit  # noqa: E402
from app.services import conversations, storage  # noqa: E402
from app.workers import ingestion  # noqa: E402
from app.workers import main as worker
from tests.doubles import TestAI  # noqa: E402


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    from contextlib import ExitStack

    with (
        tempfile.TemporaryDirectory(prefix="knowledgepilot-e2e-") as directory,
        ExitStack() as stack,
    ):
        cfg = settings()
        stack.enter_context(patch.object(cfg, "storage_backend", "local"))
        stack.enter_context(patch.object(cfg, "storage_local_path", directory))
        storage.storage.cache_clear()
        redis = (
            Redis.from_url(os.environ["TEST_REDIS_URL"])
            if os.environ.get("TEST_REDIS_URL")
            else fakeredis.FakeRedis()
        )
        for module in (rate_limit, conversations, routes, worker):
            stack.enter_context(patch.object(module, "redis_client", lambda: redis))
        provider = TestAI()
        stack.enter_context(patch.object(retrieval, "embedding_provider", lambda: provider))
        stack.enter_context(patch.object(ingestion, "embedding_provider", lambda: provider))
        stack.enter_context(patch.object(conversations, "generation_provider", lambda: provider))
        stopped = asyncio.Event()

        async def process_pending() -> None:
            while not stopped.is_set():
                await asyncio.to_thread(worker.tick)
                with suppress(TimeoutError):
                    await asyncio.wait_for(stopped.wait(), timeout=0.5)

        task = asyncio.create_task(process_pending())
        try:
            yield
        finally:
            stopped.set()
            await task
            storage.storage.cache_clear()
            redis.close()


app.router.lifespan_context = lifespan
