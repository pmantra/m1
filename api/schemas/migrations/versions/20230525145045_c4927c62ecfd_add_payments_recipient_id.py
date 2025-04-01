"""add-payments-recipient-id

Revision ID: c4927c62ecfd
Revises: 90b371bed622
Create Date: 2023-05-25 14:50:45.087952+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c4927c62ecfd"
down_revision = "90b371bed622"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "fertility_clinic",
        sa.Column(
            "payments_recipient_id",
            sa.String(36),
            nullable=True,
            default=None,
            comment="Stripe id associated with recipient account",
        ),
    )


def downgrade():
    op.drop_column("fertility_clinic", "payments_recipient_id")
