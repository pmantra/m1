"""add day_of_week to new wallet_report_config table

Revision ID: b302223e0b3c
Revises: 63c64a0a5f99
Create Date: 2024-05-14 11:19:27.256747+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b302223e0b3c"
down_revision = "63c64a0a5f99"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `wallet_client_report_configuration_v2`
            ADD COLUMN `day_of_week` tinyint(1) NOT NULL DEFAULT 1 after `cadence`,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)


def downgrade():
    sql = """
            ALTER TABLE `wallet_client_report_configuration_v2`
            DROP COLUMN `day_of_week`,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)
