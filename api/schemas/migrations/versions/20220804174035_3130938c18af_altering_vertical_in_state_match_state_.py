"""Altering vertical_in_state_match_state table to have state/vertical both be PKs

Revision ID: 3130938c18af
Revises: a45207c53b16
Create Date: 2022-08-04 17:40:35.623906+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3130938c18af"
down_revision = "a45207c53b16"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("vertical_in_state_match_state")

    op.create_table(
        "vertical_in_state_match_state",
        sa.Column(
            "vertical_id", sa.Integer, sa.ForeignKey("vertical.id"), primary_key=True
        ),
        sa.Column("state_id", sa.Integer, sa.ForeignKey("state.id"), primary_key=True),
    )
    op.create_unique_constraint(
        "uq_vertical_state",
        "vertical_in_state_match_state",
        ["vertical_id", "state_id"],
    )


def downgrade():
    op.drop_table("vertical_in_state_match_state")

    op.create_table(
        "vertical_in_state_match_state",
        sa.Column("vertical_id", sa.Integer, sa.ForeignKey("vertical.id")),
        sa.Column("state_id", sa.Integer, sa.ForeignKey("state.id")),
    )
    op.create_unique_constraint(
        "uq_vertical_state",
        "vertical_in_state_match_state",
        ["vertical_id", "state_id"],
    )
