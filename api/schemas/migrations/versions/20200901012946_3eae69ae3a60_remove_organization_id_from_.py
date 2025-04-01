"""Remove organization_id from ModuleTransition

Revision ID: 3eae69ae3a60
Revises: 72f3bf083ab4
Create Date: 2020-09-01 01:29:46.714125

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3eae69ae3a60"
down_revision = "72f3bf083ab4"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        "module_transition_ibfk_3", "module_transition", type_="foreignkey"
    )
    op.drop_column("module_transition", "organization_id")


def downgrade():
    op.add_column(
        "module_transition",
        sa.Column("organization_id", sa.Integer, sa.ForeignKey("organization.id")),
    )
    op.create_foreign_key(
        "module_transition_ibfk_3",
        "module_transition",
        "organization",
        ["organization_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "module_transition_unique_2",
        "module_transition",
        ["from_module_id", "to_module_id", "organization_id"],
    )
    op.drop_constraint(
        "module_transition_unique_1", "module_transition", type_="unique"
    )
    op.drop_constraint(
        "module_transition_ibfk_5", "module_transition", type_="foreignkey"
    )
