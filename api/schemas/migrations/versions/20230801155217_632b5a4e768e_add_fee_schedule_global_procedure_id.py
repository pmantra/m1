"""add_fee_schedule_global_procedure_id

Revision ID: 632b5a4e768e
Revises: 4a9cf0b567e2
Create Date: 2023-08-01 15:52:17.163451+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "632b5a4e768e"
down_revision = "c54d46d01d82"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """ALTER TABLE maven.fee_schedule_global_procedures
            ADD COLUMN global_procedure_id CHAR(36),
            ADD UNIQUE KEY fee_schedule_global_procedure_id_uq (fee_schedule_id, global_procedure_id),
            ALGORITHM=INPLACE, LOCK=NONE
        """
    )


def downgrade():
    op.execute(
        """ALTER TABLE maven.fee_schedule_global_procedures
            DROP KEY fee_schedule_global_procedure_id_uq,
            DROP COLUMN global_procedure_id,
            ALGORITHM=INPLACE, LOCK=NONE
        """
    )
