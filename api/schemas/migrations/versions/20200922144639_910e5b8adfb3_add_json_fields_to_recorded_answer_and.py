"""Add json fields to recorded answer and question...Also add oid field to question set, apparently

Revision ID: 910e5b8adfb3
Revises: 2eb39ac20baa
Create Date: 2020-09-22 14:46:39.527380

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "910e5b8adfb3"
down_revision = ("2eb39ac20baa", "7dc1f518a2df")
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "question", sa.Column("non_db_answer_options_json", sa.Text, nullable=True)
    )
    op.add_column("recorded_answer", sa.Column("payload", sa.Text, nullable=True))

    op.add_column("question_set", sa.Column("oid", sa.String(191), nullable=True))


def downgrade():
    op.drop_column("recorded_answer", "payload")
    op.drop_column("question", "non_db_answer_options_json")

    op.drop_column("question_set", "oid")
