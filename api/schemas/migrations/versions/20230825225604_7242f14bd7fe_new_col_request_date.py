"""new-col-request-date

Revision ID: 7242f14bd7fe
Revises: 4e4ba6f051a0
Create Date: 2023-08-25 22:56:04.684127+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "7242f14bd7fe"
down_revision = "4e4ba6f051a0"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `gdpr_deletion_backup`
        ADD COLUMN `requested_date` date DEFAULT '2020-01-01',
        ALGORITHM=INPLACE,
        LOCK=NONE
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `gdpr_deletion_backup`
        DROP COLUMN `requested_date`,
        ALGORITHM=INPLACE,
        LOCK=NONE
        """
    )
