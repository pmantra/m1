"""Add country_code and subdivision_code to User table

Revision ID: 8923e4783291
Revises: baf07832e4c9
Create Date: 2022-07-06 16:44:47.716664+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "8923e4783291"
down_revision = "baf07832e4c9"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(
            sa.Column(
                "country_code",
                sa.String(2),
                nullable=True,
            ),
        )
        batch_op.add_column(
            sa.Column(
                "subdivision_code",
                sa.String(6),
                nullable=True,
            ),
        )


def downgrade():
    with op.batch_alter_table("user") as batch_op:
        batch_op.drop_column("country_code")
        batch_op.drop_column("subdivision_code")
