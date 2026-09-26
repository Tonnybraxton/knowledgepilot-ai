import time
import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.v1 import auth, conversations, documents, workspaces
from app.core.config import settings
from app.core.errors import AppError
from app.db.session import engine
from app.security.rate_limit import redis_client
from app.services.storage import storage

structlog.configure(
    processors=[structlog.processors.TimeStamper(fmt="iso"), structlog.processors.JSONRenderer()]
)
log = structlog.get_logger()


class RequestGuard:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        if scope["method"] not in {"GET", "HEAD", "OPTIONS"}:
            origin = headers.get(b"origin", b"").decode()
            if origin != settings().frontend_url:
                await JSONResponse(
                    {"error": {"code": "origin", "message": "Request origin is not allowed."}}, 403
                )(scope, receive, send)
                return
        length = headers.get(b"content-length", b"0")
        if length.isdigit() and int(length) > settings().max_upload_bytes + 1024 * 1024:
            await JSONResponse(
                {"error": {"code": "file_size", "message": "Request body is too large."}}, 413
            )(scope, receive, send)
            return
        request_id = str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        started = time.monotonic()

        async def secured_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] += [
                    (b"x-request-id", request_id.encode()),
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"same-origin"),
                    (b"cache-control", b"no-store"),
                ]
                if settings().app_env == "production":
                    message["headers"].append(
                        (b"strict-transport-security", b"max-age=31536000; includeSubDomains")
                    )
                log.info(
                    "http_request",
                    request_id=request_id,
                    method=scope["method"],
                    path=scope["path"],
                    status=message["status"],
                    latency_ms=round((time.monotonic() - started) * 1000),
                )
            await send(message)

        await self.app(scope, receive, secured_send)


app = FastAPI(
    title="KnowledgePilot AI",
    version="0.1.0",
    description="Private document intelligence with grounded, verifiable citations.",
    docs_url="/docs" if settings().app_env != "production" else None,
)
app.add_middleware(RequestGuard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings().frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)
for router in (auth.router, workspaces.router, documents.router, conversations.router):
    app.include_router(router, prefix="/api/v1")


@app.exception_handler(AppError)
async def app_error(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": exc.code, "message": exc.message}},
        exc.status,
        headers={"Retry-After": "60"} if exc.status == 429 else None,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        {
            "error": {
                "code": "validation",
                "message": "Check the submitted fields.",
                "fields": [
                    {"path": ".".join(map(str, e["loc"])), "message": e["msg"]}
                    for e in exc.errors()
                ],
            }
        },
        422,
    )


@app.exception_handler(IntegrityError)
async def conflict(request: Request, exc: IntegrityError) -> JSONResponse:
    return JSONResponse(
        {
            "error": {
                "code": "conflict",
                "message": "This operation conflicts with existing data. Refresh and retry.",
            }
        },
        409,
    )


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    log.error(
        "request_failed",
        request_id=getattr(request.state, "request_id", None),
        error_type=type(exc).__name__,
    )
    return JSONResponse(
        {
            "error": {
                "code": "internal",
                "message": "The service could not complete your request. Please retry.",
            }
        },
        500,
    )


@app.get("/health", tags=["Operations"])
def health() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/ready", tags=["Operations"])
def ready() -> JSONResponse:
    checks: dict[str, bool] = {}
    try:
        with engine.connect() as conn:
            checks["database"] = bool(conn.scalar(text("SELECT 1 FROM alembic_version")))
            checks["vector"] = bool(
                conn.scalar(text("SELECT 1 FROM pg_extension WHERE extname='vector'"))
            )
    except Exception:
        checks["database"] = False
    try:
        checks["redis"] = bool(redis_client().ping())
        checks["worker"] = bool(redis_client().get("worker:heartbeat"))
    except Exception:
        checks["redis"] = False
    try:
        checks["storage"] = storage().healthy()
    except Exception:
        checks["storage"] = False
    return JSONResponse(
        {"status": "ready" if all(checks.values()) else "unavailable", "checks": checks},
        200 if all(checks.values()) else 503,
    )
