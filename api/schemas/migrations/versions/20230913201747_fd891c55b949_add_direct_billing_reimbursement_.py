"""add_direct_billing_reimbursement_request_type

Revision ID: fd891c55b949
Revises: ba3bae761b2b
Create Date: 2023-09-13 20:17:47.338055+00:00

"""
from alembic import op
import sqlalchemy as sa

import enum


# revision identifiers, used by Alembic.
revision = "fd891c55b949"
down_revision = "cf925a6b0ada"
branch_labels = None
depends_on = None


class ReimbursementRequestType(enum.Enum):
    MANUAL = "MANUAL"
    DEBIT_CARD = "DEBIT_CARD"
    DIRECT_BILLING = "DIRECT_BILLING"


def upgrade():
    types = [
        reimbursement_type.value for reimbursement_type in ReimbursementRequestType
    ]
    sql = sa.text(
        "ALTER TABLE reimbursement_request MODIFY COLUMN reimbursement_type ENUM :types NOT NULL"
    ).bindparams(types=types)
    op.execute(sql)


def downgrade():
    types = [
        reimbursement_type.value for reimbursement_type in ReimbursementRequestType
    ]
    types.remove(ReimbursementRequestType.DIRECT_BILLING.value)
    sql = sa.text(
        "ALTER TABLE reimbursement_request MODIFY COLUMN reimbursement_type ENUM :types NOT NULL"
    ).bindparams(types=types)
    op.execute(sql)
