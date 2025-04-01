"""Add tax status col to reimbursement org setting

Revision ID: 617f132a201a
Revises: 2e1e9bd4ac05
Create Date: 2022-05-11 20:12:54.716051+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "617f132a201a"
down_revision = "2e1e9bd4ac05"
branch_labels = None
depends_on = None


def upgrade():
    from wallet.models.constants import TaxationState

    op.add_column(
        "reimbursement_organization_settings",
        sa.Column(
            "taxation_status",
            sa.Enum(
                TaxationState, values_callable=lambda _enum: [e.value for e in _enum]
            ),
        ),
    )


def downgrade():
    op.drop_column("reimbursement_organization_settings", "taxation_status")
