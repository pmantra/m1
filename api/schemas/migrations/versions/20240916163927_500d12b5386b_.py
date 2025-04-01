"""create user_locale_preference table

Revision ID: 500d12b5386b
Revises: 52bdff1dca8f
Create Date: 2024-09-16 16:39:27.419462+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "500d12b5386b"
down_revision = "bac04d40a715"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE `user_locale_preference` (
          `id` int(11) NOT NULL AUTO_INCREMENT,
          `user_id` int(11) NOT NULL,
          `locale` varchar(255) NOT NULL,
          `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
          `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          PRIMARY KEY (`id`),
          UNIQUE KEY `user_id` (`user_id`),
          CONSTRAINT `fk_user_locale_preference` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE
        )
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `user_locale_preference`;
        """
    )
