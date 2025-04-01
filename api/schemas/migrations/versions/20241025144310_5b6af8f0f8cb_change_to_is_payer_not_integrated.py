"""change_to_is_payer_not_integrated

Revision ID: 5b6af8f0f8cb
Revises: a7a360957be9
Create Date: 2024-10-25 14:43:10.684343+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "5b6af8f0f8cb"
down_revision = "a7a360957be9"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `employer_health_plan`
            CHANGE COLUMN `is_payer_integrated` `is_payer_not_integrated` tinyint(1) NOT NULL DEFAULT '0',
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)


def downgrade():
    sql = """
            ALTER TABLE `employer_health_plan`
            CHANGE COLUMN `is_payer_not_integrated` `is_payer_integrated` tinyint(1) NOT NULL DEFAULT '0',
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)
