"""add_async_encounter_summary

Revision ID: 586a13668149
Revises: 48e68c854773
Create Date: 2023-11-13 20:56:18.065926+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "586a13668149"
down_revision = "48e68c854773"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `async_encounter_summary`(
        `id` bigint(20) PRIMARY KEY NOT NULL AUTO_INCREMENT,
        `provider_id` int(11) NOT NULL,
        `user_id` int(11) NOT NULL,
        `questionnaire_id` bigint(20) NOT NULL,
        `encounter_date` datetime NOT NULL,
        `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
        `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX  `ix_provider_id` (`provider_id`),
        INDEX  `ix_user_id` (`user_id`),
        CONSTRAINT `fk_async_encounter_summary_questionnaire_id` FOREIGN KEY (`questionnaire_id`) REFERENCES `questionnaire` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
        CONSTRAINT `fk_async_encounter_summary_provider_id` FOREIGN KEY (`provider_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
        CONSTRAINT `fk_async_encounter_summary_user_id` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `async_encounter_summary_answer`;
        """
    )
