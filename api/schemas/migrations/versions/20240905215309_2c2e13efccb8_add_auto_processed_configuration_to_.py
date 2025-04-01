"""add auto_processed configuration to reimbursement request for smp

Revision ID: 2c2e13efccb8
Revises: a2ae53a03853
Create Date: 2024-09-05 21:53:09.352353+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "2c2e13efccb8"
down_revision = "a2ae53a03853"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
            ALTER TABLE `reimbursement_request`
            ADD COLUMN auto_processed enum('RX') COLLATE utf8mb4_unicode_ci default NULL,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)


def downgrade():
    sql = """
            ALTER TABLE `reimbursement_request`
            DROP COLUMN auto_processed,
            ALGORITHM=COPY, LOCK=SHARED;
        """
    op.execute(sql)
