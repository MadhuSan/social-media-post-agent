"""add content drafts

Revision ID: a3f5d7c9e1b2
Revises: 71591d9e5890
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3f5d7c9e1b2"
down_revision: Union[str, Sequence[str], None] = "71591d9e5890"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "content_drafts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("facebook_page_id", sa.UUID(), nullable=True),
        sa.Column("facebook_post_id", sa.String(length=255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["facebook_page_id"], ["facebook_pages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("content_drafts")