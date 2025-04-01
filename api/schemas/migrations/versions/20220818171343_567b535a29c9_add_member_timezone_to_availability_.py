"""Add member_timezone to availability_notification_request

Revision ID: 567b535a29c9
Revises: 89c048ca2842
Create Date: 2022-08-18 17:13:43.837725+00:00

"""
from alembic import op
import sqlalchemy as sa


from appointments.models.availability_notification_request import (
    AvailabilityNotificationRequest,
)


# revision identifiers, used by Alembic.
revision = "567b535a29c9"
down_revision = "89c048ca2842"
branch_labels = None
depends_on = None


# op.add_column('mytable', sa.Column('mycolumn', sa.String(), nullable=False, server_default='lorem ipsum'))
#     op.alter_column('mytable', 'mycolumn', server_default=None)
def upgrade():
    op.add_column(
        AvailabilityNotificationRequest.__tablename__,
        sa.Column(
            "member_timezone",
            sa.String(50),
            server_default="America/New_York",
            nullable=False,
        ),
    )


def downgrade():
    op.drop_column(AvailabilityNotificationRequest.__tablename__, "member_timezone")
