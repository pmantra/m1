"""remove stripe_recipient_id

Revision ID: a7a55645f231
Revises: d9e810b26abb
Create Date: 2022-07-25 14:50:41.207475+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a7a55645f231"
down_revision = "66026f8f048f"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("practitioner_profile", "stripe_recipient_id")


def downgrade():
    op.add_column(
        "practitioner_profile",
        sa.Column("stripe_recipient_id", sa.String(50), nullable=True),
    )
