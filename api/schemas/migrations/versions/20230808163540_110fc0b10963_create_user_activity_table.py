"""create_user_activity_table

Revision ID: 110fc0b10963
Revises: 74be3169efe3
Create Date: 2023-08-08 16:35:40.124615+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "110fc0b10963"
down_revision = "74be3169efe3"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
    CREATE TABLE IF NOT EXISTS `user_activity` (
        `id` INT(11) NOT NULL AUTO_INCREMENT,
        `user_id` INT(11) NOT NULL,
        `activity_type` VARCHAR(255),
        `activity_date` DATETIME DEFAULT CURRENT_TIMESTAMP,
        `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
        `modified_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        CONSTRAINT `user_activity_ibfk_1` FOREIGN KEY (`user_id`)
            REFERENCES `user` (`id`)
            ON DELETE CASCADE
            ON UPDATE CASCADE,
        KEY ix_user_id_activity_type (`user_id`, `activity_type`)
    )
    """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS `user_activity`")
