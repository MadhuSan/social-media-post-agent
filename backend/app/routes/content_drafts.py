from datetime import datetime, timezone
import logging
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from ..config import settings
from ..db.database import get_db
from ..db.models import ContentDraft, FacebookPage, SocialAccount, User
from ..services.token_encryption import decrypt_token


router = APIRouter(prefix="/users/{user_id}/content-drafts", tags=["Content Drafts"])
logger = logging.getLogger(__name__)


class ContentDraftCreate(BaseModel):
    social_account_id: UUID
    search_query: str = Field(min_length=1)


class ContentDraftResponse(BaseModel):
    id: UUID
    user_id: UUID
    content: str
    status: str
    facebook_page_id: UUID | None
    facebook_post_id: str | None
    reviewed_at: datetime | None
    published_at: datetime | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ContentDraftApproval(BaseModel):
    facebook_page_id: UUID


async def get_user_or_404(user_id: UUID, db: AsyncSession) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("", response_model=ContentDraftResponse, status_code=status.HTTP_201_CREATED)
async def create_content_draft(
    user_id: UUID,
    generation_request: ContentDraftCreate,
    db: AsyncSession = Depends(get_db),
):
    await get_user_or_404(user_id, db)

    account_result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.id == generation_request.social_account_id,
            SocialAccount.user_id == user_id,
            SocialAccount.provider == "facebook",
        )
    )
    account = account_result.scalar_one_or_none()
    if account is None:
        raise HTTPException(
            status_code=404,
            detail="Facebook social account not found for this user",
        )

    try:
        from agent import graph
        from prompts.birdsPrompt import system_prompt, user_prompt

        result = await run_in_threadpool(
            graph.invoke,
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "search_query": generation_request.search_query,
                "social_account_id": str(account.id),
            },
        )
        draft_id = UUID(result["draft_result"]["id"])
    except Exception as error:
        logger.exception("Content draft agent failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The agent could not generate or save a content draft.",
        ) from error

    draft = await db.get(ContentDraft, draft_id)
    if draft is None or draft.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The agent did not return a saved draft for this user.",
        )
    return draft


@router.get("", response_model=list[ContentDraftResponse])
async def list_content_drafts(
    user_id: UUID,
    draft_status: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
):
    await get_user_or_404(user_id, db)
    query = select(ContentDraft).where(ContentDraft.user_id == user_id)
    if draft_status is not None:
        query = query.where(ContentDraft.status == draft_status)
    query = query.order_by(ContentDraft.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/{draft_id}/approve", response_model=ContentDraftResponse)
async def approve_content_draft(
    user_id: UUID,
    draft_id: UUID,
    approval: ContentDraftApproval,
    db: AsyncSession = Depends(get_db),
):
    await get_user_or_404(user_id, db)

    draft_result = await db.execute(
        select(ContentDraft).where(
            ContentDraft.id == draft_id,
            ContentDraft.user_id == user_id,
        )
    )
    draft = draft_result.scalar_one_or_none()
    if draft is None:
        raise HTTPException(status_code=404, detail="Content draft not found")
    if draft.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Content draft is already {draft.status}.",
        )

    page_result = await db.execute(
        select(FacebookPage)
        .join(SocialAccount)
        .where(
            FacebookPage.id == approval.facebook_page_id,
            SocialAccount.user_id == user_id,
            SocialAccount.provider == "facebook",
        )
    )
    page = page_result.scalar_one_or_none()
    if page is None:
        raise HTTPException(
            status_code=404,
            detail="Facebook page not found for this user",
        )

    now = datetime.now(timezone.utc)
    draft.status = "approved"
    draft.facebook_page_id = page.id
    draft.reviewed_at = now
    await db.flush()

    url = f"https://graph.facebook.com/{settings.META_API_VERSION}/{page.page_id}/feed"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                data={
                    "message": draft.content,
                    "access_token": decrypt_token(page.page_access_token_encrypted),
                },
                timeout=30.0,
            )
        if response.status_code >= 400:
            raise RuntimeError("Facebook returned an error while publishing the draft")
        post_id = response.json().get("id")
        if not post_id:
            raise RuntimeError("Facebook did not return a post ID")
    except (httpx.HTTPError, RuntimeError) as error:
        draft.status = "failed"
        draft.error_message = str(error)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Facebook could not publish the approved draft.",
        ) from error

    draft.status = "published"
    draft.facebook_post_id = post_id
    draft.published_at = datetime.now(timezone.utc)
    draft.error_message = None
    await db.commit()
    await db.refresh(draft)
    return draft