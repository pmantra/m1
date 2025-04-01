
/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE TRIGGER before_external_identity_insert
    BEFORE INSERT
    ON external_identity FOR EACH ROW
    BEGIN
        IF NEW.identity_provider_id IS NULL THEN
            CALL lookupIDPForOrganization(NEW.organization_id, NEW.identity_provider_id);
        END IF;
        IF NEW.external_organization_id IS NULL THEN
            CALL lookupOrgExternalIDForIdentity(NEW.organization_id, NEW.external_organization_id);
        END IF;
    END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE TRIGGER after_external_identity_insert
    AFTER INSERT
    ON external_identity FOR EACH ROW
    BEGIN
        IF NEW.identity_provider_id IS NOT NULL THEN
            CALL copyExternalIdentity(
                NEW.user_id,
                NEW.identity_provider_id,
                NEW.external_user_id,
                NEW.external_organization_id,
                NEW.unique_corp_id,
                NEW.rewards_id
            );
        END IF;
    END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE TRIGGER before_external_identity_update
    BEFORE UPDATE
    ON external_identity FOR EACH ROW
    BEGIN
        SET @idp = COALESCE(NEW.identity_provider_id, OLD.identity_provider_id);
        SET @org = COALESCE(NEW.organization_id, OLD.organization_id);
        SET @external_org = COALESCE(NEW.external_organization_id, OLD.external_organization_id);
        IF @idp IS NULL THEN
            CALL lookupIDPForOrganization(@org, NEW.identity_provider_id);
        END IF;
        IF @external_org IS NULL THEN
            CALL lookupOrgExternalIDForIdentity(NEW.organization_id, NEW.external_organization_id);
        END IF;
    END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE TRIGGER after_external_identity_update
    AFTER UPDATE
    ON external_identity FOR EACH ROW
    BEGIN
        IF NEW.identity_provider_id IS NOT NULL THEN
            CALL copyExternalIdentity(
                NEW.user_id,
                NEW.identity_provider_id,
                NEW.external_user_id,
                NEW.external_organization_id,
                NEW.unique_corp_id,
                NEW.rewards_id
            );
        END IF;
    END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE TRIGGER after_external_identity_delete
    AFTER DELETE
    ON external_identity FOR EACH ROW
    BEGIN
        DELETE FROM user_external_identity
        WHERE
            (
                OLD.user_id,
                OLD.identity_provider_id,
                OLD.external_user_id
            ) = (
                user_external_identity.user_id,
                user_external_identity.identity_provider_id,
                user_external_identity.external_user_id
            )
        ;
    END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE TRIGGER before_org_external_id_insert
    BEFORE INSERT
    ON organization_external_id FOR EACH ROW
    BEGIN
        IF NEW.identity_provider_id IS NULL THEN
            CALL lookupIDPForOrganization(NEW.organization_id, NEW.identity_provider_id);
        END IF;
    END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE TRIGGER before_org_external_id_update
    BEFORE UPDATE
    ON organization_external_id FOR EACH ROW
    BEGIN
        SET @idp = COALESCE(NEW.identity_provider_id, OLD.identity_provider_id);
        SET @org = COALESCE(NEW.organization_id, OLD.organization_id);
        IF @idp IS NULL THEN
            CALL lookupIDPForOrganization(@org, NEW.identity_provider_id);
        END IF;
    END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE TRIGGER after_next_availability_update
            AFTER UPDATE
            ON practitioner_profile
            FOR EACH ROW
            BEGIN
                IF OLD.next_availability != NEW.next_availability THEN
                    UPDATE practitioner_data
                    SET next_availability = NEW.next_availability
                    WHERE user_id = NEW.user_id;
                END IF;
            END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE TRIGGER after_next_availability_delete
            AFTER DELETE
            ON practitioner_profile FOR EACH ROW
            BEGIN
                DELETE FROM practitioner_data
                WHERE user_id = OLD.user_id;
            END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE TRIGGER after_wallet_client_report_configuration_insert
    AFTER INSERT
    ON wallet_client_report_configuration FOR EACH ROW
    BEGIN
        INSERT INTO wallet_client_report_configuration_v2 (
            `cadence`,
            `organization_id`
        )
        VALUES (NEW.cadence, NEW.organization_id);
    END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE TRIGGER after_wallet_client_report_configuration_update
    AFTER UPDATE
    ON wallet_client_report_configuration FOR EACH ROW
    BEGIN
        UPDATE wallet_client_report_configuration_v2
        SET cadence = NEW.cadence, organization_id = NEW.organization_id
        WHERE organization_id = OLD.organization_id;
    END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE TRIGGER after_wallet_client_report_configuration_delete
    AFTER DELETE
    ON wallet_client_report_configuration FOR EACH ROW
    BEGIN
        DELETE FROM wallet_client_report_configuration_v2
        WHERE organization_id = OLD.organization_id;
    END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE TRIGGER after_wallet_client_report_configuration_report_columns_insert
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
    END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE TRIGGER after_wallet_client_report_configuration_report_columns_update
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
    END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
/*!50003 CREATE TRIGGER after_wallet_client_report_configuration_report_columns_delete
    AFTER DELETE
    ON wallet_client_report_configuration_report_columns FOR EACH ROW
    BEGIN
        DELETE FROM wallet_client_report_configuration_report_columns_v2
        WHERE wallet_client_report_configuration_id = (
            SELECT config.id
            FROM wallet_client_report_configuration_v2 config
            WHERE config.organization_id = OLD.wallet_client_report_configuration_id
        ) AND wallet_client_report_configuration_report_type_id = old.wallet_client_report_configuration_report_type_id;
    END */;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE FUNCTION `add_benefit_id_for_member`(user_id INT) RETURNS varchar(16) CHARSET utf8mb4 COLLATE utf8mb4_unicode_ci
