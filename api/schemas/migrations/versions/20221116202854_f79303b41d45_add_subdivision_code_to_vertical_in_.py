"""add_subdivision_code_to_vertical_in_state_match_state

Revision ID: f79303b41d45
Revises: 01a2a17115fc
Create Date: 2022-11-16 20:28:54.633691+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f79303b41d45"
down_revision = "01a2a17115fc"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "vertical_in_state_match_state",
        sa.Column("subdivision_code", sa.String(6), nullable=True),
    )
    op.drop_constraint(
        "uq_vertical_state", "vertical_in_state_match_state", type_="unique"
    )
    op.create_unique_constraint(
        "uq_vertical_state",
        "vertical_in_state_match_state",
        ["vertical_id", "state_id", "subdivision_code"],
    )


def downgrade():
    op.drop_constraint(
        "uq_vertical_state", "vertical_in_state_match_state", type_="unique"
    )
    op.create_unique_constraint(
        "uq_vertical_state",
        "vertical_in_state_match_state",
        ["vertical_id", "state_id"],
    )
    op.drop_column("vertical_in_state_match_state", "subdivision_code")
