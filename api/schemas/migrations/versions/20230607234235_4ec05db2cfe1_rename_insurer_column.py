"""rename insurer column

Revision ID: 4ec05db2cfe1
Revises: ac96cce30679
Create Date: 2023-06-28 23:42:30.450782+00:00

"""
import enum

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4ec05db2cfe1"
down_revision = "ac96cce30679"
branch_labels = None
depends_on = None


class PatientAndSubscriberRelationship(enum.Enum):
    SELF = "SELF"
    SPOUSE = "SPOUSE"
    PARTNER = "PARTNER"
    DEPENDENT = "DEPENDENT"


def upgrade():
    op.drop_constraint(
        "employee_health_plan_ibfk_3", "employee_health_plan", type_="foreignkey"
    )
    op.alter_column(
        "employee_health_plan",
        "insurer",
        new_column_name="payer_id",
        existing_type=sa.BigInteger,
        nullable=False,
    )
    op.alter_column(
        "employee_health_plan",
        "relationship",
        new_column_name="relation",
        existing_type=sa.Enum(PatientAndSubscriberRelationship),
        nullable=False,
    )
    op.create_foreign_key(
        constraint_name="employee_health_plan_ibfk_3",
        source_table="employee_health_plan",
        referent_table="rte_payer_list",
        local_cols=["payer_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
        onupdate="CASCADE",
    )


def downgrade():
    op.drop_constraint(
        "employee_health_plan_ibfk_3", "employee_health_plan", type_="foreignkey"
    )
    op.alter_column(
        "employee_health_plan",
        "payer_id",
        new_column_name="insurer",
        existing_type=sa.BigInteger,
        nullable=False,
    )
    op.alter_column(
        "employee_health_plan",
        "relation",
        new_column_name="relationship",
        existing_type=sa.Enum(PatientAndSubscriberRelationship),
        nullable=False,
    )
    op.create_foreign_key(
        constraint_name="employee_health_plan_ibfk_3",
        source_table="employee_health_plan",
        referent_table="rte_payer_list",
        local_cols=["insurer"],
        remote_cols=["id"],
    )
