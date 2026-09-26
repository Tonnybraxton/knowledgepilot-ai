import asyncio
import io
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from reportlab.pdfgen.canvas import Canvas
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.main import app
from app.models.entities import (
    AuthSession,
    DocumentChunk,
    Message,
    PasswordReset,
    ProcessingJob,
    WorkspaceMember,
    utcnow,
)
from app.security.sessions import digest
from app.workers.ingestion import process_job

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("test_services")]


def registered() -> tuple[TestClient, str, str]:
    client = TestClient(app, client=(str(uuid.uuid4()), 50000))
    client.headers["Origin"] = "http://localhost:3000"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"{uuid.uuid4().hex}@example.com",
            "password": "integration-password-42",
            "display_name": "Researcher",
        },
    )
    assert response.status_code == 201, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    workspace = client.get("/api/v1/workspaces").json()[0]["id"]
    return client, workspace, response.json()["user"]["id"]


def upload(
    client: TestClient,
    workspace: str,
    content: bytes = b"Orion cobalt batteries have 80 kWh capacity.",
    name: str = "specs.txt",
) -> str:
    response = client.post(
        f"/api/v1/workspaces/{workspace}/documents", files={"file": (name, content)}
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def process(document_id: str) -> str:
    with SessionLocal() as db:
        job_id = db.scalar(
            select(ProcessingJob.id)
            .where(ProcessingJob.document_id == uuid.UUID(document_id))
            .order_by(ProcessingJob.created_at.desc())
        )
    assert job_id
    process_job(str(job_id))
    return str(job_id)


def conversation(client: TestClient, workspace: str, documents: list[str] | None = None) -> str:
    response = client.post(
        f"/api/v1/workspaces/{workspace}/conversations",
        json={"scope": {"document_ids": documents or []}},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def test_pdf_upload_processing_search_chat_and_citation() -> None:
    client, workspace, _ = registered()
    data = io.BytesIO()
    pdf = Canvas(data)
    pdf.drawString(72, 700, "Orion cobalt batteries have 80 kWh capacity.")
    pdf.save()
    doc = upload(client, workspace, data.getvalue(), "orion.pdf")
    job = process(doc)
    assert client.get(f"/api/v1/documents/{doc}").json()["status"] == "ready"
    process_job(job)
    chunks = client.get(f"/api/v1/documents/{doc}/chunks").json()
    assert chunks["total"] == 1 and chunks["items"][0]["page_number"] == 1
    for mode in ["semantic", "keyword", "hybrid"]:
        hits = client.post(
            f"/api/v1/workspaces/{workspace}/search",
            json={
                "query": "Orion cobalt batteries",
                "mode": mode,
                "scope": {"document_ids": [doc]},
            },
        )
        assert hits.status_code == 200 and hits.json()[0]["document_id"] == doc
    chat = conversation(client, workspace, [doc])
    response = client.post(
        f"/api/v1/conversations/{chat}/messages",
        json={"content": "What is the Orion cobalt battery capacity?"},
    )
    assert response.status_code == 200 and "event: done" in response.text, response.text
    messages = client.get(f"/api/v1/conversations/{chat}/messages").json()["items"]
    citation = messages[-1]["citations"][0]
    assert citation["document_id"] == doc and citation["page_number"] == 1
    assert "80 kWh" in citation["excerpt"] and "[1]" in messages[-1]["content"]
    exact = client.get(f"/api/v1/documents/{doc}/chunks?chunk_id={citation['chunk_id']}").json()
    assert exact["total"] == 1 and exact["items"][0]["id"] == citation["chunk_id"]
    original = client.get(f"/api/v1/documents/{doc}/source")
    assert original.content.startswith(b"%PDF-")
    assert "attachment" in original.headers["content-disposition"]
    assert client.delete(f"/api/v1/documents/{doc}").status_code == 204
    archived = client.get(f"/api/v1/conversations/{chat}/messages").json()["items"][-1][
        "citations"
    ][0]
    assert archived["document_id"] is None and archived["chunk_id"] is None
    assert "80 kWh" in archived["excerpt"]


def test_message_order_with_equal_timestamps() -> None:
    client, workspace, _ = registered()
    chat = conversation(client, workspace)
    timestamp = utcnow()
    with SessionLocal() as db:
        # Batched inserts can share a timestamp, particularly on Windows.
        db.add_all(
            [
                Message(
                    conversation_id=uuid.UUID(chat),
                    role=role,
                    content=role,
                    created_at=timestamp,
                )
                for role in ("assistant", "user")
            ]
        )
        db.commit()
    path = f"/api/v1/conversations/{chat}/messages"
    rows = client.get(path).json()["items"]
    assert [row["role"] for row in rows] == ["user", "assistant"]
    newest = client.get(f"{path}?page_size=1&page=1").json()["items"]
    older = client.get(f"{path}?page_size=1&page=2").json()["items"]
    assert newest[0]["id"] == rows[1]["id"]
    assert older[0]["id"] == rows[0]["id"]


def test_tenant_isolation_for_sources_search_scope_and_history() -> None:
    alice, workspace_a, _ = registered()
    bob, workspace_b, _ = registered()
    doc_a, doc_b = (
        upload(alice, workspace_a),
        upload(bob, workspace_b, b"Orion private tenant secret 99 kWh."),
    )
    process(doc_a)
    process(doc_b)
    chat = conversation(alice, workspace_a)
    for path in [
        f"/documents/{doc_a}",
        f"/documents/{doc_a}/source",
        f"/documents/{doc_a}/chunks",
        f"/conversations/{chat}",
        f"/conversations/{chat}/messages",
        f"/workspaces/{workspace_a}/stats",
    ]:
        assert bob.get("/api/v1" + path).status_code == 404
    assert bob.delete(f"/api/v1/documents/{doc_a}").status_code == 404
    assert (
        bob.post(
            f"/api/v1/workspaces/{workspace_b}/search",
            json={"query": "Orion", "scope": {"document_ids": [doc_a]}},
        ).status_code
        == 404
    )
    hits = alice.post(
        f"/api/v1/workspaces/{workspace_a}/search", json={"query": "Orion", "mode": "keyword"}
    ).json()
    assert hits and all(hit["document_id"] == doc_a for hit in hits)
    collection = bob.post(
        f"/api/v1/workspaces/{workspace_b}/collections", json={"name": "Private"}
    ).json()
    assert (
        alice.patch(
            f"/api/v1/documents/{doc_a}", json={"collection_id": collection["id"]}
        ).status_code
        == 404
    )


def test_csrf_origin_revocation_expiration_and_viewer_role() -> None:
    client, workspace, user = registered()
    csrf = client.headers.pop("X-CSRF-Token")
    assert client.post("/api/v1/workspaces", json={"name": "forbidden"}).status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    assert (
        client.post(
            "/api/v1/workspaces",
            json={"name": "forbidden"},
            headers={"Origin": "https://attacker.invalid"},
        ).status_code
        == 403
    )
    with SessionLocal() as db:
        membership = db.scalar(
            select(WorkspaceMember).where(
                WorkspaceMember.user_id == uuid.UUID(user),
                WorkspaceMember.workspace_id == uuid.UUID(workspace),
            )
        )
        assert membership
        membership.role = "viewer"
        db.commit()
    assert (
        client.post(
            f"/api/v1/workspaces/{workspace}/documents", files={"file": ("test.txt", b"text")}
        ).status_code
        == 403
    )
    cookie = client.cookies.get("kp_session")
    assert client.post("/api/v1/auth/logout").status_code == 204
    client.cookies.set("kp_session", cookie or "")
    assert client.get("/api/v1/auth/session").status_code == 401
    other, _, other_user = registered()
    with SessionLocal() as db:
        session = db.scalar(select(AuthSession).where(AuthSession.user_id == uuid.UUID(other_user)))
        assert session
        session.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert other.get("/api/v1/auth/session").status_code == 401


def test_reset_is_single_use_and_revokes_sessions() -> None:
    client, _, user = registered()
    token = "test-reset-token-" + uuid.uuid4().hex
    with SessionLocal() as db:
        db.add(
            PasswordReset(
                user_id=uuid.UUID(user),
                token_hash=digest(token),
                expires_at=utcnow() + timedelta(minutes=1),
            )
        )
        db.commit()
    payload = {"token": token, "password": "replacement-password-42"}
    assert client.post("/api/v1/auth/reset-password", json=payload).status_code == 204
    assert client.get("/api/v1/auth/session").status_code == 401
    assert client.post("/api/v1/auth/reset-password", json=payload).status_code == 400


def test_duplicate_reprocessing_and_bounded_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.workers import ingestion

    client, workspace, _ = registered()
    doc = upload(client, workspace)
    duplicate = client.post(
        f"/api/v1/workspaces/{workspace}/documents",
        files={"file": ("copy.txt", b"Orion cobalt batteries have 80 kWh capacity.")},
    )
    assert duplicate.status_code == 409
    process(doc)
    assert client.post(f"/api/v1/documents/{doc}/processing-jobs").status_code == 202
    process(doc)
    with SessionLocal() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(DocumentChunk)
                .where(DocumentChunk.document_id == uuid.UUID(doc))
            )
            == 1
        )
    failed = upload(client, workspace, b"Different content for a failing document")

    def unavailable() -> None:
        raise RuntimeError("Provider unavailable")

    monkeypatch.setattr(ingestion, "embedding_provider", unavailable)
    job = process(failed)
    process_job(job)
    process_job(job)
    process_job(job)
    with SessionLocal() as db:
        item = db.get(ProcessingJob, uuid.UUID(job))
        assert item and item.attempts == 3 and item.status == "failed"
    assert client.get(f"/api/v1/documents/{failed}").json()["status"] == "failed"


