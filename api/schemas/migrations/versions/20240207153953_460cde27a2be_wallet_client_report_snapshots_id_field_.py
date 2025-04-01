"""wallet_client_report_snapshots_id_field_autoincrement

Revision ID: 460cde27a2be
Revises: eb151dc505e4
Create Date: 2024-02-07 15:39:53.771579+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "460cde27a2be"
down_revision = "eb151dc505e4"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `wallet_client_report_snapshots`
        MODIFY COLUMN `id` BIGINT AUTO_INCREMENT,
        ALGORITHM=COPY,
        LOCK=SHARED;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `wallet_client_report_snapshots`
        MODIFY COLUMN `id` bigint(20) NOT NULL,
        ALGORITHM=COPY,
        LOCK=SHARED;
        """
    )
