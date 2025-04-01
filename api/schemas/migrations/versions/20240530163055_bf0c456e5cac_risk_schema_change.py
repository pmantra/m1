"""Risk Schema Change

Revision ID: bf0c456e5cac
Create Date: 2024-05-30 16:30:55.317091+00:00

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "bf0c456e5cac"
down_revision = "270088333fff"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE risk_flag 
            ADD is_physical_health BOOL NOT NULL DEFAULT FALSE,
            ADD uses_value BOOL NOT NULL DEFAULT FALSE,
            ADD value_unit varchar(32)  DEFAULT NULL;
            
        UPDATE risk_flag
            set is_physical_health = is_chronic_condition;

        ALTER TABLE member_risk_flag
            ADD INDEX member_risk_flag_idx_user_risk(user_id, risk_flag_id),
            DROP INDEX member_risk_flag_idx_user_risk_end;
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE risk_flag 
            DROP COLUMN is_physical_health,
            DROP COLUMN uses_value,
            DROP COLUMN value_unit;

        ALTER TABLE member_risk_flag 
            ADD UNIQUE INDEX member_risk_flag_idx_user_risk_end (user_id, risk_flag_id, end),
            DROP INDEX member_risk_flag_idx_user_risk;  
        """
    )
