"""New Member Risk Flag Columns

Revision ID: 914decf50888
Create Date: 2024-05-23 21:48:04.122445+00:00

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "914decf50888"
down_revision = "5170fe76866f"
branch_labels = None
depends_on = None


def upgrade():
    # Add ID Column, make it the primary Key
    #       Need to drop the FKs before changing PK
    op.execute(
        """
        ALTER TABLE member_risk_flag
            DROP FOREIGN KEY member_risk_flag_ibfk_1,
            DROP FOREIGN KEY member_risk_flag_ibfk_2,
            DROP INDEX user_flag_users_ibfk_2;
        ALTER TABLE member_risk_flag
            DROP PRIMARY KEY,
            ADD id INT AUTO_INCREMENT  PRIMARY KEY;
        ALTER TABLE member_risk_flag
            ADD CONSTRAINT member_risk_flag_fk_risk FOREIGN KEY (risk_flag_id) REFERENCES risk_flag(id),
            ADD CONSTRAINT member_risk_flag_fk_user FOREIGN KEY (user_id) REFERENCES user(id);                        
        """
    )

    # Add the new columns
    op.execute(
        """
        ALTER TABLE member_risk_flag 
            ADD value INT, 
            ADD start DATE,
            ADD end DATE,
            ADD confirmed_at DATETIME,
            ADD modified_at datetime DEFAULT NOW() ON UPDATE NOW(),
            ADD modified_by INT,
            ADD modified_reason varchar(255),
            ADD UNIQUE INDEX member_risk_flag_idx_user_risk_end (user_id, risk_flag_id, end);  
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE member_risk_flag       
            DROP FOREIGN KEY member_risk_flag_fk_risk,
            DROP FOREIGN KEY member_risk_flag_fk_user,
            DROP INDEX member_risk_flag_idx_user_risk_end;

        ALTER TABLE member_risk_flag     
            DROP COLUMN id,
            DROP PRIMARY KEY,
            ADD PRIMARY KEY(risk_flag_id, user_id);

        ALTER TABLE member_risk_flag 
            DROP COLUMN value, 
            DROP COLUMN start,
            DROP COLUMN end,
            DROP COLUMN confirmed_at,
            DROP COLUMN modified_at,
            DROP COLUMN modified_by,
            DROP COLUMN modified_reason;

        ALTER TABLE member_risk_flag
            ADD CONSTRAINT member_risk_flag_ibfk_1 FOREIGN KEY (risk_flag_id) REFERENCES risk_flag(id),
            ADD CONSTRAINT member_risk_flag_ibfk_2 FOREIGN KEY (user_id) REFERENCES user(id),
            Add INDEX user_flag_users_ibfk_2 (user_id);
        """
    )
