"""add_index_to_e9y_member_id_cols

Revision ID: d82e535460e5
Revises: aad1bc3d5969
Create Date: 2023-07-27 15:14:46.061509+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "d82e535460e5"
down_revision = "79b0b05f5e79"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `backfill_credit_state` (
            `id` int(11) NOT NULL AUTO_INCREMENT,
            `credit_id` int(11) NOT NULL,
            `eligibility_member_id` int(11) DEFAULT NULL,
            `updated` tinyint(1) not null default 0,
            PRIMARY KEY (`id`),
            KEY `credit_id` (`credit_id`),
            KEY `eligibility_member_id` (`eligibility_member_id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;   
    """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `backfill_credit_state`
    """
    )
