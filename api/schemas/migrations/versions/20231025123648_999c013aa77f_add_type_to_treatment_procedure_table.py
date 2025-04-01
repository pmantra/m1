"""add_type_to_treatment_procedure_table

Revision ID: 999c013aa77f
Revises: 8ae8519d27a9
Create Date: 2023-10-25 12:36:48.790036+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "999c013aa77f"
down_revision = "8ae8519d27a9"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE `treatment_procedure`
        ADD COLUMN `type` enum('MEDICAL', 'PHARMACY') default 'MEDICAL' after `procedure_name`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE `treatment_procedure`
        DROP COLUMN `type`,
        ALGORITHM=INPLACE, LOCK=NONE;
        """
    )
