import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.database import get_db
from ..db.models import OAuthState, User
from ..services.sessions import create_session, resolve_session
from ..services.social_accounts import upsert_social_account
from ..services.token_encryption import encrypt_token


router = APIRouter(
    prefix="/auth/meta",
    tags=["Meta Authentication"]
)


OAUTH_STATE_TTL = timedelta(minutes=10)


class FrontendHandoffRequest(BaseModel):
    handoff_token: str = Field(min_length=32, max_length=128)


class FrontendHandoffResponse(BaseModel):
    user_id: UUID
    email: str | None
    social_account_id: UUID | None


def _frontend_url(**params: str) -> str:
    """FRONTEND_URL with the given query parameters merged in."""
    parts = urlsplit(settings.FRONTEND_URL)
    query = dict(parse_qsl(parts.query))
    query.update(params)
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path or "/", urlencode(query), "")
    )


def _redirect_to_frontend(**params: str) -> RedirectResponse:
    return RedirectResponse(url=_frontend_url(**params), status_code=302)


async def _redirect_to_frontend_with_session(
    db: AsyncSession,
    user_id: UUID,
    meta_status: str,
) -> RedirectResponse:
    """Send the browser back to the UI together with a restorable login session.

    The trip to Facebook and back is a full-page navigation, which starts a brand
    new Streamlit session. The session token is how the UI gets the user back,
    whether Facebook succeeded, was cancelled, or failed.
    """
    token = await create_session(db, user_id)
    await db.commit()
    return _redirect_to_frontend(meta_status=meta_status, sid=token)


async def _oauth_failure(
    db: AsyncSession,
    frontend: bool,
    user_id: UUID,
    status_code: int,
    detail: str,
) -> RedirectResponse:
    if frontend:
        return await _redirect_to_frontend_with_session(db, user_id, "error")
    raise HTTPException(status_code=status_code, detail=detail)


@router.post(
    "/frontend-handoff",
    response_model=FrontendHandoffResponse,
)
async def consume_frontend_handoff(
    request: FrontendHandoffRequest,
    db: AsyncSession = Depends(get_db),
):
    """Kept for backwards compatibility; prefer POST /auth/session/restore.

    The handoff token is now a login session token, so it can be presented more
    than once (page refresh, reconnecting tab) until it expires.
    """
    info = await resolve_session(db, request.handoff_token)
    if info is None:
        raise HTTPException(
            status_code=400,
            detail="The Facebook login handoff is invalid or expired. Please connect again.",
        )
    return FrontendHandoffResponse(
        user_id=info.user_id,
        email=info.email,
        social_account_id=info.social_account_id,
    )


@router.get("/login")
async def meta_login(
    user_id: UUID = Query(...),
    frontend: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    """
    Starts Meta OAuth flow.
    """

    if await db.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Generate a cryptographically secure random state
    state = secrets.token_urlsafe(32)

    # Persisted (not in process memory) so a backend reload or a second worker
    # between "login" and "callback" cannot invalidate the flow.
    now = datetime.now(timezone.utc)
    await db.execute(delete(OAuthState).where(OAuthState.expires_at <= now))
    db.add(
        OAuthState(
            state=state,
            user_id=user_id,
            frontend=frontend,
            expires_at=now + OAUTH_STATE_TTL,
        )
    )
    await db.commit()

    # Permissions we need for the Facebook Page flow.
    scopes = [
        "pages_show_list",
        "pages_read_engagement",
        "pages_manage_posts",
    ]

    authorization_url = (
        f"https://www.facebook.com/"
        f"{settings.META_API_VERSION}/dialog/oauth"
    )

    params = {
        "client_id": settings.META_APP_ID,
        "redirect_uri": settings.META_REDIRECT_URI,
        "state": state,
        "scope": ",".join(scopes),
        "response_type": "code",
    }

    request = httpx.Request(
        "GET",
        authorization_url,
        params=params
    )

    return RedirectResponse(
        url=str(request.url),
        status_code=302
    )


@router.get("/callback")
async def meta_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_reason: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """
    Meta redirects the user here after login.
    """

    now = datetime.now(timezone.utc)
    oauth_state = await db.get(OAuthState, state) if state else None
    if oauth_state is not None and oauth_state.expires_at <= now:
        await db.delete(oauth_state)
        await db.commit()
        oauth_state = None

    # User denied permission or Meta returned an error
    if error:
        if oauth_state is not None and oauth_state.frontend:
            user_id = oauth_state.user_id
            await db.delete(oauth_state)
            await db.commit()
            return await _redirect_to_frontend_with_session(db, user_id, "denied")
        raise HTTPException(
            status_code=400,
            detail={
                "error": error,
                "reason": error_reason,
                "description": error_description,
            }
        )

    # Check required OAuth parameters
    if not code or not state:
        raise HTTPException(
            status_code=400,
            detail="Missing OAuth code or state"
        )

    # Validate state
    if oauth_state is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state"
        )

    # Remove state so it cannot be reused
    user_id = oauth_state.user_id
    redirect_to_frontend = oauth_state.frontend
    await db.delete(oauth_state)
    await db.commit()

    token_url = (
        f"https://graph.facebook.com/"
        f"{settings.META_API_VERSION}/oauth/access_token"
    )

    params = {
        "client_id": settings.META_APP_ID,
        "client_secret": settings.META_APP_SECRET,
        "redirect_uri": settings.META_REDIRECT_URI,
        "code": code,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                token_url,
                params=params,
                timeout=30.0
            )

            if response.status_code != 200:
                return await _oauth_failure(
                    db,
                    redirect_to_frontend,
                    user_id,
                    502,
                    "Meta could not complete the authorization.",
                )

            try:
                token_data = response.json()
            except ValueError:
                return await _oauth_failure(
                    db,
                    redirect_to_frontend,
                    user_id,
                    502,
                    "Meta returned an invalid authorization response.",
                )
            user_access_token = token_data.get("access_token")
            if not user_access_token:
                return await _oauth_failure(
                    db,
                    redirect_to_frontend,
                    user_id,
                    502,
                    "Meta did not return an access token.",
                )

            user_response = await client.get(
                f"https://graph.facebook.com/{settings.META_API_VERSION}/me",
                params={"fields": "id", "access_token": user_access_token},
                timeout=30.0,
            )
    except httpx.HTTPError as error:
        if redirect_to_frontend:
            return await _redirect_to_frontend_with_session(db, user_id, "error")
        raise HTTPException(
            status_code=502,
            detail="Meta could not complete the authorization.",
        ) from error

    if user_response.status_code != 200:
        return await _oauth_failure(
            db,
            redirect_to_frontend,
            user_id,
            502,
            "Meta did not return the authenticated user details.",
        )

    try:
        provider_user_id = user_response.json().get("id")
    except ValueError:
        return await _oauth_failure(
            db,
            redirect_to_frontend,
            user_id,
            502,
            "Meta returned invalid user details.",
        )
    if not provider_user_id:
        return await _oauth_failure(
            db,
            redirect_to_frontend,
            user_id,
            502,
            "Meta user ID is missing.",
        )

    social_account = await upsert_social_account(
        db,
        user_id=user_id,
        provider="facebook",
        provider_user_id=provider_user_id,
        access_token_encrypted=encrypt_token(user_access_token),
    )
    await db.commit()

    if redirect_to_frontend:
        return await _redirect_to_frontend_with_session(db, user_id, "success")

    return {
        "message": "Meta authentication successful",
        "social_account_id": str(social_account.id),
    }
