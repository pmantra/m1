"""remove question_set_vertical

Revision ID: afb0d2129d91
Revises: 5ca1f99e6b51
Create Date: 2020-05-07 15:15:55.763037

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "afb0d2129d91"
down_revision = "5ca1f99e6b51"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.engine.reflection.Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if "question_set_vertical" in tables:
        op.drop_table("question_set_vertical")


def downgrade():
    conn = op.get_bind()
    inspector = sa.engine.reflection.Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if "question_set_vertical" not in tables:
        op.create_table(
            "question_set_vertical",
            sa.Column(
                "vertical_id", sa.Integer, sa.ForeignKey("vertical.id"), nullable=False
            ),
            sa.Column(
                "question_set_id",
                sa.BigInteger,
                sa.ForeignKey("question_set.id"),
                nullable=False,
            ),
        )
