"""Remove nullability of sender field on CareAdvocateMemberTransitionTemplate model

Revision ID: 29a2df1743fe
Revises: 931b280390ef
Create Date: 2023-01-12 21:34:50.405625+00:00

"""
from alembic import op
import sqlalchemy as sa
from enum import Enum

# revision identifiers, used by Alembic.
revision = "29a2df1743fe"
down_revision = "931b280390ef"
branch_labels = None
depends_on = None


class MessageSender(Enum):
    OLD_CX = "Messge from Old CX"
    NEW_CX = "Message from New CX"


def upgrade():
    op.alter_column(
        "ca_member_transition_template",
        "sender",
        existing_type=sa.Enum(MessageSender),
        nullable=False,
    )


def downgrade():
    op.alter_column(
        "ca_member_transition_template",
        "sender",
        existing_type=sa.Enum(MessageSender),
        nullable=True,
    )
