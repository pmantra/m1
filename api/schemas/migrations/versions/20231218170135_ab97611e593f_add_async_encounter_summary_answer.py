"""add_async_encounter_summary_answer

Revision ID: ab97611e593f
Revises: 28c8ec06044d
Create Date: 2023-12-18 17:01:35.836499+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "ab97611e593f"
down_revision = "28c8ec06044d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `async_encounter_summary_answer`(
        `id` bigint(20) PRIMARY KEY NOT NULL AUTO_INCREMENT,
        `async_encounter_summary_id` bigint(20) NOT NULL,
        `question_id` bigint(20) NOT NULL,
        `answer_id` bigint(20) DEFAULT NULL,
        `text` varchar(6000) DEFAULT NULL,
        `date` datetime DEFAULT NULL,
        `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
        `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX  `ix_async_encounter_summary_id` (`async_encounter_summary_id`),
        CONSTRAINT `fk_async_encounter_summary_answer_async_encounter_summary_id` FOREIGN KEY (`async_encounter_summary_id`) REFERENCES `async_encounter_summary` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
        CONSTRAINT `fk_async_encounter_summary_answer_question_id` FOREIGN KEY (`question_id`) REFERENCES `question` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
        CONSTRAINT `fk_async_encounter_summary_answer_answer_id` FOREIGN KEY (`answer_id`) REFERENCES `answer` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `async_encounter_summary_answer`;
        """
    )
