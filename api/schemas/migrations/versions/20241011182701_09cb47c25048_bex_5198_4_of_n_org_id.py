"""BEX-5198_4_of_n_org_id

Revision ID: 09cb47c25048
Revises: 77139469012c
Create Date: 2024-10-11 18:27:01.844774+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "09cb47c25048"
down_revision = "77139469012c"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE reimbursement_plan
        ADD COLUMN `organization_id` int DEFAULT NULL,
        ADD INDEX `organization_id_idx` (`organization_id`),        
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_plan`
        DROP INDEX `organization_id_idx`,
        DROP COLUMN `organization_id`,
        ALGORITHM=INPLACE, 
        LOCK=NONE;
        """
    )
