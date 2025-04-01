"""BEX-4816-update-ros-model

Revision ID: b5a979514aec
Revises: 23f0849f183a
Create Date: 2024-09-24 17:44:59.970736+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "b5a979514aec"
down_revision = "23f0849f183a"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
    ALTER TABLE reimbursement_organization_settings
    ADD COLUMN run_out_days INTEGER,
    ADD COLUMN eligibility_loss_rule ENUM(
        'TERMINATION_DATE',
        'END_OF_MONTH_FOLLOWING_TERMINATION'
    ),
    ALGORITHM=COPY;
    """
    op.execute(sql)


def downgrade():
    sql = """
    ALTER TABLE reimbursement_organization_settings
    DROP COLUMN eligibility_loss_rule,
    DROP COLUMN run_out_days,
    ALGORITHM=COPY;
    """
    op.execute(sql)
