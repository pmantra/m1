"""create_questionnaire_global_procedure_table

Revision ID: 6997ec78145f
Revises: 9de74a570042
Create Date: 2023-10-13 20:48:23.690835+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "6997ec78145f"
down_revision = "9de74a570042"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `questionnaire_global_procedure` (
            `id` bigint(20) PRIMARY KEY NOT NULL AUTO_INCREMENT,
            `questionnaire_id` bigint(20) NOT NULL,
            `global_procedure_id` char(36) NOT NULL,
            INDEX `ix_questionnaire_id` (`questionnaire_id`),
            INDEX `ix_global_procedure_id` (`global_procedure_id`),
            CONSTRAINT `questionnaire_global_procedure_ibfk_1` FOREIGN KEY (`questionnaire_id`) REFERENCES `questionnaire` (`id`)
                ON DELETE CASCADE
                ON UPDATE CASCADE,
            CONSTRAINT `uq_questionnaire_global_procedure` UNIQUE (`questionnaire_id`, `global_procedure_id`)
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `questionnaire_global_procedure`;
        """
    )
