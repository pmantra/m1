"""Create Care Plan Activity Publish table

Revision ID: 1f83bf5d74d9
Revises: fcbbca8d4f70
Create Date: 2022-08-22 15:03:45.036711+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1f83bf5d74d9"
down_revision = "fcbbca8d4f70"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "care_plan_activity_publish",
        sa.Column("message_id", sa.String(50), primary_key=True),
        sa.Column("message_json", sa.String(250), nullable=False),
        sa.Column("success", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("modified_at", sa.DateTime, nullable=False),
    )


def downgrade():
    op.drop_table("care_plan_activity_publish")
