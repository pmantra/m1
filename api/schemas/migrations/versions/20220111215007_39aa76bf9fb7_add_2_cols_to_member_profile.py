"""Add 2 cols to member profile

Revision ID: 39aa76bf9fb7
Revises: bb6f709d789f
Create Date: 2022-01-11 21:50:07.626554+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "39aa76bf9fb7"
down_revision = "bb6f709d789f"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "member_profile",
        sa.Column(
            "has_care_plan",
            sa.Boolean,
            nullable=False,
            default=False,
            server_default=sa.sql.expression.false(),
        ),
    )

    op.add_column(
        "member_profile",
        sa.Column(
            "care_plan_id",
            sa.Integer,
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("member_profile", "has_care_plan")
    op.drop_column("member_profile", "care_plan_id")
