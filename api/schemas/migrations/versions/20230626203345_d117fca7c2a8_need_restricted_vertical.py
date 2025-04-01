"""need-restricted-vertical

Revision ID: d117fca7c2a8
Revises: 2be0a9ca9ce0
Create Date: 2023-06-26 20:33:45.163808+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d117fca7c2a8"
down_revision = "2be0a9ca9ce0"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE need_vertical ADD COLUMN
        id INTEGER NOT NULL AUTO_INCREMENT, ADD INDEX ix_need_vertical_id (id),
        ALGORITHM=inplace, LOCK=shared;
        """
    )

    op.create_table(
        "need_restricted_vertical",
        sa.Column(
            "need_vertical_id",
            sa.Integer,
            sa.ForeignKey("need_vertical.id", ondelete="CASCADE", onupdate="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "specialty_id",
            sa.Integer,
            sa.ForeignKey("specialty.id", ondelete="CASCADE", onupdate="CASCADE"),
            primary_key=True,
        ),
        sa.Column("created_at", sa.DateTime),
        sa.Column("modified_at", sa.DateTime),
    )


def downgrade():
    op.drop_table("need_restricted_vertical")
    op.drop_column("need_vertical", "id")
