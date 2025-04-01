DELIMITER $$

-- region: idempotency
-- We can't use OR REPLACE or IF NOT EXISTS with triggers or procedures...
DROP TRIGGER IF EXISTS after_next_availability_update$$
DROP TRIGGER IF EXISTS after_next_availability_delete$$
-- endregion

-- region: crud triggers
CREATE TRIGGER after_next_availability_update
    AFTER UPDATE
    ON practitioner_profile
    FOR EACH ROW
    BEGIN
        IF OLD.next_availability != NEW.next_availability THEN
            UPDATE practitioner_data
            SET next_availability = NEW.next_availability
            WHERE user_id = NEW.user_id;
        END IF;
    END $$

CREATE TRIGGER after_next_availability_delete
    AFTER DELETE
    ON practitioner_profile FOR EACH ROW
    BEGIN
        DELETE FROM practitioner_data
        WHERE user_id = OLD.user_id;
    END $$
-- endregion