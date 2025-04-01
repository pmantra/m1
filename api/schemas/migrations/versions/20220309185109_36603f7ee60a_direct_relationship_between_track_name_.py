"""Create a direct relationship between a track name and the HDC assessment slug

Revision ID: 36603f7ee60a
Revises: 53a6f7b74e7f
Create Date: 2022-03-09 18:51:09.406438+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "36603f7ee60a"
down_revision = "53a6f7b74e7f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assessment_track_relationships",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "assessment_onboarding_slug", sa.String(150), nullable=False, unique=True
        ),
        sa.Column("track_name", sa.String(150), nullable=False, unique=True),
        sa.Column("modified_at", sa.DateTime),
    )


def downgrade():
    op.drop_table("assessment_track_relationships")
