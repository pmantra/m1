"""Add sender field to CareAdvocateMemberTransitionTemplate

Revision ID: 095c8a6dfa32
Revises: d71ded921b03
Create Date: 2023-01-03 22:53:26.402184+00:00

"""
from alembic import op
import sqlalchemy as sa
from enum import Enum

# revision identifiers, used by Alembic.
revision = "095c8a6dfa32"
down_revision = "d71ded921b03"
branch_labels = None
depends_on = None


class MessageSender(Enum):
    OLD_CX = "Messge from Old CX"
    NEW_CX = "Message from New CX"


def upgrade():
    op.add_column(
        "ca_member_transition_template",
        sa.Column("sender", sa.Enum(MessageSender), nullable=True),
    )


def downgrade():
    op.drop_column("ca_member_transition_template", "sender")
