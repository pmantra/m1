"""Add MFA fields to User table

Revision ID: b33161d7bc55
Revises: b3845cc40284
Create Date: 2020-07-10 00:30:47.412099

"""
from alembic import op
import enum
import sqlalchemy as sa

from utils.data import PHONE_NUMBER_LENGTH


# revision identifiers, used by Alembic.
revision = "b33161d7bc55"
down_revision = "b3845cc40284"
branch_labels = None
depends_on = None

USER_TABLE_NAME = "user"


class MFAState(enum.Enum):
    DISABLED = "disabled"
    PENDING_VERIFICATION = "pending_verification"
    ENABLED = "enabled"


def upgrade():
    op.add_column(
        USER_TABLE_NAME,
        sa.Column(
            "mfa_state", sa.Enum(MFAState), default=MFAState.DISABLED, nullable=False
        ),
    )
    op.add_column(
        USER_TABLE_NAME, sa.Column("sms_phone_number", sa.String(PHONE_NUMBER_LENGTH))
    )
    op.add_column(USER_TABLE_NAME, sa.Column("authy_id", sa.Integer))


def downgrade():
    op.drop_column(USER_TABLE_NAME, "mfa_state")
    op.drop_column(USER_TABLE_NAME, "sms_phone_number")
    op.drop_column(USER_TABLE_NAME, "authy_id")
