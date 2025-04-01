"""Adding new verticals_in_state_matches_states table

Revision ID: 3c2902191655
Revises: 302b1f090e11
Create Date: 2022-07-28 17:53:40.649481+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3c2902191655"
down_revision = "302b1f090e11"
branch_labels = None
depends_on = None


def upgrade():
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


def downgrade():
    op.drop_table("vertical_in_state_match_state")
