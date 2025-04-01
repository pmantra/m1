"""add_reimbursement_request_id_to_accum_treatment_mapping

Revision ID: a3ae80627328
Revises: 2527df8369b5
Create Date: 2024-02-16 22:53:01.516887+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "a3ae80627328"
down_revision = "2527df8369b5"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
        ALTER TABLE `accumulation_treatment_mapping`
        ADD COLUMN `reimbursement_request_id` bigint(20) DEFAULT NULL AFTER `reimbursement_claim_id`,
        ALGORITHM=INPLACE, LOCK=NONE;
    """
    op.execute(sql)


def downgrade():
    sql = """
        ALTER TABLE `accumulation_treatment_mapping`
        DROP COLUMN `reimbursement_request_id`,
        ALGORITHM=INPLACE, LOCK=NONE;
    """
    op.execute(sql)
