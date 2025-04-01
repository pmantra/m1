"""add contract_types fields indices to practitioner_contract

Revision ID: 157fe7553804
Revises: 47e7bdea398d
Create Date: 2023-05-16 21:20:49.060367+00:00

"""
from alembic import op
import sqlalchemy as sa
import enum


# revision identifiers, used by Alembic.
revision = "157fe7553804"
down_revision = "47e7bdea398d"
branch_labels = None
depends_on = None


class OldContractType(str, enum.Enum):
    BY_APPOINTMENT = "By appointment"
    FIXED_HOURLY = "Fixed hourly"
    FIXED_HOURLY_OVERNIGHT = "Fixed hourly overnight"
    HYBRID_2_0 = "Hybrid 2.0"
    W2 = "W2"


class ContractType(str, enum.Enum):
    BY_APPOINTMENT = "By appointment"
    FIXED_HOURLY = "Fixed hourly"
    FIXED_HOURLY_OVERNIGHT = "Fixed hourly overnight"
    HYBRID_1_0 = "Hybrid 1.0"
    HYBRID_2_0 = "Hybrid 2.0"
    NON_STANDARD_BY_APPOINTMENT = "Non standard by appointment"
    W2 = "W2"


def upgrade():
    op.alter_column(
        "practitioner_contract",
        "contract_type",
        type_=sa.Enum(ContractType),
        existing_type=sa.Enum(OldContractType),
        nullable=False,
    )
    op.add_column(
        "practitioner_contract",
        sa.Column("rate_per_overnight_appt", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        "practitioner_contract",
        sa.Column("hourly_appointment_rate", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        "practitioner_contract",
        sa.Column(
            "non_standard_by_appointment_message_rate", sa.Numeric(5, 2), nullable=True
        ),
    )
    op.create_index(
        "prac_id_end_date_idx", "practitioner_contract", ["practitioner_id", "end_date"]
    )


def downgrade():
    op.drop_constraint(
        "fk_practitioner_id", "practitioner_contract", type_="foreignkey"
    )
    op.drop_index("prac_id_end_date_idx", "practitioner_contract")
    op.create_foreign_key(
        "fk_practitioner_id",
        "practitioner_contract",
        "practitioner_profile",
        ["practitioner_id"],
        ["user_id"],
    )
    op.drop_column("practitioner_contract", "non_standard_by_appointment_message_rate")
    op.drop_column("practitioner_contract", "hourly_appointment_rate")
    op.drop_column("practitioner_contract", "rate_per_overnight_appt")
    op.alter_column(
        "practitioner_contract",
        "contract_type",
        type_=sa.Enum(OldContractType),
        existing_type=sa.Enum(ContractType),
        nullable=False,
    )
