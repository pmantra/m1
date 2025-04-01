"""Add fertility_clinic table

Revision ID: 3ac121518956
Revises: c73766ebfe2c
Create Date: 2023-04-28 14:32:04.929126+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3ac121518956"
down_revision = "c73766ebfe2c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "fertility_clinic",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("uuid", sa.String(36), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("affiliated_network", sa.String(50), nullable=True),
        sa.Column(
            "fee_schedule_id",
            sa.BigInteger,
            nullable=False,
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP, nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "modified_at",
            sa.TIMESTAMP,
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )


def downgrade():
    op.drop_table("fertility_clinic")
