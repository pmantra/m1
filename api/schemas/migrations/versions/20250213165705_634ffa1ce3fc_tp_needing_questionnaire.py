"""tp_needing_questionnaire

Revision ID: 634ffa1ce3fc
Revises: 488c8fe83a7e
Create Date: 2025-02-13 16:57:05.540589+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "634ffa1ce3fc"
down_revision = "488c8fe83a7e"
branch_labels = None
depends_on = None


def upgrade():
    stmt = """
        CREATE TABLE IF NOT EXISTS treatment_procedures_needing_questionnaires(
            `id` int(11) NOT NULL AUTO_INCREMENT,
            `treatment_procedure_id` bigint(20),
            `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `modified_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `treatment_procedure_id_idx` (`treatment_procedure_id`),
            CONSTRAINT `treatment_procedure_fk` FOREIGN KEY (`treatment_procedure_id`) REFERENCES `treatment_procedure` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    op.execute(stmt)


def downgrade():
    op.execute("DROP TABLE IF EXISTS treatment_procedures_needing_questionnaires;")
