"""add_function_add_benefit_id_for_member

Revision ID: 270088333fff
Revises: bc5c6baafb07
Create Date: 2024-05-29 17:10:41.512641+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "270088333fff"
down_revision = "bc5c6baafb07"
branch_labels = None
depends_on = None


def upgrade():
    q = """
    CREATE FUNCTION add_benefit_id_for_member(user_id INT)
    RETURNS VARCHAR(16)
    NOT DETERMINISTIC
    BEGIN
        DECLARE to_insert VARCHAR(16) DEFAULT NULL;
        DECLARE existing VARCHAR(16) DEFAULT NULL;
        SET existing = (SELECT benefit_id FROM member_benefit WHERE member_benefit.user_id=user_id);
        IF existing IS NOT NULL THEN
            RETURN existing;
        ELSE
            REPEAT
                SET to_insert = CONCAT('M', LPAD(FLOOR(RAND(CURRENT_TIMESTAMP) * 999999999), 9, '0'));
            UNTIL NOT EXISTS(SELECT benefit_id FROM member_benefit WHERE member_benefit.benefit_id=to_insert)
            END REPEAT;
    
            INSERT INTO member_benefit (user_id, benefit_id)
                VALUES (user_id, to_insert);
    
            RETURN (SELECT benefit_id FROM member_benefit WHERE member_benefit.user_id=user_id);
        END IF;
    END;
    """
    op.execute(q)


def downgrade():
    q = """
    DROP FUNCTION add_benefit_id_for_member;
    """
    op.execute(q)
