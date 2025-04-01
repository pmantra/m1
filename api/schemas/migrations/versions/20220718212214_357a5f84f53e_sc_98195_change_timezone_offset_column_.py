"""sc-98195 change timezone offset column type

Revision ID: 357a5f84f53e
Revises: ac005a927c1a
Create Date: 2022-07-18 21:22:14.043925+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "357a5f84f53e"
down_revision = "ac005a927c1a"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "availability_notification_request",
        "member_timezone_offset",
        type_=sa.String(3),
    )


def downgrade():
    op.alter_column(
        "availability_notification_request", "member_timezone_offset", type_=sa.Integer
    )
