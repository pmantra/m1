"""Add draft attribute to recorded answer set

Revision ID: 7103d915ca26
Revises: 84da774bcd24
Create Date: 2020-10-20 20:46:24.542814

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "7103d915ca26"
down_revision = "84da774bcd24"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "recorded_answer_set",
        sa.Column("draft", sa.Boolean, server_default=sa.sql.expression.true()),
    )


def downgrade():
    op.drop_column("recorded_answer_set", "draft")
