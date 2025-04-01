"""Add fertility_clinic_allowed_domain table

Revision ID: 00de519b7293
Revises: f43840ae5c78
Create Date: 2023-05-03 15:01:51.271195+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "00de519b7293"
down_revision = "f43840ae5c78"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "fertility_clinic_allowed_domain",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("uuid", sa.String(36), nullable=False),
        sa.Column("domain", sa.String(120), nullable=False),
        # fertility_clinic_id is a logical foreign key to fertility_clinic
        sa.Column(
            "fertility_clinic_id",
            sa.BigInteger,
            nullable=False,
        ),
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
    op.drop_table("fertility_clinic_allowed_domain")
