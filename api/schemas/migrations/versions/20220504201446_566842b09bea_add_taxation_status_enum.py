"""Add taxation status enum

Revision ID: 566842b09bea
Revises: 9dfe24ddc756
Create Date: 2022-05-04 20:14:46.771297+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "566842b09bea"
down_revision = "9dfe24ddc756"
branch_labels = None
depends_on = None


def upgrade():
    from wallet.models.constants import TaxationState

    op.add_column(
        "reimbursement_wallet",
        sa.Column(
            "taxation_status",
            sa.Enum(
                TaxationState, values_callable=lambda _enum: [e.value for e in _enum]
            ),
        ),
    )


def downgrade():
    op.drop_column("reimbursement_wallet", "taxation_status")