@pytest.mark.parametrize("cancel_scope", [False, True])
def test_empty_scope_abstention_provider_failure_and_cancel(
    monkeypatch: pytest.MonkeyPatch,
    cancel_scope: bool,
) -> None:
    from app.security import rate_limit
    from app.services import conversations

    client, workspace, _ = registered()
    empty = conversation(client, workspace)
    response = client.post(
        f"/api/v1/conversations/{empty}/messages", json={"content": "What is known?"}
    )
    assert "event: done" in response.text and "couldn" in response.text
    doc = upload(client, workspace)
    process(doc)
    chat = conversation(client, workspace, [doc])
    with SessionLocal() as db:
        assistant = Message(
            conversation_id=uuid.UUID(chat), role="assistant", content="", status="streaming"
        )
        db.add(assistant)
        db.commit()
        assistant_id = assistant.id
    rate_limit.redis_client().set(f"chat:{chat}", "cancel-token", ex=300)

    async def cancel() -> None:
        from anyio import CancelScope

        stream = conversations.answer(
            uuid.UUID(chat), assistant_id, "Orion cobalt batteries", "cancel-token"
        )
        with CancelScope() as scope:
            first = await anext(stream)
            assert "event: delta" in first
            if cancel_scope:
                scope.cancel()
            await stream.aclose()

    asyncio.run(cancel())
    with SessionLocal() as db:
        item = db.get(Message, assistant_id)
        assert item and item.status == "cancelled"
    assert not rate_limit.redis_client().exists(f"chat:{chat}")

    def broken() -> None:
        raise RuntimeError("Do not expose provider details")

    monkeypatch.setattr(conversations, "generation_provider", broken)
    result = client.post(
        f"/api/v1/conversations/{chat}/messages", json={"content": "Orion cobalt batteries"}
    )
    assert "event: error" in result.text and "provider details" not in result.text
    assert (
        client.get(f"/api/v1/conversations/{chat}/messages").json()["items"][-1]["status"]
        == "failed"
    )
