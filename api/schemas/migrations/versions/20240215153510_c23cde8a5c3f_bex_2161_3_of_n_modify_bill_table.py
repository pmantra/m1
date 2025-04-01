"""BEX-2161_3_of_n_modify_bill_table

Revision ID: c23cde8a5c3f
Revises: 6318192ddd6f
Create Date: 2024-02-15 15:35:10.163511+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "c23cde8a5c3f"
down_revision = "6318192ddd6f"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `bill`
        ADD COLUMN processing_scheduled_at_or_after datetime DEFAULT NULL
        COMMENT 'The time at or after which this bill can be processed.',
        ADD INDEX ix_processing_scheduled_at_or_after (processing_scheduled_at_or_after),
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `bill`
        DROP COLUMN processing_scheduled_at_or_after,
        DROP INDEX ix_processing_scheduled_at_or_after,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
