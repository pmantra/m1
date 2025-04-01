"""Update reimbursement_request model to include new states for debit card

Revision ID: d0a66cb30d3e
Revises: 6108180f93f9
Create Date: 2022-08-03 00:20:01.273912+00:00

"""
from alembic import op
import sqlalchemy as sa

from wallet.models.reimbursement import ReimbursementRequest

# revision identifiers, used by Alembic.
revision = "d0a66cb30d3e"
down_revision = "6108180f93f9"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        ReimbursementRequest.__tablename__,
        "state",
        existing_type=sa.Enum(
            "PENDING",
            "APPROVED",
            "REIMBURSED",
            "DENIED",
            "FAILED",
            "NEW",
            "NEEDS_RECEIPT",
            "RECEIPT_SUBMITTED",
        ),
        nullable=False,
        default="NEW",
    )


def downgrade():
    op.alter_column(
        ReimbursementRequest.__tablename__,
        "state",
        existing_type=sa.Enum(
            "PENDING", "APPROVED", "REIMBURSED", "DENIED", "FAILED", "NEW"
        ),
        nullable=False,
        default="NEW",
    )
