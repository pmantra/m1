"""set_rte_payer_id_to_nullable

Revision ID: 518d7b1f30ab
Revises: 0c63fbe6d816
Create Date: 2024-02-23 13:12:19.282730+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "518d7b1f30ab"
down_revision = "0c63fbe6d816"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
        ALTER TABLE `employer_health_plan`
        MODIFY `payer_id` bigint(20) DEFAULT NULL,
        MODIFY `benefits_payer_id` bigint(20) NOT NULL,
        ALGORITHM=COPY, LOCK=SHARED;
    """
    op.execute(sql)


def downgrade():
    sql = """
        ALTER TABLE `employer_health_plan`
        DROP FOREIGN KEY `employer_health_plan_ibfk_2`;
    
        ALTER TABLE `employer_health_plan`
        MODIFY `payer_id` bigint(20) NOT NULL,
        MODIFY `benefits_payer_id` bigint(20) DEFAULT NULL,
        ALGORITHM=COPY, LOCK=SHARED;
        
        ALTER TABLE `employer_health_plan`
        ADD CONSTRAINT `employer_health_plan_ibfk_2` FOREIGN KEY (`payer_id`) REFERENCES `rte_payer_list` (`id`) ON DELETE CASCADE ON UPDATE CASCADE;
    """
    op.execute(sql)
