"""Add course_member_status table

Revision ID: 94260c1782b3
Revises: 5885b9ab19a6
Create Date: 2024-01-10 22:22:23.784100+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "94260c1782b3"
down_revision = "5885b9ab19a6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE `course_member_status` (
            `user_id` int NOT NULL,
            `course_id` varchar(50) NOT NULL,
            `status` varchar(50) NOT NULL,
            `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
            `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`user_id`, `course_id`),
            CONSTRAINT `fk_course_member_status_user_id` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `course_member_status`;
        """
    )
