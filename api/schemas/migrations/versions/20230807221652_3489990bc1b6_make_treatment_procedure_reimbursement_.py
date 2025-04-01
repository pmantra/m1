"""make_treatment_procedure_reimbursement_wallet_gp_id_nullable

Revision ID: 3489990bc1b6
Revises: 6dbfba8b43a6
Create Date: 2023-08-07 22:16:52.822699+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "3489990bc1b6"
down_revision = "6dbfba8b43a6"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "treatment_procedure",
        "reimbursement_wallet_global_procedures_id",
        nullable=True,
        existing_type=sa.BigInteger,
    )


def downgrade():
    op.alter_column(
        "treatment_procedure",
        "reimbursement_wallet_global_procedures_id",
        nullable=False,
        existing_type=sa.BigInteger,
    )
