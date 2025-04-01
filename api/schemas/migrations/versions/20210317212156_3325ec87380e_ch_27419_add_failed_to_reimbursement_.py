"""CH-27419 add FAILED to reimbursement_wallet state enum

Revision ID: 3325ec87380e
Revises: d246acab3491
Create Date: 2021-03-17 21:21:56.452191

"""
from alembic import op
import sqlalchemy as sa
import enum


# revision identifiers, used by Alembic.
revision = "3325ec87380e"
down_revision = "d246acab3491"
branch_labels = None
depends_on = None


class OldReimbursementRequestTypes(enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REIMBURSED = "REIMBURSED"
    DENIED = "DENIED"


class ReimbursementRequestTypes(enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REIMBURSED = "REIMBURSED"
    DENIED = "DENIED"
    FAILED = "FAILED"


def upgrade():
    op.alter_column(
        "reimbursement_request",
        "state",
        type_=sa.Enum(ReimbursementRequestTypes),
        existing_type=sa.Enum(OldReimbursementRequestTypes),
        nullable=False,
        existing_server_default="PENDING",
    )


def downgrade():
    op.alter_column(
        "reimbursement_request",
        "state",
        type_=sa.Enum(OldReimbursementRequestTypes),
        existing_type=sa.Enum(ReimbursementRequestTypes),
        nullable=False,
        existing_server_default="PENDING",
    )
