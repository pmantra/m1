"""backfill_member_id_in_cost_breakdown

Revision ID: f546b47c30b7
Revises: ec10a90340d3
Create Date: 2024-02-12 17:39:45.161001+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "f546b47c30b7"
down_revision = "ec10a90340d3"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE cost_breakdown
        SET member_id = (
            SELECT treatment_procedure.member_id 
            FROM treatment_procedure 
            WHERE cost_breakdown.treatment_procedure_uuid = treatment_procedure.uuid
        );
        """
    )


def downgrade():
    op.execute(
        """
        UPDATE cost_breakdown
        SET member_id = NULL;
        """
    )
