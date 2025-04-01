"""BEX-2763_1_3_allowed_members

Revision ID: 56b23f91fc11
Revises: a30eb16d1215
Create Date: 2024-05-01 17:23:59.244256+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "56b23f91fc11"
down_revision = "a30eb16d1215"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    ALTER TABLE `reimbursement_organization_settings` ADD COLUMN `allowed_members` enum('SHAREABLE', 'MULTIPLE_PER_MEMBER', 'SINGLE_EMPLOYEE_ONLY', 
    'SINGLE_ANY_USER', 'SINGLE_DEPENDENT_ONLY','MULTIPLE_DEPENDENT_ONLY' ) NOT NULL DEFAULT 'SINGLE_ANY_USER';
    """
    )


def downgrade():
    op.execute(
        """
    ALTER TABLE `reimbursement_organization_settings` DROP COLUMN `allowed_members`;
    """
    )
