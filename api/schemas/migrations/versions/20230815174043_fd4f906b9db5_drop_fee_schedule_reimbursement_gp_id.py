"""drop_fee_schedule_reimbursement_gp_id

Revision ID: fd4f906b9db5
Revises: 4848a3069f08
Create Date: 2023-08-15 17:40:43.861648+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "fd4f906b9db5"
down_revision = "be50b083d542"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE maven.fee_schedule_global_procedures
            DROP INDEX fee_schedule_global_procedures_uq_1,
            DROP COLUMN reimbursement_wallet_global_procedures_id,
            ALGORITHM=INPLACE, LOCK=NONE
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE maven.fee_schedule_global_procedures
            ADD COLUMN reimbursement_wallet_global_procedures_id BIGINT(20),
            ADD UNIQUE KEY fee_schedule_global_procedures_uq_1 (
                fee_schedule_id, reimbursement_wallet_global_procedures_id
             ),
             ALGORITHM=INPLACE, LOCK=NONE 
        """
    )
