"""Change server_default of draft column on recorded_answer_set to false

Revision ID: 9d626cd02214
Revises: 0462fb526d25
Create Date: 2020-11-13 18:56:51.567162

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9d626cd02214"
down_revision = "0462fb526d25"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "recorded_answer_set",
        sa.Column("draft", server_default=sa.sql.expression.false()),
    )


def downgrade():
    op.alter_column(
        "recorded_answer_set",
        sa.Column("draft", server_default=sa.sql.expression.true()),
    )
