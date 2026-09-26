import smtplib
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Request, Response

from app.models.entities import AuditLog, AuthSession
from app.schemas.api import EmailIn, LoginIn, ProfileIn, RegisterIn, ResetIn, SessionOut, UserOut
from app.security.rate_limit import rate_limit
from app.security.sessions import COOKIE, CurrentUser, Db, current_session, issue_session
from app.services import auth

router = APIRouter(tags=["Authentication"])


def auth_limit(request: Request) -> None:
    rate_limit("auth:" + (request.client.host if request.client else "unknown"), 15)


@router.post(
    "/auth/register", response_model=SessionOut, status_code=201, dependencies=[Depends(auth_limit)]
)
def register(data: RegisterIn, response: Response, db: Db) -> SessionOut:
    user = auth.register(db, data)
    session = issue_session(db, user, response)
    db.commit()
    return SessionOut(user=UserOut.model_validate(user), csrf_token=session.csrf_token)


@router.post("/auth/login", response_model=SessionOut, dependencies=[Depends(auth_limit)])
def login(data: LoginIn, response: Response, db: Db) -> SessionOut:
    user = auth.login(db, data)
    session = issue_session(db, user, response)
    db.commit()
    return SessionOut(user=UserOut.model_validate(user), csrf_token=session.csrf_token)


@router.get("/auth/session", response_model=SessionOut)
def session(
    user: CurrentUser, active: Annotated[AuthSession, Depends(current_session)]
) -> SessionOut:
    return SessionOut(user=UserOut.model_validate(user), csrf_token=active.csrf_token)


@router.post("/auth/logout", status_code=204)
def logout(
    response: Response, db: Db, active: Annotated[AuthSession, Depends(current_session)]
) -> None:
    db.add(AuditLog(user_id=active.user_id, action="logout"))
    db.delete(active)
    db.commit()
    response.delete_cookie(COOKIE, path="/")


@router.post("/auth/forgot-password", status_code=202, dependencies=[Depends(auth_limit)])
def forgot(data: EmailIn, db: Db) -> dict[str, str]:
    try:
        auth.request_reset(db, str(data.email))
        db.commit()
    except (smtplib.SMTPException, OSError):
        db.rollback()
        structlog.get_logger().error("password_reset_delivery_failed")
    return {
        "message": "If that account exists, a reset link will be emailed. Check your inbox or try again shortly."
    }


@router.post("/auth/reset-password", status_code=204, dependencies=[Depends(auth_limit)])
def reset(data: ResetIn, db: Db) -> None:
    auth.reset_password(db, data)
    db.commit()


@router.patch("/users/me", response_model=UserOut)
def profile(data: ProfileIn, user: CurrentUser, db: Db) -> UserOut:
    user.display_name = data.display_name.strip()
    user.preferences = {"theme": data.theme}
    db.commit()
    return UserOut.model_validate(user)
