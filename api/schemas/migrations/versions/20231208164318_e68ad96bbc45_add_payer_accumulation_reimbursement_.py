"""add-payer-accumulation-reimbursement-claim-fields

Revision ID: e68ad96bbc45
Revises: f6322f22eb2c
Create Date: 2023-12-08 16:43:18.527754+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "e68ad96bbc45"
down_revision = "f6322f22eb2c"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
        ALTER TABLE `accumulation_treatment_mapping`
        MODIFY COLUMN `treatment_procedure_uuid` varchar(36) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
        ADD COLUMN `reimbursement_claim_id` bigint(20) DEFAULT NULL AFTER `treatment_procedure_uuid`,
        ALGORITHM=INPLACE, LOCK=NONE;
    """
    op.execute(sql)


def downgrade():
    sql = """
        ALTER TABLE `accumulation_treatment_mapping`
        DROP COLUMN `reimbursement_claim_id`,
        ALGORITHM=INPLACE, LOCK=NONE;
    """
    op.execute(sql)
