"""add name attr reimbursement_organization_settings

Revision ID: 3a63d38e2676
Revises: 8ab8b28a12c4
Create Date: 2023-09-20 04:04:45.819035+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "3a63d38e2676"
down_revision = "8ab8b28a12c4"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_organization_settings`
        ADD COLUMN `name` VARCHAR(50) DEFAULT NULL 
        AFTER `organization_id`,
        ALGORITHM=INPLACE, 
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `reimbursement_organization_settings`
        DROP COLUMN `name`,
        ALGORITHM=INPLACE, 
        LOCK=NONE;
        """
    )
