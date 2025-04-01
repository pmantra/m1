"""update_reimbursement_request_state_enum

Revision ID: 3ab765a5fa8f
Revises: cf8296ff9db0
Create Date: 2022-10-04 21:30:34.319117+00:00

"""
import enum
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from wallet.models.reimbursement import ReimbursementRequest

revision = "3ab765a5fa8f"
down_revision = "cf8296ff9db0"
branch_labels = None
depends_on = None


class ExistingReimbursementRequestStates(enum.Enum):
    NEW = "NEW"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REIMBURSED = "REIMBURSED"
    DENIED = "DENIED"
    FAILED = "FAILED"
    NEEDS_RECEIPT = "NEEDS_RECEIPT"
    RECEIPT_SUBMITTED = "RECEIPT_SUBMITTED"


class NewReimbursementRequestStates(enum.Enum):
    NEW = "NEW"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REIMBURSED = "REIMBURSED"
    DENIED = "DENIED"
    FAILED = "FAILED"
    NEEDS_RECEIPT = "NEEDS_RECEIPT"
    RECEIPT_SUBMITTED = "RECEIPT_SUBMITTED"
    INSUFFICIENT_RECEIPT = "INSUFFICIENT_RECEIPT"
    INELIGIBLE_EXPENSE = "INELIGIBLE_EXPENSE"
    RESOLVED = "RESOLVED"
    REFUNDED = "REFUNDED"


def upgrade():
    op.alter_column(
        ReimbursementRequest.__tablename__,
        "state",
        existing_type=sa.Enum(ExistingReimbursementRequestStates),
        type_=sa.Enum(NewReimbursementRequestStates),
        nullable=False,
        default="NEW",
    )


def downgrade():
    op.alter_column(
        ReimbursementRequest.__tablename__,
        "state",
        existing_type=sa.Enum(NewReimbursementRequestStates),
        type_=sa.Enum(ExistingReimbursementRequestStates),
        nullable=False,
        default="NEW",
    )
