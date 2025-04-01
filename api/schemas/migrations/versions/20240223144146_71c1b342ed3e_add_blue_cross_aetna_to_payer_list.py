"""add_blue_cross_aetna_to_payer_list

Revision ID: 71c1b342ed3e
Revises: 518d7b1f30ab
Create Date: 2024-02-23 14:41:46.330455+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "71c1b342ed3e"
down_revision = "518d7b1f30ab"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
        ALTER TABLE `payer_list`
        MODIFY COLUMN `payer_name` enum('UHC','Cigna','ESI','OHIO_HEALTH', 'AETNA', 'BLUE_EXCHANGE') COLLATE utf8mb4_unicode_ci NOT NULL,
        ALGORITHM=COPY, LOCK=SHARED;
    """
    op.execute(sql)


def downgrade():
    sql = """
        ALTER TABLE `payer_list`
        MODIFY COLUMN `payer_name` enum('UHC','Cigna','ESI','OHIO_HEALTH') COLLATE utf8mb4_unicode_ci NOT NULL,
        ALGORITHM=COPY, LOCK=SHARED;
    """
    op.execute(sql)
