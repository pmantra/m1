"""Add Anthem to payer list

Revision ID: a186ec792b4d
Revises: 789394635a74
Create Date: 2024-08-14 19:26:30.597906+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "a186ec792b4d"
down_revision = "789394635a74"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
        ALTER TABLE `payer_list`
        MODIFY COLUMN `payer_name` enum('UHC','Cigna','ESI','OHIO_HEALTH', 'AETNA', 'BLUE_EXCHANGE', 'ANTHEM') COLLATE utf8mb4_unicode_ci NOT NULL,
        ALGORITHM=COPY, LOCK=SHARED;
    """
    op.execute(sql)


def downgrade():
    sql = """
        ALTER TABLE `payer_list`
        MODIFY COLUMN `payer_name` enum('UHC','Cigna','ESI','OHIO_HEALTH', 'AETNA', 'BLUE_EXCHANGE') COLLATE utf8mb4_unicode_ci NOT NULL,
        ALGORITHM=COPY, LOCK=SHARED;
    """
    op.execute(sql)
