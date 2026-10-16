from datetime import datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import FacebookPage, SocialAccount


async def upsert_social_account(
    db: AsyncSession,
    *,
    user_id: UUID,
    provider: str,
    provider_user_id: str,
    access_token_encrypted: str,
    token_expires_at: datetime | None = None,
) -> SocialAccount:
    normalized_provider = provider.strip().lower()
    statement = (
        insert(SocialAccount)
        .values(
            user_id=user_id,
            provider=normalized_provider,
            provider_user_id=provider_user_id,
            access_token_encrypted=access_token_encrypted,
            token_expires_at=token_expires_at,
        )
        .on_conflict_do_update(
            constraint="uq_social_accounts_user_provider",
            set_={
                "provider_user_id": provider_user_id,
                "access_token_encrypted": access_token_encrypted,
                "token_expires_at": token_expires_at,
                "updated_at": func.now(),
            },
        )
        .returning(SocialAccount)
    )
    result = await db.execute(statement)
    return result.scalar_one()


async def upsert_facebook_page(
    db: AsyncSession,
    *,
    social_account_id: UUID,
    page_id: str,
    page_name: str | None,
    page_access_token_encrypted: str,
) -> FacebookPage:
    statement = (
        insert(FacebookPage)
        .values(
            social_account_id=social_account_id,
            page_id=page_id,
            page_name=page_name,
            page_access_token_encrypted=page_access_token_encrypted,
        )
        .on_conflict_do_update(
            constraint="uq_facebook_pages_account_page",
            set_={
                "page_name": page_name,
                "page_access_token_encrypted": page_access_token_encrypted,
                "updated_at": func.now(),
            },
        )
        .returning(FacebookPage)
    )
    result = await db.execute(statement)
    return result.scalar_one()
