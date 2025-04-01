"""add_entity_identifier_column

Revision ID: 30179a5d81cf
Revises: feb85e69b8b3
Create Date: 2022-10-31 15:55:18.656269+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "30179a5d81cf"
down_revision = "afcf01696a4d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "matching_rule_entity",
        sa.Column("entity_identifier", sa.String(120), nullable=True),
    )

    op.drop_constraint(
        "matching_rule_entity_ibfk_1", "matching_rule_entity", type_="foreignkey"
    )
    op.drop_index("ix_matching_rule_entity_matching_rule_id", "matching_rule_entity")
    op.create_index(
        "ix_matching_rule_entity_matching_rule_id",
        "matching_rule_entity",
        ["matching_rule_id", "entity_id", "entity_identifier"],
    )
    op.create_foreign_key(
        "matching_rule_entity_ibfk_1",
        "matching_rule_entity",
        "matching_rule",
        ["matching_rule_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade():
    op.drop_constraint(
        "matching_rule_entity_ibfk_1", "matching_rule_entity", type_="foreignkey"
    )
    op.drop_index("ix_matching_rule_entity_matching_rule_id", "matching_rule_entity")
    op.create_foreign_key(
        "matching_rule_entity_ibfk_1",
        "matching_rule_entity",
        "matching_rule",
        ["matching_rule_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_matching_rule_entity_matching_rule_id",
        "matching_rule_entity",
        ["matching_rule_id", "entity_id"],
    )
    op.drop_column("matching_rule_entity", "entity_identifier")
