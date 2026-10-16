"""deduplicate social accounts and Facebook pages

Revision ID: c2d4e6f8a102
Revises: b8c1d4e6f902
"""
from collections import defaultdict
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2d4e6f8a102"
down_revision: Union[str, Sequence[str], None] = "b8c1d4e6f902"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _deduplicate_existing_rows(connection) -> None:
    social_accounts = sa.table(
        "social_accounts",
        sa.column("id"),
        sa.column("user_id"),
        sa.column("provider"),
        sa.column("created_at"),
        sa.column("updated_at"),
    )
    facebook_pages = sa.table(
        "facebook_pages",
        sa.column("id"),
        sa.column("social_account_id"),
        sa.column("page_id"),
        sa.column("created_at"),
        sa.column("updated_at"),
    )
    content_drafts = sa.table(
        "content_drafts",
        sa.column("facebook_page_id"),
    )

    accounts = connection.execute(sa.select(social_accounts)).mappings().all()
    account_groups = defaultdict(list)
    for account in accounts:
        provider = account["provider"].strip().lower()
        account_groups[(account["user_id"], provider)].append(account)

    for (_, normalized_provider), group in account_groups.items():
        group.sort(
            key=lambda row: (
                row["updated_at"],
                row["created_at"],
                str(row["id"]),
            ),
            reverse=True,
        )
        canonical = group[0]
        account_ids = [row["id"] for row in group]

        connection.execute(
            sa.update(social_accounts)
            .where(social_accounts.c.id == canonical["id"])
            .values(provider=normalized_provider)
        )

        pages = connection.execute(
            sa.select(facebook_pages)
            .where(facebook_pages.c.social_account_id.in_(account_ids))
        ).mappings().all()
        page_groups = defaultdict(list)
        for page in pages:
            page_groups[page["page_id"]].append(page)

        for page_group in page_groups.values():
            page_group.sort(
                key=lambda row: (
                    row["updated_at"],
                    row["created_at"],
                    str(row["id"]),
                ),
                reverse=True,
            )
            canonical_page = page_group[0]
            page_ids = [row["id"] for row in page_group]
            duplicate_page_ids = page_ids[1:]

            if duplicate_page_ids:
                connection.execute(
                    sa.update(content_drafts)
                    .where(
                        content_drafts.c.facebook_page_id.in_(
                            [canonical_page["id"], *duplicate_page_ids]
                        )
                    )
                    .values(facebook_page_id=canonical_page["id"])
                )
                connection.execute(
                    sa.delete(facebook_pages)
                    .where(facebook_pages.c.id.in_(duplicate_page_ids))
                )

            connection.execute(
                sa.update(facebook_pages)
                .where(facebook_pages.c.id == canonical_page["id"])
                .values(social_account_id=canonical["id"])
            )

        duplicate_account_ids = [row["id"] for row in group[1:]]
        if duplicate_account_ids:
            connection.execute(
                sa.delete(social_accounts)
                .where(social_accounts.c.id.in_(duplicate_account_ids))
            )


def upgrade() -> None:
    connection = op.get_bind()
    _deduplicate_existing_rows(connection)
    op.create_unique_constraint(
        "uq_social_accounts_user_provider",
        "social_accounts",
        ["user_id", "provider"],
    )
    op.create_unique_constraint(
        "uq_facebook_pages_account_page",
        "facebook_pages",
        ["social_account_id", "page_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_facebook_pages_account_page",
        "facebook_pages",
        type_="unique",
    )
    op.drop_constraint(
        "uq_social_accounts_user_provider",
        "social_accounts",
        type_="unique",
    )
