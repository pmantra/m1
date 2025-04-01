"""provider-addendum-answer

Revision ID: f2b18d9dc43b
Revises: 69a317bbad59
Create Date: 2023-10-30 16:45:24.583636+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "f2b18d9dc43b"
down_revision = "69a317bbad59"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `provider_addendum_answer`(
        `id` bigint(20) PRIMARY KEY NOT NULL AUTO_INCREMENT,
        `addendum_id` bigint(20) NOT NULL,
        `question_id` bigint(20) NOT NULL,
        `answer_id` bigint(20) DEFAULT NULL,
        `text` varchar(6000) DEFAULT NULL,
        `date` datetime DEFAULT NULL,
        `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
        `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX  `ix_addendum_id` (`addendum_id`),
        CONSTRAINT `fk_provider_addendum_answer_addendum_id` FOREIGN KEY (`addendum_id`) REFERENCES `provider_addendum` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
        CONSTRAINT `fk_provider_addendum_answer_question_id` FOREIGN KEY (`question_id`) REFERENCES `question` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
        CONSTRAINT `fk_provider_addendum_answer_answer_id` FOREIGN KEY (`answer_id`) REFERENCES `answer` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `provider_addendum_answer`;
        """
    )
