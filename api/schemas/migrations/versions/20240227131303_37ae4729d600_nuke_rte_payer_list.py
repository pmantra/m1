"""nuke_rte_payer_list

Revision ID: 37ae4729d600
Revises: 58ced9f007c1
Create Date: 2024-02-27 13:13:03.077529+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "37ae4729d600"
down_revision = "58ced9f007c1"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
        ALTER TABLE `employer_health_plan`
        DROP COLUMN `payer_id`,
        ALGORITHM=COPY, LOCK=SHARED;
        
        DROP TABLE `rte_payer_list`;
    """
    op.execute(sql)


def downgrade():
    sql = """
        CREATE TABLE `rte_payer_list` (
          `id` bigint(20) NOT NULL AUTO_INCREMENT,
          `payer_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
          `payer_code` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
          PRIMARY KEY (`id`)
        );
        
        ALTER TABLE `employer_health_plan`
        ADD COLUMN payer_id bigint(20) DEFAULT NULL,
        ALGORITHM=COPY, LOCK=SHARED;
    """
    op.execute(sql)
