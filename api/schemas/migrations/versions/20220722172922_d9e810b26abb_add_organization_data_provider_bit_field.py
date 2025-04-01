"""add organization.data_provider bit field

Revision ID: d9e810b26abb
Revises: 11b834ded8d3
Create Date: 2022-07-22 17:29:22.579949+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d9e810b26abb"
down_revision = "11b834ded8d3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "organization",
        sa.Column(
            "data_provider",
            sa.Boolean,
            nullable=False,
            default=False,
            server_default=sa.sql.expression.false(),
        ),
    )


def downgrade():
    op.drop_column("organization", "data_provider")
