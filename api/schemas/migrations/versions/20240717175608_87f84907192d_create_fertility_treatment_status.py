"""create_fertility_treatment_status

Revision ID: 87f84907192d
Revises: 6108180f93ff
Create Date: 2024-07-17 17:56:08.423352+00:00

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "87f84907192d"
down_revision = "6108180f93ff"
branch_labels = None
depends_on = None


def upgrade():
    sql = """
        CREATE TABLE IF NOT EXISTS `fertility_treatment_status` (
            `id` bigint(20) NOT NULL AUTO_INCREMENT comment 'Internal unique ID',
            `user_id` int(11) NOT NULL comment 'ID column from user table',
            `fertility_treatment_status` varchar(200) NOT NULL comment 'Fertility treatment status',
            `created_at` datetime DEFAULT CURRENT_TIMESTAMP comment 'The time at which this record was created',
            `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP comment 'The time at which this record was updated',
            PRIMARY KEY (`id`),
            CONSTRAINT `fk_member_fertility_treatment_status` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE,
            INDEX `ix_member_fertility_treatment_status_created_at` (`user_id`, `created_at` DESC)
        );
        """
    op.execute(sql)


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `fertility_treatment_status`;
        """
    )
