"""increase fertility clinic name limit 

Revision ID: 534cb29dc8c5
Revises: 96fbac0c9cc4
Create Date: 2024-03-29 15:09:32.257099+00:00

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "534cb29dc8c5"
down_revision = "96fbac0c9cc4"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `fertility_clinic`
        MODIFY COLUMN `name` varchar(191) COLLATE utf8mb4_unicode_ci DEFAULT NULL;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `fertility_clinic`
        MODIFY COLUMN `name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL;
        """
    )
