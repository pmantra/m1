"""increase fertility clinic location name limit

Revision ID: 03c75a89383c
Revises: d7bb09c7fe89
Create Date: 2024-05-21 17:34:25.058651+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "03c75a89383c"
down_revision = "d7bb09c7fe89"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `fertility_clinic_location`
        MODIFY COLUMN `name` varchar(191) COLLATE utf8mb4_unicode_ci NOT NULL;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `fertility_clinic_location`
        MODIFY COLUMN `name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL;
        """
    )
