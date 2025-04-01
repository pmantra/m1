"""Add matching rules

Revision ID: 3b0e4bfca5ae
Revises: bf345a0650e9
Create Date: 2021-07-07 14:45:44.911929+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3b0e4bfca5ae"
down_revision = "bf345a0650e9"
branch_labels = None
depends_on = None


def upgrade():
    from care_advocates.models.matching_rules import MatchingRuleType

    op.create_table(
        "matching_rule",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "assignable_advocate_id",
            sa.Integer,
            sa.ForeignKey("assignable_advocate.practitioner_id", ondelete="cascade"),
            nullable=False,
        ),
        sa.Column(
            "type",
            sa.Enum(
                MatchingRuleType, values_callable=lambda _enum: [e.value for e in _enum]
            ),
        ),
        sa.Column("entity", sa.String(128)),
        sa.Column("all", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime),
        sa.Column("modified_at", sa.DateTime),
    )

    op.create_table(
        "matching_rule_entity",
        sa.Column(
            "matching_rule_id",
            sa.Integer,
            sa.ForeignKey("matching_rule.id", ondelete="cascade"),
        ),
        sa.Column("entity_id", sa.Integer),
    )

    op.create_index(None, "matching_rule_entity", ["matching_rule_id", "entity_id"])

    op.create_index(None, "matching_rule", ["type", "entity"])
    op.create_index(None, "matching_rule", ["all"])


def downgrade():
    op.drop_constraint(
        "matching_rule_entity_ibfk_1", "matching_rule_entity", type_="foreignkey"
    )
    op.drop_constraint("matching_rule_ibfk_1", "matching_rule", type_="foreignkey")
    op.drop_index("ix_matching_rule_entity_matching_rule_id", "matching_rule_entity")
    op.drop_index("ix_matching_rule_type", "matching_rule")
    op.drop_index("ix_matching_rule_all", "matching_rule")
    op.drop_table("matching_rule_entity")
    op.drop_table("matching_rule")
