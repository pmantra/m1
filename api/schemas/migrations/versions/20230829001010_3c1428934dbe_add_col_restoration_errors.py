"""add-col-restoration_errors

Revision ID: 3c1428934dbe
Revises: 7242f14bd7fe
Create Date: 2023-08-29 00:10:10.766034+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "3c1428934dbe"
down_revision = "7242f14bd7fe"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `gdpr_deletion_backup`
        ADD COLUMN `restoration_errors` longtext DEFAULT NULL,
        ALGORITHM=INPLACE,
        LOCK=NONE
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `gdpr_deletion_backup`
        DROP COLUMN `restoration_errors`,
        ALGORITHM=INPLACE,
        LOCK=NONE
        """
    )
