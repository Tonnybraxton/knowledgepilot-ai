import hashlib
import secrets
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models.entities import AuthSession, User, utcnow

COOKIE = "kp_session"
Db = Annotated[Session, Depends(get_db)]


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_session(db: Session, user: User, response: Response) -> AuthSession:
    token = secrets.token_urlsafe(48)
    session = AuthSession(
        user_id=user.id,
        token_hash=digest(token),
        csrf_token=secrets.token_urlsafe(32),
        expires_at=utcnow() + timedelta(days=settings().session_days),
    )
    db.add(session)
    response.set_cookie(
        COOKIE,
        token,
        httponly=True,
        secure=settings().app_env == "production",
        samesite="lax",
        max_age=settings().session_days * 86400,
        path="/",
    )
    return session


def current_session(request: Request, db: Db) -> AuthSession:
    token = request.cookies.get(COOKIE)
    session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == digest(token or ""), AuthSession.expires_at > utcnow()
        )
    )
    if session is None:
        raise AppError(401, "session_expired", "Your session expired. Please sign in again.")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf = request.headers.get("x-csrf-token", "")
        if not secrets.compare_digest(csrf, session.csrf_token):
            raise AppError(403, "csrf", "Refresh the page and try again.")
    return session


def current_user(db: Db, session: Annotated[AuthSession, Depends(current_session)]) -> User:
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise AppError(401, "session_expired", "Please sign in again.")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
