"""treatment-procedure-partial-procedure

Revision ID: d2c71cd58430
Revises: 9de74a570042
Create Date: 2023-10-13 19:44:28.287169+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "d2c71cd58430"
down_revision = "30c547014222"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `treatment_procedure`
        ADD COLUMN `partial_procedure_id` bigint(20) DEFAULT NULL,
        ADD CONSTRAINT `treatment_procedure_partial_fk` 
        FOREIGN KEY (`partial_procedure_id`) REFERENCES `treatment_procedure` (`id`)
        ON DELETE CASCADE
        ON UPDATE CASCADE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `treatment_procedure`
        DROP FOREIGN KEY `treatment_procedure_partial_fk`;
        """
    )
    op.execute(
        """
        ALTER TABLE `treatment_procedure`
        DROP COLUMN `partial_procedure_id`;
        """
    )
