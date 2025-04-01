"""add_user_preferences_table

Revision ID: 679066dce759
Revises: 14fba3f0bd2d
Create Date: 2023-01-19 20:35:06.040533+00:00

"""
from alembic import op


# revision identifiers used by Alembic.
revision = "679066dce759"
down_revision = "14fba3f0bd2d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
            CREATE TABLE IF NOT EXISTS `member_preferences` (
                `id` INT(11) PRIMARY KEY NOT NULL AUTO_INCREMENT,
                `member_id` INT(11) NOT NULL,
                `preference_id` INT(11) NOT NULL,
                `value` VARCHAR(255) DEFAULT NULL,
                CONSTRAINT `member_preferences_ibfk_1` FOREIGN KEY (`member_id`) REFERENCES `member_profile` (`user_id`),
                CONSTRAINT `preference_id_ibfk_2` FOREIGN KEY (`preference_id`) REFERENCES `preferences` (`id`)
        )
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS `member_preferences`")
