import secrets

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from services.token_store import save_user_access_token

from app.config import settings


router = APIRouter(
    prefix="/auth/meta",
    tags=["Meta Authentication"]
)


# TEMPORARY ONLY
# Later this will move to Redis/database/session storage.
oauth_states = set()


@router.get("/login")
async def meta_login():
    """
    Starts Meta OAuth flow.
    """

    # Generate a cryptographically secure random state
    state = secrets.token_urlsafe(32)

    # Temporary storage for Phase 1
    oauth_states.add(state)

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
):
    """
    Meta redirects the user here after login.
    """

    # User denied permission or Meta returned an error
    if error:
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
    if state not in oauth_states:
        raise HTTPException(
            status_code=400,
            detail="Invalid OAuth state"
        )

    # Remove state so it cannot be reused
    oauth_states.remove(state)

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

    async with httpx.AsyncClient() as client:

        response = await client.get(
            token_url,
            params=params,
            timeout=30.0
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail=response.json()
        )

    token_data = response.json()

    # PHASE 1 ONLY
    # DO NOT return access tokens to frontend in production.

    token_data = response.json()

    user_access_token = token_data.get("access_token")

    if not user_access_token:
        raise HTTPException(
            status_code=400,
            detail="Meta did not return an access token"
        )

    save_user_access_token(user_access_token)

    return {
    "message": "Meta authentication successful",
    "token_received": True,
}