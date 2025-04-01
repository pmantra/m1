"""create_practitioner_contract_table

Revision ID: 4a46e53667cb
Revises: db63438f0ee5
Create Date: 2023-04-12 18:43:19.391944+00:00

"""
from alembic import op
import sqlalchemy as sa
from payments.models.practitioner_contract import ContractType


# revision identifiers, used by Alembic.
revision = "4a46e53667cb"
down_revision = "db63438f0ee5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "practitioner_contract",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("modified_at", sa.DateTime, nullable=False),
        sa.Column("practitioner_id", sa.Integer, nullable=False),
        sa.Column("created_by_user_id", sa.Integer, nullable=False),
        sa.Column("contract_type", sa.Enum(ContractType), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("weekly_contracted_hours", sa.Numeric(5, 2), nullable=True),
        sa.Column("fixed_hourly_rate", sa.Numeric(5, 2), nullable=True),
    )
    op.create_foreign_key(
        "fk_practitioner_id",
        "practitioner_contract",
        "practitioner_profile",
        ["practitioner_id"],
        ["user_id"],
    )


def downgrade():
    op.execute("SET foreign_key_checks = 0")
    op.execute("DROP TABLE practitioner_contract")
    op.execute("SET foreign_key_checks = 1")
