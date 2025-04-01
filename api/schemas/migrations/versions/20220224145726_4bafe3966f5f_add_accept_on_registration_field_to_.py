"""Add accept_on_registration field to Agreements

Revision ID: 4bafe3966f5f
Revises: 997b191e8fca
Create Date: 2022-02-24 14:57:26.590261+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4bafe3966f5f"
down_revision = "997b191e8fca"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "agreement",
        sa.Column(
            "accept_on_registration",
            sa.Boolean,
            nullable=False,
            default=True,
            server_default=sa.sql.expression.true(),
        ),
    )


def downgrade():
    op.drop_column("agreement", "accept_on_registration")
