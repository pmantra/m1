"""add practitioner billing field

Revision ID: 596184410a7b
Revises: 6283041ec8b7
Create Date: 2020-05-12 21:34:22.138912

"""
from alembic import op
import sqlalchemy as sa
import enum


# revision identifiers, used by Alembic.
revision = "596184410a7b"
down_revision = "6283041ec8b7"
branch_labels = None
depends_on = None


def upgrade():
    class BillingTypes(enum.Enum):
        DCW_PC = "DCW PC"
        DCW_PA = "DCW PA"
        DN = "DN"

    op.add_column(
        "practitioner_profile",
        sa.Column("billing_org", sa.Enum(BillingTypes), nullable=True),
    )


def downgrade():
    op.drop_column("practitioner_profile", "billing_org")
