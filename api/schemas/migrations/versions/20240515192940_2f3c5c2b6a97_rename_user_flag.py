"""rename-user-flag-users

Revision ID: 2f3c5c2b6a97
Revises: 31c5cd9dc15a
Create Date: 2024-05-15 

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "2f3c5c2b6a97"
down_revision = "b302223e0b3c"
branch_labels = None
depends_on = None


def upgrade():
    # Rename user_flag -> risk_flag & 2 of its columns
    # Rename user_flag_users -> member_risk_flag & its risk_flag id column
    # Create Views to allow backwards compatability (code and sql commands can still read/write as if they tables had their old naming)
    sql = """
        RENAME TABLE user_flag TO risk_flag;
        ALTER TABLE risk_flag change type severity enum ('NONE', 'LOW_RISK', 'MEDIUM_RISK', 'HIGH_RISK') not null;
        ALTER TABLE risk_flag change ecp_flag_type ecp_qualifier_type  enum ('RISK', 'CONDITION') null;

        RENAME TABLE user_flag_users TO member_risk_flag;
        ALTER TABLE member_risk_flag change user_flag_id risk_flag_id int not null;

        
        CREATE VIEW user_flag AS
            SELECT id, name, severity as type, modified_at, created_at, ecp_qualifier_type as ecp_flag_type, ecp_program_qualifier
            FROM risk_flag;
        CREATE VIEW user_flag_users AS
            SELECT risk_flag_id as user_flag_id, user_id, created_at
            FROM member_risk_flag;
       """
    op.execute(sql)


def downgrade():
    sql = """
        DROP VIEW user_flag;
        DROP VIEW user_flag_users;

        
        RENAME TABLE risk_flag TO user_flag;
        ALTER TABLE user_flag change severity type enum ('NONE', 'LOW_RISK', 'MEDIUM_RISK', 'HIGH_RISK') not null;
        ALTER TABLE user_flag change ecp_qualifier_type ecp_flag_type enum ('RISK', 'CONDITION') null;

        RENAME TABLE member_risk_flag TO user_flag_users;
        ALTER TABLE user_flag_users change risk_flag_id user_flag_id int not null;
        """
    op.execute(sql)
