"""Server-side login sessions for the Connfas UI.

Streamlit keeps its own state only in memory for one browser connection. The
Meta OAuth flow is a full-page redirect to Facebook and back, which starts a new
Streamlit session, so the login has to be restorable from something that lives
outside Streamlit. That is what these sessions are: the UI keeps the opaque token
in its URL and exchanges it for the user at the start of every new session.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import AppSession, SocialAccount, User


SESSION_TTL = timedelta(hours=12)


@dataclass(frozen=True)
class SessionInfo:
    user_id: UUID
    email: str | None
    social_account_id: UUID | None


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def create_session(db: AsyncSession, user_id: UUID) -> str:
    """Create a session for the user and return the raw token (not stored)."""
    now = datetime.now(timezone.utc)
    await db.execute(delete(AppSession).where(AppSession.expires_at <= now))

    token = secrets.token_urlsafe(32)
    db.add(
        AppSession(
            token_hash=hash_token(token),
            user_id=user_id,
            expires_at=now + SESSION_TTL,
        )
    )
    await db.flush()
    return token


async def resolve_session(db: AsyncSession, token: str) -> SessionInfo | None:
    """Return the session owner, or None if the token is unknown or expired.

    Deliberately does not consume the token: a page refresh, a reconnecting
    browser tab or a second Streamlit session must all be able to restore it.
    """
    session = await db.get(AppSession, hash_token(token))
    if session is None or session.expires_at <= datetime.now(timezone.utc):
        return None

    user = await db.get(User, session.user_id)
    if user is None:
        return None

    social_account_id = await db.scalar(
        select(SocialAccount.id).where(
            SocialAccount.user_id == user.id,
            SocialAccount.provider == "facebook",
        )
    )
    return SessionInfo(
        user_id=user.id,
        email=user.email,
        social_account_id=social_account_id,
    )


async def revoke_session(db: AsyncSession, token: str) -> None:
    await db.execute(
        delete(AppSession).where(AppSession.token_hash == hash_token(token))
    )
