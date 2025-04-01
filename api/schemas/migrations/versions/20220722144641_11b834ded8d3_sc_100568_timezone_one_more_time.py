"""sc-100568 timezone, one more time

Revision ID: 11b834ded8d3
Revises: 5cce3671245b
Create Date: 2022-07-22 14:46:41.215649+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "11b834ded8d3"
down_revision = "5cce3671245b"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "availability_notification_request",
        "member_timezone_offset",
        type_=sa.Integer,
    )


def downgrade():
    op.alter_column(
        "availability_notification_request",
        "member_timezone_offset",
        type_=sa.String(3),
    )
