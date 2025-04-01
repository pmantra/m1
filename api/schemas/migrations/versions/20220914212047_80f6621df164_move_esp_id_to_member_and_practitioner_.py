"""Move esp id to member and practitioner profile

Revision ID: 80f6621df164
Revises: dcaf02846079
Create Date: 2022-09-14 21:20:47.024408+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "80f6621df164"
down_revision = "dcaf02846079"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "member_profile",
        sa.Column(
            "esp_id",
            sa.String(36),
        ),
    )
    op.add_column(
        "practitioner_profile",
        sa.Column(
            "esp_id",
            sa.String(36),
        ),
    )


def downgrade():
    op.drop_column("member_profile", "esp_id")
    op.drop_column("practitioner_profile", "esp_id")
