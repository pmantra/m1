"""add_error_message_to_atm

Revision ID: 488c8fe83a7e
Revises: 46979b86247b
Create Date: 2025-02-13 16:25:55.738181+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "488c8fe83a7e"
down_revision = "46979b86247b"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE accumulation_treatment_mapping
        ADD COLUMN row_error_reason varchar(1024) DEFAULT NULL,
        ALGORITHM=INPLACE, 
        LOCK=NONE;
    """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE accumulation_treatment_mapping
        DROP COLUMN row_error_reason,
        ALGORITHM=INPLACE, 
        LOCK=NONE;
    """
    )
