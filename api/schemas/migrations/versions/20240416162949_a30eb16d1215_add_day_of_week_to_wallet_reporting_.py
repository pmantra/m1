"""add day_of_week to wallet reporting configuration

Revision ID: a30eb16d1215
Revises: 1edb8a3ae653
Create Date: 2024-04-16 16:29:49.443735+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "a30eb16d1215"
down_revision = "1edb8a3ae653"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `wallet_client_report_configuration`
            ADD COLUMN `day_of_week` tinyint(1) NOT NULL DEFAULT 1 after `cadence`,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)


def downgrade():
    sql = """
            ALTER TABLE `wallet_client_report_configuration`
            DROP COLUMN `day_of_week`,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)
