import asyncio
import json
from uuid import UUID

from langchain_community.tools import tool
from sqlalchemy import select

from backend.app.db.database import AsyncSessionLocal
from backend.app.db.models import FacebookPage
from backend.app.services.token_encryption import decrypt_token
from backend.app.config import settings

async def _get_facebook_pages_info(social_account_id: UUID) -> list[dict[str, str]]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(FacebookPage)
            .where(FacebookPage.social_account_id == social_account_id)
            .order_by(FacebookPage.created_at)
        )
        pages = result.scalars().all()
        if not pages:
            raise RuntimeError("No Facebook page is stored for this social account")

        return [
            {
                "id": page.page_id,
                "name": page.page_name or "",
                "access_token": decrypt_token(page.page_access_token_encrypted),
            }
            for page in pages
        ]


@tool
def get_facebook_pages(social_account_id: str):
    """Get all stored Facebook pages so the user can select one."""
    return asyncio.run(_get_facebook_pages_info(UUID(social_account_id)))


@tool
def get_facebook_page_info(social_account_id: str, page_id: str):
    """Get the selected Facebook page for a social account."""
    pages = asyncio.run(_get_facebook_pages_info(UUID(social_account_id)))
    for page in pages:
        if page["id"] == page_id:
            return page
    raise ValueError(f"Facebook page '{page_id}' is not available for this social account")


@tool
def get_facebook_page_info(social_account_id: str):
    "Get the first stored Facebook page for a social account from PostgreSQL."
    return asyncio.run(_get_facebook_page_info(UUID(social_account_id)))

@tool
def post_content(page_id,access_token,content):
    "Post content to the Facebook page using the Graph API. Content will be provided by the LLM by previous tool call"

    if content is None:
        content = "Content is provided by LLM."
    url = f"https://graph.facebook.com/{settings.META_API_VERSION}/{page_id}/feed"

    data={
    "message": content,
    "access_token": access_token
    }

    import requests

    response = requests.post(url, data=data, timeout=30)
    if not response.ok:
        try:
            response_data = response.json()
        except json.JSONDecodeError:
            response_data = response.text
        raise RuntimeError(f"Facebook post failed: {response_data}")

    return response.json()
    


if __name__ == "__main__":
    page_data = get_facebook_page_info("SOCIAL_ACCOUNT_UUID")
    post_content(
        page_data["id"],
        page_data["access_token"],
        "Content is provided by LLM.",
    )

