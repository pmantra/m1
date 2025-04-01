"""Add spam fields to forum posts

Revision ID: bf3d24ff2cdc
Revises: 753cc14fdcd6
Create Date: 2021-04-23 15:36:03.610237+00:00

"""
import enum

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "bf3d24ff2cdc"
down_revision = "753cc14fdcd6"
branch_labels = None
depends_on = None


class PostSpamStatus(enum.Enum):
    NONE = "NONE"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    SPAM = "SPAM"


def upgrade():
    op.add_column("post", sa.Column("recaptcha_score", sa.Float, nullable=True))
    op.add_column(
        "post",
        sa.Column(
            "spam_status",
            sa.Enum(PostSpamStatus),
            nullable=False,
            default=PostSpamStatus.NONE,
        ),
    )


def downgrade():
    op.drop_column("post", "recaptcha_score")
    op.drop_column("post", "spam_status")
