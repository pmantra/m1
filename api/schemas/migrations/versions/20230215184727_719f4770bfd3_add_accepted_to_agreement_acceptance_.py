"""add_accepted_to_agreement_acceptance_table

Revision ID: 719f4770bfd3
Revises: 7632237e43f0
Create Date: 2023-02-15 18:47:27.477739+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "719f4770bfd3"
down_revision = "905ca5f52adf"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "agreement_acceptance",
        sa.Column("accepted", sa.Boolean, nullable=True, default=True),
    )


def downgrade():
    op.drop_column("agreement_acceptance", "accepted")
