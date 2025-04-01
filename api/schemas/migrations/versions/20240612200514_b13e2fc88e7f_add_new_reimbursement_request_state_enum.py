"""add_new_reimbursement_request_state_enum

Revision ID: b13e2fc88e7f
Revises: a1ed887bfc58
Create Date: 2024-06-12 20:05:14.334470+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b13e2fc88e7f"
down_revision = "a1ed887bfc58"
branch_labels = None
depends_on = None


def upgrade():
    q = """
    ALTER TABLE reimbursement_request MODIFY COLUMN state
    ENUM('NEW','PENDING','APPROVED','REIMBURSED','DENIED','FAILED','NEEDS_RECEIPT','RECEIPT_SUBMITTED','INSUFFICIENT_RECEIPT','INELIGIBLE_EXPENSE','PENDING_MEMBER_INPUT','RESOLVED','REFUNDED') COLLATE utf8mb4_unicode_ci NOT NULL,
    ALGORITHM=COPY,
    LOCK=SHARED;
    """
    op.execute(q)


def downgrade():
    q = """
    ALTER TABLE reimbursement_request MODIFY COLUMN state
    ENUM('NEW','PENDING','APPROVED','REIMBURSED','DENIED','FAILED','NEEDS_RECEIPT','RECEIPT_SUBMITTED','INSUFFICIENT_RECEIPT','INELIGIBLE_EXPENSE','RESOLVED','REFUNDED') COLLATE utf8mb4_unicode_ci NOT NULL,
    ALGORITHM=COPY,
    LOCK=SHARED;
    """
    op.execute(q)
