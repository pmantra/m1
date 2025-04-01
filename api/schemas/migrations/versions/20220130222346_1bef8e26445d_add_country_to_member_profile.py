"""add country to member profile

Revision ID: 1bef8e26445d
Revises: 39aa76bf9fb7
Create Date: 2022-01-30 22:23:46.143987+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1bef8e26445d"
down_revision = "39aa76bf9fb7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "member_profile",
        sa.Column(
            "country_id",
            sa.Integer,
            nullable=True,
        ),
    )
    op.create_foreign_key(None, "member_profile", "country", ["country_id"], ["id"])


def downgrade():
    op.drop_constraint("member_profile_ibfk_4", "member_profile", type_="foreignkey")
    op.drop_column("member_profile", "country_id")
