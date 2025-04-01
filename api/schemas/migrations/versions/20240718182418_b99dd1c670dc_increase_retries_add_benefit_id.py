"""increase_retries_add_benefit_id_for_member

Revision ID: b99dd1c670dc
Revises: c1a624b098f7
Create Date: 2024-07-11 18:24:18.770995+00:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "b99dd1c670dc"
down_revision = "87f84907192d"
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
        DECLARE i INT DEFAULT 20;
        DECLARE done INT DEFAULT FALSE;
        DECLARE CONTINUE HANDLER FOR SQLSTATE '23000'
            BEGIN
                SET i = i - 1;
            END;

        retry:
            REPEAT
                BEGIN
                    IF done = TRUE OR i < 0 THEN
                        IF done = FALSE AND i < 0 THEN
                            SET to_insert = '-1';
                        END IF;
                        LEAVE retry;
                    END IF;

                    SET to_insert = CONCAT('M', LPAD(FLOOR(RAND() * 999999999), 9, '0'));
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
