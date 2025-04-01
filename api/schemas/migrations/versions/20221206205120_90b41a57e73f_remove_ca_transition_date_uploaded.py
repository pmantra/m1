"""remove_ca_transition_date_uploaded

Revision ID: 90b41a57e73f
Revises: 559c96c35bd0
Create Date: 2022-12-06 20:51:20.021972+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "90b41a57e73f"
down_revision = "559c96c35bd0"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("ca_member_transition_log", "date_uploaded")


def downgrade():
    op.add_column(
        "ca_member_transition_log",
        sa.Column("date_uploaded", sa.DateTime),
    )
