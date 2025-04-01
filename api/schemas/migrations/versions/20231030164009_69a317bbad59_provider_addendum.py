"""provider-addendum

Revision ID: 69a317bbad59
Revises: d7a8b7b444c9
Create Date: 2023-10-30 16:40:09.157203+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "69a317bbad59"
down_revision = "d7a8b7b444c9"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `provider_addendum`(
        `id` bigint(20) PRIMARY KEY NOT NULL AUTO_INCREMENT,
        `submitted_at` datetime NOT NULL,
        `appointment_id` int(11) NOT NULL,
        `questionnaire_id` bigint(20) NOT NULL,
        `associated_answer_id` bigint(20) NOT NULL,
        `user_id` int(11) NOT NULL,
        `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
        `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX  `ix_appointment_id` (`appointment_id`),
        INDEX  `ix_associated_answer_id` (`associated_answer_id`),
        CONSTRAINT `fk_provider_addendum_appointment_id` FOREIGN KEY (`appointment_id`) REFERENCES `appointment` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
        CONSTRAINT `fk_provider_addendum_questionnaire_id` FOREIGN KEY (`questionnaire_id`) REFERENCES `questionnaire` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
        CONSTRAINT `fk_provider_addendum_associated_answer_id` FOREIGN KEY (`associated_answer_id`) REFERENCES `recorded_answer` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
        CONSTRAINT `fk_provider_addendum_user_id` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `provider_addendum`;
        """
    )
