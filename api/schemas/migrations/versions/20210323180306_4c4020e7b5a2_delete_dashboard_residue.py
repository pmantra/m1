"""Delete dashboard residue

Revision ID: 4c4020e7b5a2
Revises: 3325ec87380e
Create Date: 2021-03-23 18:03:06.890031

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4c4020e7b5a2"
down_revision = "3325ec87380e"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("module_transition")
    op.drop_table("curriculum_step_user")
    op.drop_table("curriculum_step")
    op.drop_table("curriculum")
    op.drop_table("curriculum_lifecycle")
    op.drop_table("dismissal")
    op.drop_table("card_action")
    op.drop_table("card")
    op.drop_table("block")
    op.drop_table("dashboard_version")
    op.drop_table("dashboard")

    op.drop_column("user", "curriculum_active")


def downgrade():
    op.add_column("user", sa.Column("curriculum_active", sa.Boolean))

    op.create_table(
        "curriculum",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
    )
    op.create_table(
        "module_transition",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
    )
    op.create_table(
        "curriculum_step_user",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
    )
    op.create_table(
        "curriculum_step",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
    )
    op.create_table(
        "curriculum_lifecycle",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
    )
    op.create_table(
        "dismissal",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
    )
    op.create_table(
        "card_action",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
    )
    op.create_table(
        "card", sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True)
    )
    op.create_table(
        "block", sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True)
    )
    op.create_table(
        "dashboard_version",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
    )
    op.create_table(
        "dashboard",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
    )
