import secrets
import smtplib
from datetime import timedelta
from email.message import EmailMessage

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.models.entities import (
    AuditLog,
    AuthSession,
    PasswordReset,
    User,
    Workspace,
    WorkspaceMember,
    utcnow,
)
from app.schemas.api import LoginIn, RegisterIn, ResetIn
from app.security.sessions import digest

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


def register(db: Session, data: RegisterIn) -> User:
    user = User(
        email=str(data.email).lower(),
        password_hash=hasher.hash(data.password),
        display_name=data.display_name.strip(),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            409,
            "account_exists",
            "Unable to create this account. Try signing in or resetting your password.",
        ) from exc
    workspace = Workspace(name=f"{user.display_name}'s workspace", owner_id=user.id)
    db.add(workspace)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    return user


def login(db: Session, data: LoginIn) -> User:
    user = db.scalar(select(User).where(User.email == str(data.email).lower()))
    try:
        hasher.verify(user.password_hash if user else DUMMY_HASH, data.password)
    except VerificationError as exc:
        raise AppError(401, "credentials", "Email or password is incorrect.") from exc
    if user is None or not user.is_active:
        raise AppError(401, "credentials", "Email or password is incorrect.")
    if hasher.check_needs_rehash(user.password_hash):
        user.password_hash = hasher.hash(data.password)
    db.add(AuditLog(user_id=user.id, action="login"))
    return user


def request_reset(db: Session, email: str) -> None:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        return
    token = secrets.token_urlsafe(48)
    record = PasswordReset(
        user_id=user.id, token_hash=digest(token), expires_at=utcnow() + timedelta(minutes=30)
    )
    db.add(record)
    db.flush()
    cfg = settings()
    mail = EmailMessage()
    mail["Subject"] = "Reset your KnowledgePilot password"
    mail["From"] = cfg.mail_from
    mail["To"] = user.email
    mail.set_content(
        f"Reset your password within 30 minutes: {cfg.frontend_url}/reset-password#token={token}\n\nIf you did not request this, ignore this message."
    )
    with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=10) as smtp:
        if cfg.smtp_tls:
            smtp.starttls()
        if cfg.smtp_user:
            smtp.login(cfg.smtp_user, cfg.smtp_password)
        smtp.send_message(mail)


def reset_password(db: Session, data: ResetIn) -> None:
    record = db.scalar(
        select(PasswordReset)
        .where(
            PasswordReset.token_hash == digest(data.token),
            PasswordReset.expires_at > utcnow(),
            PasswordReset.used.is_(False),
        )
        .with_for_update()
    )
    if record is None:
        raise AppError(
            400, "invalid_reset", "This reset link is invalid or expired. Request a new one."
        )
    user = db.get(User, record.user_id)
    if user is None:
        raise AppError(400, "invalid_reset", "This reset link is invalid.")
    user.password_hash = hasher.hash(data.password)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    db.execute(delete(PasswordReset).where(PasswordReset.user_id == user.id))
    db.add(AuditLog(user_id=user.id, action="password_reset"))
