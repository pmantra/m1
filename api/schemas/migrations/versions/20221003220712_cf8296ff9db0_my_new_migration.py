"""Migration to add `ca_member_transition_log` and `ca_member_transition_template` tables.

Revision ID: cf8296ff9db0
Revises: 8b190e8533df
Create Date: 2022-10-03 22:07:12.286576+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "cf8296ff9db0"
down_revision = "8b190e8533df"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ca_member_transition_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime),
        sa.Column("modified_at", sa.DateTime),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id")),
        sa.Column("date_uploaded", sa.DateTime),
        sa.Column("date_completed", sa.DateTime),
        sa.Column("date_scheduled", sa.DateTime),
        sa.Column("csv_filename", sa.String(100)),
        sa.Column("csv_content", sa.Text),
    )

    op.create_table(
        "ca_member_transition_template",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime),
        sa.Column("modified_at", sa.DateTime),
        sa.Column("message_type", sa.String(100), unique=True),
        sa.Column("message_description", sa.String(100)),
        sa.Column("message_body", sa.String(1000)),
    )


def downgrade():
    op.drop_table("ca_member_transition_log")
    op.drop_table("ca_member_transition_template")
