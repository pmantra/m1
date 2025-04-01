"""Add matching_rule_set table

Revision ID: 0f616fa67a58
Revises: ecd94bf69b39
Create Date: 2021-07-29 14:29:48.305006+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0f616fa67a58"
down_revision = "ecd94bf69b39"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("matching_rule_ibfk_1", "matching_rule", type_="foreignkey")
    op.drop_column("matching_rule", "assignable_advocate_id")

    op.create_table(
        "matching_rule_set",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "assignable_advocate_id",
            sa.Integer,
            sa.ForeignKey("assignable_advocate.practitioner_id", ondelete="cascade"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime),
        sa.Column("modified_at", sa.DateTime),
    )

    op.add_column(
        "matching_rule",
        sa.Column(
            "matching_rule_set_id", sa.Integer, sa.ForeignKey("matching_rule_set.id")
        ),
    )


def downgrade():
    op.drop_table("matching_rule_set")
    op.drop_column("matching_rule", "matching_rule_set_id")

    op.add_column(
        "matching_rule",
        sa.Column(
            "assignable_advocate_id",
            sa.Integer,
            sa.ForeignKey("assignable_advocate.practitioner_id", ondelete="cascade"),
            nullable=False,
        ),
    )
