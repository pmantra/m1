"""populate-feature-type-table

Revision ID: 3ab107b77578
Revises: 6d925a992ab9
Create Date: 2023-09-13 15:40:40.482830+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "3ab107b77578"
down_revision = "6d925a992ab9"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        INSERT IGNORE INTO `feature_type`
            (`name`, `enum_id`)
        VALUES
            ('Tracks', 1),
            ('Wallets', 2);
        """
    )


def downgrade():
    op.execute(
        """
        DELETE FROM `feature_type`
        WHERE (`name` = 'Tracks' AND `enum_id` = 1)
        OR (`name` = 'Wallets' AND `enum_id` = 2);
        """
    )
