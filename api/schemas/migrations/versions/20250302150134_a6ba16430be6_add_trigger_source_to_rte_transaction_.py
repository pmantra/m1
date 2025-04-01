"""add_trigger_source_to_rte_transaction_table

Revision ID: a6ba16430be6
Revises: 700f409bafa8
Create Date: 2025-03-02 15:01:34.499453+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "a6ba16430be6"
down_revision = "700f409bafa8"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE maven.rte_transaction
        ADD COLUMN trigger_source VARCHAR(255) NULL,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE maven.rte_transaction
        DROP COLUMN trigger_source,
        ALGORITHM=INPLACE,
        LOCK=NONE;
        """
    )
