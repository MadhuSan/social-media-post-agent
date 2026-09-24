from datetime import datetime
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.database import get_db
from ..db.models import FacebookPage, SocialAccount, User
from ..services.token_encryption import decrypt_token, encrypt_token


router = APIRouter(tags=["Social Accounts"])


class SocialAccountCreate(BaseModel):
    provider: str = Field(min_length=1, max_length=50)
    provider_user_id: str = Field(min_length=1, max_length=255)
    access_token: str = Field(min_length=1)
    token_expires_at: datetime | None = None


class SocialAccountResponse(BaseModel):
    id: UUID
    user_id: UUID
    provider: str
    provider_user_id: str
    token_expires_at: datetime | None

    model_config = {"from_attributes": True}


class FacebookPageResponse(BaseModel):
    id: UUID
    social_account_id: UUID
    page_id: str
    page_name: str | None

    model_config = {"from_attributes": True}


@router.post(
    "/users/{user_id}/social-accounts",
    response_model=SocialAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_social_account(
    user_id: UUID,
    account_data: SocialAccountCreate,
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    social_account = SocialAccount(
        user_id=user_id,
        provider=account_data.provider,
        provider_user_id=account_data.provider_user_id,
        access_token_encrypted=encrypt_token(account_data.access_token),
        token_expires_at=account_data.token_expires_at,
    )
    db.add(social_account)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The social account could not be created.",
        )

    await db.refresh(social_account)
    return social_account


@router.get(
    "/social-accounts/{social_account_id}/facebook-pages",
    response_model=list[FacebookPageResponse],
)
async def get_facebook_pages(
    social_account_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    social_account = await db.get(SocialAccount, social_account_id)
    if social_account is None:
        raise HTTPException(status_code=404, detail="Social account not found")

    if social_account.provider.lower() != "facebook":
        raise HTTPException(
            status_code=400,
            detail="The social account provider must be facebook.",
        )

    url = f"https://graph.facebook.com/{settings.META_API_VERSION}/me/accounts"
    params = {
        "fields": "id,name,access_token",
        "access_token": decrypt_token(social_account.access_token_encrypted),
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, timeout=30.0)

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Facebook returned an error while loading page details.",
        )

    pages = response.json().get("data", [])
    saved_pages = []

    for page_data in pages:
        page_id = page_data.get("id")
        page_access_token = page_data.get("access_token")
        if not page_id or not page_access_token:
            continue

        result = await db.execute(
            select(FacebookPage).where(
                FacebookPage.social_account_id == social_account_id,
                FacebookPage.page_id == page_id,
            )
        )
        page = result.scalar_one_or_none()

        if page is None:
            page = FacebookPage(
                social_account_id=social_account_id,
                page_id=page_id,
                page_name=page_data.get("name"),
                page_access_token_encrypted=encrypt_token(page_access_token),
            )
            db.add(page)
        else:
            page.page_name = page_data.get("name")
            page.page_access_token_encrypted = encrypt_token(page_access_token)

        saved_pages.append(page)

    await db.commit()

    for page in saved_pages:
        await db.refresh(page)

    return saved_pages