BEGIN
        DECLARE to_insert VARCHAR(16) DEFAULT NULL;
        DECLARE i INT DEFAULT 20;
        DECLARE done INT DEFAULT FALSE;
    
        retry:
            REPEAT
                BEGIN
                    DECLARE CONTINUE HANDLER FOR SQLSTATE '23000'
                        BEGIN
                            SET i = i - 1;
                        END;
    
                    IF done = TRUE OR i < 0 THEN
                        IF done = FALSE AND i < 0 THEN
                            SET to_insert = '-1';
                        END IF;
                        LEAVE retry;
                    END IF;
    
                    SET to_insert = CONCAT('M', LPAD(FLOOR(RAND() * 999999999), 9, '0'));
                    INSERT INTO member_benefit (user_id, benefit_id)
                    VALUES (user_id, to_insert);
    
                    IF ROW_COUNT() = 1 THEN
                        SET done = TRUE;
                    END IF;
                END;
            UNTIL FALSE END REPEAT;
    
        RETURN to_insert;
    END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE PROCEDURE `copyExternalIdentities`()
    MODIFIES SQL DATA
BEGIN
    INSERT INTO `user_external_identity` (
        `user_id`,
        `identity_provider_id`,
        `external_user_id`,
        `external_organization_id`,
        `unique_corp_id`,
        `reporting_id`
    )
        SELECT
            `user_id`,
            `identity_provider_id`,
            `external_user_id`,
            `external_organization_id`,
            `unique_corp_id`,
            `rewards_id`
        FROM `external_identity`
        WHERE identity_provider_id IN (SELECT id from identity_provider)
    ON DUPLICATE KEY UPDATE
        `user_id`=VALUES(`user_id`),
        `identity_provider_id`=VALUES(`identity_provider_id`),
        `external_user_id`=VALUES(`external_user_id`),
        `external_organization_id`=VALUES(`external_organization_id`),
        `unique_corp_id`=VALUES(`unique_corp_id`),
        `reporting_id`=VALUES(`reporting_id`)
    ;
END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE PROCEDURE `copyExternalIdentity`(
    IN user_id_in INT,
    IN identity_provider_id_in BIGINT,
    IN external_user_id_in VARCHAR(120),
    IN external_organization_id_in VARCHAR(120),
    IN unique_corp_id_in VARCHAR(120),
    IN reporting_id_in VARCHAR(120)
)
    MODIFIES SQL DATA
BEGIN
    INSERT INTO `user_external_identity` (
        user_id,
        identity_provider_id,
        external_user_id,
        external_organization_id,
        unique_corp_id,
        reporting_id
    ) VALUES (
        user_id_in,
        identity_provider_id_in,
        external_user_id_in,
        external_organization_id_in,
        unique_corp_id_in,
        reporting_id_in
    )
    ON DUPLICATE KEY UPDATE
        user_id=VALUES(user_id),
        identity_provider_id=VALUES(identity_provider_id),
        external_user_id=VALUES(external_user_id),
        external_organization_id=VALUES(external_organization_id),
        unique_corp_id=VALUES(unique_corp_id),
        reporting_id=VALUES(reporting_id)
    ;
END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE PROCEDURE `fillIdentityProviders`()
    MODIFIES SQL DATA
BEGIN
    UPDATE organization_external_id
        INNER JOIN identity_provider
            ON organization_external_id.idp = identity_provider.name
    SET identity_provider_id = identity_provider.id;
    UPDATE external_identity
        INNER JOIN organization_external_id
            ON organization_external_id.organization_id = external_identity.organization_id
    SET
        external_identity.identity_provider_id = organization_external_id.identity_provider_id,
        external_identity.external_organization_id = organization_external_id.id;
END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE PROCEDURE `lookupIDPForOrganization`(
    IN organization_id INT, OUT idp BIGINT
)
    DETERMINISTIC
BEGIN
    SELECT identity_provider.id INTO idp
        FROM identity_provider
        INNER JOIN organization_external_id
            ON organization_external_id.identity_provider_id = identity_provider.id
            OR organization_external_id.idp = identity_provider.name
        WHERE organization_external_id.organization_id = organization_id
    ;
END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!50003 SET @saved_cs_client      = @@character_set_client */ ;
/*!50003 SET @saved_cs_results     = @@character_set_results */ ;
/*!50003 SET @saved_col_connection = @@collation_connection */ ;
/*!50003 SET character_set_client  = utf8mb4 */ ;
/*!50003 SET character_set_results = utf8mb4 */ ;
/*!50003 SET collation_connection  = utf8mb4_general_ci */ ;
/*!50003 SET @saved_sql_mode       = @@sql_mode */ ;
/*!50003 SET sql_mode              = 'NO_ENGINE_SUBSTITUTION' */ ;
DELIMITER ;;
CREATE PROCEDURE `lookupOrgExternalIDForIdentity`(
    IN organization_id INT, OUT external_id VARCHAR(120)
)
    DETERMINISTIC
BEGIN
    SELECT organization_external_id.external_id INTO external_id
        FROM organization_external_id
        WHERE organization_external_id.organization_id = organization_id
    ;
END ;;
DELIMITER ;
/*!50003 SET sql_mode              = @saved_sql_mode */ ;
/*!50003 SET character_set_client  = @saved_cs_client */ ;
/*!50003 SET character_set_results = @saved_cs_results */ ;
/*!50003 SET collation_connection  = @saved_col_connection */ ;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

