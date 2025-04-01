"""Add reimbursement_account_type to reimbursement_plan

Revision ID: 9afd71a96afb
Revises: 345c984723e6
Create Date: 2021-09-02 17:56:14.418437+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "9afd71a96afb"
down_revision = "345c984723e6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "reimbursement_plan",
        sa.Column(
            "reimbursement_account_type_id",
            sa.BigInteger,
            sa.ForeignKey("reimbursement_account_type.id"),
        ),
    )


def downgrade():
    op.drop_constraint(
        "reimbursement_plan_ibfk_1", "reimbursement_plan", type_="foreignkey"
    )
    op.drop_column("reimbursement_plan", "reimbursement_account_type_id")
