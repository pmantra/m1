"""Add availability request id to message

Revision ID: bcd4ff8b7371
Revises: a7a55645f231
Create Date: 2022-07-27 15:08:53.826184+00:00

"""
from alembic import op
import sqlalchemy as sa

from messaging.models.messaging import Message

# revision identifiers, used by Alembic.
revision = "bcd4ff8b7371"
down_revision = "a7a55645f231"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        Message.__tablename__,
        sa.Column(
            "availability_notification_request_id",
            sa.Integer,
            sa.ForeignKey("availability_notification_request.id"),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_constraint("message_ibfk_3", Message.__tablename__, type_="foreignkey")
    op.drop_column(Message.__tablename__, "availability_notification_request_id")
