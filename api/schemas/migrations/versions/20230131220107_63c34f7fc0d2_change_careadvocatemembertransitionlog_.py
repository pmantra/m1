"""Change CareAdvocateMemberTransitionLog.uploaded_content to MEDIUMETXT

Revision ID: 63c34f7fc0d2
Revises: 77d9ef7f6f41
Create Date: 2023-01-31 22:01:07.396760+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
from sqlalchemy.dialects import mysql

revision = "63c34f7fc0d2"
down_revision = "31d84f438e05"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "ca_member_transition_log",
        "uploaded_content",
        type_=mysql.MEDIUMTEXT(),
        existing_type=sa.Text(),
    )


def downgrade():
    op.alter_column(
        "ca_member_transition_log",
        "uploaded_content",
        type_=sa.Text(),
        existing_type=mysql.MEDIUMTEXT(),
    )
