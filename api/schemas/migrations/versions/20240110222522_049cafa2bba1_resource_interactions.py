"""resource_interactions

Revision ID: 049cafa2bba1
Revises: 94260c1782b3
Create Date: 2024-01-10 22:25:22.503764+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "049cafa2bba1"
down_revision = "94260c1782b3"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE `resource_interactions` (
            `user_id` int NOT NULL,
            `resource_type` varchar(50) NOT NULL,
            `slug` varchar(128) NOT NULL,
            `resource_viewed_at` datetime,
            `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`user_id`, `resource_type`, `slug`),
            CONSTRAINT `fk_resource_interactions_user` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `resource_interactions`;
        """
    )
