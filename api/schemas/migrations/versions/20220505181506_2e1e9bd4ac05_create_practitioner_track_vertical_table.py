"""Create Provider Vertical Track Table

Revision ID: 2e1e9bd4ac05
Revises: 9dfe24ddc756
Create Date: 2022-05-05 18:15:06.681469+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "2e1e9bd4ac05"
down_revision = "566842b09bea"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "practitioner_track_vertical",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "practitioner_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False
        ),
        sa.Column("track_name", sa.String(120), nullable=False),
        sa.Column(
            "vertical_id", sa.Integer, sa.ForeignKey("vertical.id"), nullable=False
        ),
    )


def downgrade():
    op.drop_table("practitioner_track_vertical")
