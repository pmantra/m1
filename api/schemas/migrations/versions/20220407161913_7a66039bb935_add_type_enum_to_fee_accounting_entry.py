"""Add Type Enum to Fee Accounting Entry

Revision ID: 7a66039bb935
Revises: 18cb044b6305
Create Date: 2022-04-07 16:19:13.597359+00:00

"""
from alembic import op
import sqlalchemy as sa
from appointments.models.payments import FeeAccountingEntryTypes


# revision identifiers, used by Alembic.
revision = "7a66039bb935"
down_revision = "18cb044b6305"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "fee_accounting_entry",
        sa.Column(
            "type",
            sa.Enum(FeeAccountingEntryTypes),
            nullable=False,
            server_default=FeeAccountingEntryTypes.UNKNOWN,
        ),
    )


def downgrade():
    op.drop_column("fee_accounting_entry", "type")
