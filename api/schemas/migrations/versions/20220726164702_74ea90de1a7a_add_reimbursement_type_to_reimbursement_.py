"""Add reimbursement_type to reimbursement_request

Revision ID: 74ea90de1a7a
Revises: 7d9a3635b858
Create Date: 2022-07-26 12:53:14.418437+00:00

"""
from alembic import op
import sqlalchemy as sa

from wallet.models.constants import ReimbursementRequestType


# revision identifiers, used by Alembic.
revision = "74ea90de1a7a"
down_revision = "7d9a3635b858"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "reimbursement_request",
        sa.Column(
            "reimbursement_type",
            sa.Enum(ReimbursementRequestType),
            nullable=False,
            default=ReimbursementRequestType.MANUAL,
        ),
    )


def downgrade():
    op.drop_column("reimbursement_request", "reimbursement_type")
