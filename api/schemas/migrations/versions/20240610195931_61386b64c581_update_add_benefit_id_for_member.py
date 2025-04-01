"""update_add_benefit_id_for_member

Revision ID: 61386b64c581
Revises: 017d7ce5a9ed
Create Date: 2024-06-10 19:59:31.491271+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "61386b64c581"
down_revision = "017d7ce5a9ed"
branch_labels = None
depends_on = None


def upgrade():
    q = """
    DROP FUNCTION add_benefit_id_for_member;
    CREATE FUNCTION add_benefit_id_for_member(user_id INT)
    RETURNS VARCHAR(16)
    NOT DETERMINISTIC
    BEGIN
        DECLARE to_insert VARCHAR(16) DEFAULT NULL;
        DECLARE i INT DEFAULT 3;
        DECLARE done INT DEFAULT FALSE;
        retry:
            REPEAT
                BEGIN
                    DECLARE CONTINUE HANDLER FOR SQLSTATE '23000'
                        BEGIN
                            SET i = i - 1;
                        END;
    
                    IF done OR i < 0 THEN
                        LEAVE retry;
                    END IF;
    
                    SET to_insert = CONCAT('M', LPAD(FLOOR(RAND(CURRENT_TIMESTAMP) * 999999999), 9, '0'));
                    INSERT INTO member_benefit (user_id, benefit_id)
                    VALUES (user_id, to_insert);
                    SET done = TRUE;
                END;
            UNTIL FALSE END REPEAT;
    
        RETURN to_insert;
    END;
    """
    op.execute(q)


def downgrade():
    q = """
    DROP FUNCTION add_benefit_id_for_member;
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
