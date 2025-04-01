"""Create gdpr user request table

Revision ID: fcbbca8d4f70
Revises: 3130938c18af
Create Date: 2022-08-15 21:25:26.803919+00:00

"""
import enum

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "fcbbca8d4f70"
down_revision = "567b535a29c9"
branch_labels = None
depends_on = None


def upgrade():
    class GDPRRequestStatus(enum.Enum):
        PENDING = "PENDING"
        COMPLETED = "COMPLETED"

    class GDPRRequestSource(enum.Enum):
        MEMBER = "MEMBER"
        ADMIN = "ADMIN"

    op.create_table(
        "gdpr_user_request",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("user_email", sa.String(120), nullable=False),
        sa.Column(
            "status",
            sa.Enum(GDPRRequestStatus),
            nullable=False,
            default=GDPRRequestStatus.PENDING,
        ),
        sa.Column("source", sa.Enum(GDPRRequestSource), nullable=False),
    )


def downgrade():
    op.drop_table("gdpr_user_request")
