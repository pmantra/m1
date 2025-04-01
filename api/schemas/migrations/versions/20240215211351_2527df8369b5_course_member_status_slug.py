"""course-member-status-slug

Revision ID: 2527df8369b5
Revises: c23cde8a5c3f
Create Date: 2024-02-15 21:13:51.972072+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "2527df8369b5"
down_revision = "c23cde8a5c3f"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `course_member_status`;
        """
    )
    op.execute(
        """
        CREATE TABLE `course_member_status` (
            `user_id` int NOT NULL,
            `course_slug` varchar(50) NOT NULL,
            `status` varchar(50) NOT NULL,
            `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
            `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`user_id`, `course_slug`),
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
