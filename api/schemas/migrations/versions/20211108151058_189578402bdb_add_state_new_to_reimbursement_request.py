"""SC-45672 add state NEW to reimbursement_request

Revision ID: 189578402bdb
Revises: 6b73786c6e68
Create Date: 2021-11-08 15:10:58.247527+00:00

"""
import enum

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "189578402bdb"
down_revision = "6b73786c6e68"
branch_labels = None
depends_on = None


class OldReimbursementRequestTypes(enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REIMBURSED = "REIMBURSED"
    DENIED = "DENIED"
    FAILED = "FAILED"


class ReimbursementRequestTypes(enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REIMBURSED = "REIMBURSED"
    DENIED = "DENIED"
    FAILED = "FAILED"
    NEW = "NEW"


def upgrade():
    op.alter_column(
        "reimbursement_request",
        "state",
        type_=sa.Enum(ReimbursementRequestTypes),
        existing_type=sa.Enum(OldReimbursementRequestTypes),
        nullable=False,
        existing_server_default="NEW",
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
