import secrets
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.database import get_db
from ..services.social_accounts import upsert_social_account
from ..services.token_encryption import encrypt_token


router = APIRouter(
    prefix="/auth/meta",
    tags=["Meta Authentication"]
)


# TEMPORARY ONLY
# Later this will move to Redis/database/session storage.
oauth_states: dict[str, UUID] = {}
oauth_frontend_redirects: set[str] = set()


def _redirect_to_frontend(**params: str) -> RedirectResponse:
    separator = "&" if "?" in settings.FRONTEND_URL else "?"
    return RedirectResponse(
        url=f"{settings.FRONTEND_URL}{separator}{urlencode(params)}",
        status_code=302,
    )


def _oauth_failure(
    frontend: bool,
    status_code: int,
    detail: str,
) -> RedirectResponse:
    if frontend:
        return _redirect_to_frontend(meta_status="error")
    raise HTTPException(status_code=status_code, detail=detail)


@router.get("/login")
async def meta_login(
    user_id: UUID = Query(...),
    frontend: bool = Query(default=False),
):
    """
    Starts Meta OAuth flow.
    """

    # Generate a cryptographically secure random state
    state = secrets.token_urlsafe(32)

    # Temporary storage for Phase 1
    oauth_states[state] = user_id
    if frontend:
        oauth_frontend_redirects.add(state)

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

    # User denied permission or Meta returned an error
    if error:
        if state and state in oauth_frontend_redirects:
            oauth_frontend_redirects.discard(state)
            oauth_states.pop(state, None)
            return _redirect_to_frontend(meta_status="denied")
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
    user_id = oauth_states.get(state)
    if user_id is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state"
        )

    # Remove state so it cannot be reused
    oauth_states.pop(state, None)
    redirect_to_frontend = state in oauth_frontend_redirects
    oauth_frontend_redirects.discard(state)

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
                return _oauth_failure(
                    redirect_to_frontend,
                    502,
                    "Meta could not complete the authorization.",
                )

            try:
                token_data = response.json()
            except ValueError:
                return _oauth_failure(
                    redirect_to_frontend,
                    502,
                    "Meta returned an invalid authorization response.",
                )
            user_access_token = token_data.get("access_token")
            if not user_access_token:
                return _oauth_failure(
                    redirect_to_frontend,
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
            return _redirect_to_frontend(meta_status="error")
        raise HTTPException(
            status_code=502,
            detail="Meta could not complete the authorization.",
        ) from error

    if user_response.status_code != 200:
        return _oauth_failure(
            redirect_to_frontend,
            502,
            "Meta did not return the authenticated user details.",
        )

    try:
        provider_user_id = user_response.json().get("id")
    except ValueError:
        return _oauth_failure(
            redirect_to_frontend,
            502,
            "Meta returned invalid user details.",
        )
    if not provider_user_id:
        return _oauth_failure(
            redirect_to_frontend,
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

    result = {
        "message": "Meta authentication successful",
        "social_account_id": str(social_account.id),
    }
    if redirect_to_frontend:
        return _redirect_to_frontend(
            meta_status="success",
            social_account_id=str(social_account.id),
        )
    return result