"""Add fertility_clinic_location table

Revision ID: 331494abfe04
Revises: 3ac121518956
Create Date: 2023-05-01 17:00:26.595422+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "331494abfe04"
down_revision = "3ac121518956"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "fertility_clinic_location",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("uuid", sa.String(36), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("address_1", sa.String(200), nullable=False),
        sa.Column("address_2", sa.String(200), nullable=True),
        sa.Column("city", sa.String(40), nullable=False),
        sa.Column("subdivision_code", sa.String(6), nullable=False),
        sa.Column("postal_code", sa.String(20), nullable=False),
        sa.Column("country_code", sa.String(3), nullable=True),
        sa.Column("phone_number", sa.String(50), nullable=True),
        sa.Column("email", sa.String(120), nullable=True),
        # fertility_clinic_id is a logical foreign key to fertility_clinic
        sa.Column(
            "fertility_clinic_id",
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
    op.drop_table("fertility_clinic_location")
