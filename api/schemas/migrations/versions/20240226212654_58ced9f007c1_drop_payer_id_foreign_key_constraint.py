"""drop_payer_id_foreign_key_constraint

Revision ID: 58ced9f007c1
Revises: 71c1b342ed3e
Create Date: 2024-02-26 21:26:54.803839+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "58ced9f007c1"
down_revision = "71c1b342ed3e"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
        ALTER TABLE `employer_health_plan`
        DROP FOREIGN KEY `employer_health_plan_ibfk_2`,
        DROP KEY `employer_health_plan_ibfk_2`,
        ALGORITHM=COPY, LOCK=SHARED;
    """
    op.execute(sql)


def downgrade():
    sql = """
        ALTER TABLE `employer_health_plan`
        ADD CONSTRAINT `employer_health_plan_ibfk_2` FOREIGN KEY (`payer_id`) REFERENCES `rte_payer_list` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
        ALGORITHM=COPY, LOCK=SHARED;
    """
    op.execute(sql)
