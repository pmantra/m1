"""create incentive table

Revision ID: 065ef13b21fe
Revises: 950b5e0caee4
Create Date: 2023-10-05 16:38:36.162372+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "065ef13b21fe"
down_revision = "950b5e0caee4"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `incentive` (
            `id` int(11) PRIMARY KEY NOT NULL AUTO_INCREMENT,
            `type` enum('GIFT_CARD', 'WELCOME_BOX') NOT NULL,
            `name` varchar(128) NOT NULL,
            `amount` int(11),
            `vendor` varchar(128) NOT NULL,
            `design_asset` enum('GENERIC_GIFT_CARD', 'AMAZON_GIFT_CARD', 'WELCOME_BOX') NOT NULL,
            `active` bool NOT NULL,
            `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
            `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `incentive`;
        """
    )
