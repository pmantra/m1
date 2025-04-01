"""Update ReimbursementAccountStatuses

Revision ID: 779a38b5f3f5
Revises: 9296f5a5630a
Create Date: 2022-01-07 15:09:32.466727+00:00

"""
import enum

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "779a38b5f3f5"
down_revision = "9296f5a5630a"
branch_labels = None
depends_on = None


class OldReimbursementAccountStatus(enum.Enum):
    ACTIVE = 1
    PERMANENTLY_INACTIVE = 4


class ReimbursementAccountStatus(enum.Enum):
    NEW = 1
    ACTIVE = 2
    TEMPORARILY_INACTIVE = 3
    PERMANENTLY_INACTIVE = 4
    TERMINATED = 5


def upgrade():
    op.alter_column(
        "reimbursement_account",
        "status",
        type_=sa.Enum(ReimbursementAccountStatus),
        existing_type=sa.Enum(OldReimbursementAccountStatus),
        nullable=True,
    )


def downgrade():
    op.alter_column(
        "reimbursement_account",
        "status",
        type_=sa.Enum(OldReimbursementAccountStatus),
        existing_type=sa.Enum(ReimbursementAccountStatus),
        nullable=True,
    )
