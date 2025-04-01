"""PAY-4946-update-ingestion-meta

Revision ID: d21ddd63347b
Revises: fb507e9b4700
Create Date: 2023-11-12 15:40:15.012830+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "d21ddd63347b"
down_revision = "fb507e9b4700"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE ingestion_meta
        MODIFY COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        MODIFY COLUMN modified_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        ALGORITHM=INPLACE, LOCK=NONE
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE ingestion_meta
        MODIFY COLUMN created_at DATETIME NULL,
        MODIFY COLUMN modified_at DATETIME NULL,
        ALGORITHM=INPLACE, LOCK=NONE
        """
    )
