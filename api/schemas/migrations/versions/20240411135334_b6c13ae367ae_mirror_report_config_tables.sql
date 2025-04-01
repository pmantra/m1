DELIMITER $$

-- Copy existing data to new tables
INSERT INTO `wallet_client_report_configuration_v2` (`cadence`, `organization_id`)
SELECT `cadence`, `organization_id`
FROM `wallet_client_report_configuration`$$

INSERT INTO `wallet_client_report_configuration_report_columns_v2` (`wallet_client_report_configuration_report_type_id`, `wallet_client_report_configuration_id`)
SELECT columns.wallet_client_report_configuration_report_type_id, config.id
FROM wallet_client_report_configuration_report_columns columns INNER JOIN wallet_client_report_configuration_v2 config
ON columns.wallet_client_report_configuration_id = config.organization_id$$

-- Backfill configuration id data into wallet client reports table
UPDATE `wallet_client_reports` report
JOIN `wallet_client_report_configuration_v2` config ON report.organization_id = config.organization_id
SET report.configuration_id = config.id$$


-- Triggers for wallet_client_report_configuration
CREATE TRIGGER after_wallet_client_report_configuration_insert
    AFTER INSERT
    ON wallet_client_report_configuration FOR EACH ROW
    BEGIN
        INSERT INTO wallet_client_report_configuration_v2 (
            `cadence`,
            `organization_id`
        )
        VALUES (NEW.cadence, NEW.organization_id);
    END $$

CREATE TRIGGER after_wallet_client_report_configuration_update
    AFTER UPDATE
    ON wallet_client_report_configuration FOR EACH ROW
    BEGIN
        UPDATE wallet_client_report_configuration_v2
        SET cadence = NEW.cadence, organization_id = NEW.organization_id
        WHERE organization_id = OLD.organization_id;
    END $$

CREATE TRIGGER after_wallet_client_report_configuration_delete
    AFTER DELETE
    ON wallet_client_report_configuration FOR EACH ROW
    BEGIN
        DELETE FROM wallet_client_report_configuration_v2
        WHERE organization_id = OLD.organization_id;
    END $$


-- Triggers for wallet_client_report_configuration_report_columns
CREATE TRIGGER after_wallet_client_report_configuration_report_columns_insert
    AFTER INSERT
    ON wallet_client_report_configuration_report_columns FOR EACH ROW
    BEGIN
        INSERT INTO wallet_client_report_configuration_report_columns_v2 (
            `wallet_client_report_configuration_report_type_id`,
            `wallet_client_report_configuration_id`
        )
        VALUES (
            NEW.wallet_client_report_configuration_report_type_id,
            (SELECT id FROM wallet_client_report_configuration_v2 WHERE organization_id = NEW.wallet_client_report_configuration_id)
        );
    END $$

CREATE TRIGGER after_wallet_client_report_configuration_report_columns_update
    AFTER UPDATE
    ON wallet_client_report_configuration_report_columns FOR EACH ROW
    BEGIN
        UPDATE wallet_client_report_configuration_v2
        SET wallet_client_report_configuration_report_type_id = NEW.wallet_client_report_configuration_report_type_id,
            wallet_client_report_configuration_id = (
                SELECT config.id
                FROM wallet_client_report_configuration_v2 config
                WHERE config.organization_id = NEW.wallet_client_report_configuration_id
                )
        WHERE wallet_client_report_configuration_id = (
                SELECT config.id
                FROM wallet_client_report_configuration_v2 config
                WHERE config.organization_id = OLD.wallet_client_report_configuration_id
            );
    END $$

CREATE TRIGGER after_wallet_client_report_configuration_report_columns_delete
    AFTER DELETE
    ON wallet_client_report_configuration_report_columns FOR EACH ROW
    BEGIN
        DELETE FROM wallet_client_report_configuration_report_columns_v2
        WHERE wallet_client_report_configuration_id = (
            SELECT config.id
            FROM wallet_client_report_configuration_v2 config
            WHERE config.organization_id = OLD.wallet_client_report_configuration_id
        ) AND wallet_client_report_configuration_report_type_id = old.wallet_client_report_configuration_report_type_id;
    END
