"""reimbursement-request-cost-credit

Revision ID: f8dc11ec225d
Revises: b6c13ae367ae
Create Date: 2024-04-16 20:06:48.556688+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "f8dc11ec225d"
down_revision = "b6c13ae367ae"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
        ALTER TABLE reimbursement_request
        ADD COLUMN `cost_credit` int(11) DEFAULT NULL after `procedure_type`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
    """
    op.execute(sql)


def downgrade():
    sql = """
        ALTER TABLE reimbursement_request
        DROP COLUMN `cost_credit`,
        ALGORITHM=INPLACE,
        LOCK=NONE;
    """
    op.execute(sql)
