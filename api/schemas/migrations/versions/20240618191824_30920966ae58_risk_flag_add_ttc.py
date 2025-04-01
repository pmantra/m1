"""Risk Flag add ttc

Revision ID: 30920966ae58
Revises: b13e2fc88e7f
Create Date: 2024-06-18 19:18:24.387593+00:00

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "30920966ae58"
down_revision = "b13e2fc88e7f"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE risk_flag 
            ADD is_ttc_and_treatment BOOL NOT NULL DEFAULT FALSE,
            ALGORITHM=COPY, LOCK=SHARED;
            
        UPDATE risk_flag
            SET is_ttc_and_treatment = True
            WHERE uses_value = True;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE risk_flag 
            DROP COLUMN is_ttc_and_treatment;
        """
    )
