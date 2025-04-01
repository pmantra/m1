"""New Risk Flag Columns

Revision ID: 5170fe76866f
Revises: 03c75a89383c
Create Date: 2024-05-23 20:34:44.923468+00:00

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "5170fe76866f"
down_revision = "03c75a89383c"
branch_labels = None
depends_on = None


def upgrade():
    # Add boolean columns columns
    # Add COMPOSITE enum value to ecp_qualifier_type
    op.execute(
        """
        ALTER TABLE risk_flag 
            ADD is_mental_health BOOL NOT NULL DEFAULT FALSE,
            ADD is_chronic_condition BOOL NOT NULL DEFAULT FALSE,
            ADD is_utilization BOOL NOT NULL DEFAULT FALSE,
            ADD is_situational BOOL NOT NULL DEFAULT FALSE,
            ADD relevant_to_materity BOOL NOT NULL DEFAULT FALSE,
            ADD relevant_to_fertility BOOL NOT NULL DEFAULT FALSE;
    
        ALTER TABLE risk_flag 
            MODIFY ecp_qualifier_type ENUM ('RISK', 'CONDITION', 'COMPOSITE') NULL;

        UPDATE risk_flag
        SET is_mental_health = TRUE
        WHERE ecp_program_qualifier = 'MENTAL_HEALTH';  

        UPDATE risk_flag
        SET is_chronic_condition = TRUE
        WHERE ecp_program_qualifier = 'CHRONIC_CONDITIONS';  
        """
    )


def downgrade():
    # Delete data that might violate the old PK
    # And then revert all the schema changes
    op.execute(
        """
        ALTER TABLE risk_flag 
            DROP COLUMN is_mental_health,
            DROP COLUMN is_chronic_condition,
            DROP COLUMN is_utilization,
            DROP COLUMN is_situational,
            DROP COLUMN relevant_to_materity,
            DROP COLUMN relevant_to_fertility;
    
        ALTER TABLE risk_flag 
            MODIFY ecp_qualifier_type ENUM ('RISK', 'CONDITION') NULL;
        """
    )
