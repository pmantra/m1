"""Add discount rate to fertility clinic

Revision ID: 24806fa6615d
Revises: a41858119368
Create Date: 2024-01-18 04:20:05.763210+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "24806fa6615d"
down_revision = "a41858119368"
branch_labels = None
depends_on = None


def upgrade():
    query = """
        ALTER TABLE fertility_clinic
        ADD COLUMN self_pay_discount_rate decimal(5, 2) DEFAULT NULL,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    op.execute(query)


def downgrade():
    query = """
        ALTER TABLE fertility_clinic
        DROP COLUMN self_pay_discount_rate,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    op.execute(query)
