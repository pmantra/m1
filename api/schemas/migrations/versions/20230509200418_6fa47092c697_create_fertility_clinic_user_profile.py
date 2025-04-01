"""create fertility clinic user profile

Revision ID: 6fa47092c697
Revises: afdf8b97ee7a
Create Date: 2023-05-09 20:04:18.728439+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6fa47092c697"
down_revision = "afdf8b97ee7a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "fertility_clinic_user_profile",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("uuid", sa.String(36), nullable=False),
        sa.Column("first_name", sa.String(40), nullable=False),
        sa.Column("last_name", sa.String(40), nullable=False),
        # user_id is a logical foreign key to user
        sa.Column(
            "user_id",
            sa.Integer,
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.TIMESTAMP, nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "modified_at",
            sa.TIMESTAMP,
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )


def downgrade():
    op.drop_table("fertility_clinic_user_profile")
