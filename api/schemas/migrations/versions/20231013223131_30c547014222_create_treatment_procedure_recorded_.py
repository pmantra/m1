"""create_treatment_procedure_recorded_answer_set_table

Revision ID: 30c547014222
Revises: 6997ec78145f
Create Date: 2023-10-13 22:31:31.859489+00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "30c547014222"
down_revision = "6997ec78145f"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS `treatment_procedure_recorded_answer_set` (
            `id` bigint(20) PRIMARY KEY NOT NULL AUTO_INCREMENT,
            `treatment_procedure_id` bigint(20) NOT NULL,
            `recorded_answer_set_id` bigint(20) NOT NULL UNIQUE,
            `questionnaire_id` bigint(20) NOT NULL,
            `user_id` int(11) NOT NULL,
            `fertility_clinic_id` bigint(20) NOT NULL,
            `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
            `modified_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX `ix_treatment_procedure_id` (`treatment_procedure_id`),
            INDEX `ix_recorded_answer_set_id` (`recorded_answer_set_id`),
            INDEX `ix_questionnaire_id` (`questionnaire_id`),
            INDEX `ix_user_id` (`user_id`),
            INDEX `ix_fertility_clinic_id` (`fertility_clinic_id`),
            CONSTRAINT `treatment_procedure_recorded_answer_set_ibfk_1` FOREIGN KEY (`treatment_procedure_id`) REFERENCES `treatment_procedure` (`id`)
                ON DELETE CASCADE
                ON UPDATE CASCADE,
            CONSTRAINT `treatment_procedure_recorded_answer_set_ibfk_2` FOREIGN KEY (`recorded_answer_set_id`) REFERENCES `recorded_answer_set` (`id`)
                ON DELETE CASCADE
                ON UPDATE CASCADE,
            CONSTRAINT `treatment_procedure_recorded_answer_set_ibfk_3` FOREIGN KEY (`questionnaire_id`) REFERENCES `questionnaire` (`id`)
                ON DELETE CASCADE
                ON UPDATE CASCADE,
            CONSTRAINT `treatment_procedure_recorded_answer_set_ibfk_4` FOREIGN KEY (`user_id`) REFERENCES `user` (`id`)
                ON DELETE CASCADE
                ON UPDATE CASCADE,
            CONSTRAINT `treatment_procedure_recorded_answer_set_ibfk_5` FOREIGN KEY (`fertility_clinic_id`) REFERENCES `fertility_clinic` (`id`)
                ON DELETE CASCADE
                ON UPDATE CASCADE
        );
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS `treatment_procedure_recorded_answer_set`;
        """
    )
