"""Add tax status to reimbursement request table

Revision ID: e070e7a507e1
Revises: 617f132a201a
Create Date: 2022-05-13 19:46:26.350775+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e070e7a507e1"
down_revision = "617f132a201a"
branch_labels = None
depends_on = None


def upgrade():
    from wallet.models.constants import TaxationState

    op.add_column(
        "reimbursement_request",
        sa.Column(
            "taxation_status",
            sa.Enum(
                TaxationState, values_callable=lambda _enum: [e.value for e in _enum]
            ),
        ),
    )


def downgrade():
    op.drop_column("reimbursement_request", "taxation_status")
