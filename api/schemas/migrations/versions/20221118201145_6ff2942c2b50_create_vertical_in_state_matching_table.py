"""create_vertical_in_state_matching_table

Revision ID: 6ff2942c2b50
Revises: f79303b41d45
Create Date: 2022-11-18 20:11:45.710982+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6ff2942c2b50"
down_revision = "f79303b41d45"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "vertical_in_state_matching",
        sa.Column(
            "vertical_id",
            sa.Integer,
            sa.ForeignKey("vertical.id"),
            nullable=False,
        ),
        sa.Column("subdivision_code", sa.String(6), nullable=False),
    )
    op.create_primary_key(
        constraint_name="pk_vertical_in_state_matching",
        table_name="vertical_in_state_matching",
        columns=["vertical_id", "subdivision_code"],
    )


def downgrade():
    op.drop_table("vertical_in_state_matching")
