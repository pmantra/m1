"""make_report_id_accumulation_nullable

Revision ID: 7af2f5fff25a
Revises: 53ac6940663d
Create Date: 2023-11-01 15:58:36.681045+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "7af2f5fff25a"
down_revision = "53ac6940663d"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `accumulation_treatment_mapping`
        DROP FOREIGN KEY `payer_accumulation_reports_fk_1`,
        DROP INDEX `payer_accumulation_reports_fk_1`,
        MODIFY COLUMN `report_id` bigint(20) DEFAULT NULL,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `accumulation_treatment_mapping`
        MODIFY COLUMN `report_id` bigint(20) NOT NULL,
        ADD CONSTRAINT `payer_accumulation_reports_fk_1` FOREIGN KEY (`report_id`) REFERENCES `payer_accumulation_reports` (`id`),
        ALGORITHM=COPY, LOCK=SHARED;
        """
    )
