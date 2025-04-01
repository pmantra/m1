"""Updating CSV field names on 'ca_member_transition_log' table

Revision ID: 4d99c216f8b6
Revises: cf8296ff9db0
Create Date: 2022-10-04 21:27:59.061885+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4d99c216f8b6"
down_revision = "3ab765a5fa8f"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "ca_member_transition_log",
        "csv_filename",
        existing_type=sa.String(100),
        new_column_name="uploaded_filename",
    )
    op.alter_column(
        "ca_member_transition_log",
        "csv_content",
        existing_type=sa.Text,
        new_column_name="uploaded_content",
    )


def downgrade():
    op.alter_column(
        "ca_member_transition_log",
        "uploaded_filename",
        existing_type=sa.String(100),
        new_column_name="csv_filename",
    )
    op.alter_column(
        "ca_member_transition_log",
        "uploaded_content",
        existing_type=sa.Text,
        new_column_name="csv_content",
    )
