"""reimbursement_request_id_to_cost_breakdown

Revision ID: f7171bfed449
Revises: ab02eff69511
Create Date: 2024-03-07 22:57:32.003615+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "f7171bfed449"
down_revision = "ab02eff69511"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
        ALTER TABLE cost_breakdown
        ADD COLUMN reimbursement_request_id bigint(20) DEFAULT NULL AFTER treatment_procedure_uuid,
        ALGORITHM=INPLACE,
        LOCK=NONE;
    """
    op.execute(sql)


def downgrade():
    sql = """
        ALTER TABLE cost_breakdown
        DROP COLUMN reimbursement_request_id,
        ALGORITHM=INPLACE,
        LOCK=NONE;
    """
    op.execute(sql)
