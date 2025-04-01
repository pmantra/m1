DELIMITER $$
-- region: table definition
--   Define the new schema for external identities.
CREATE TABLE IF NOT EXISTS `user_external_identity` (
    id BIGINT PRIMARY KEY NOT NULL AUTO_INCREMENT,
    user_id INT NOT NULL,
    identity_provider_id BIGINT NOT NULL,
    external_user_id VARCHAR(120) NOT NULL,
    external_organization_id VARCHAR(120) DEFAULT NULL,
    unique_corp_id VARCHAR(120) DEFAULT NULL,
    reporting_id VARCHAR(120) DEFAULT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    modified_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (identity_provider_id)
        REFERENCES `identity_provider`(`id`)
        ON DELETE CASCADE,
    FOREIGN KEY (user_id)
        REFERENCES `user`(`id`)
        ON DELETE CASCADE,
    INDEX ix_user_external_identity_external_user_id (external_user_id),
    INDEX ix_user_external_identity_unique_corp_id (unique_corp_id),
    INDEX ix_user_external_identity_external_organization_id (external_organization_id),
    UNIQUE (identity_provider_id, external_user_id),
    UNIQUE (reporting_id)
)$$
-- Fix the column definition in the legacy schema
ALTER TABLE external_identity
    DROP COLUMN external_organization_id,
    ADD COLUMN external_organization_id VARCHAR(120) DEFAULT NULL;
-- Make created_at and modified_at server defaults on the user table.
ALTER TABLE user
    MODIFY created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    MODIFY modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
-- endregion

-- region: idempotency
-- We can't use OR REPLACE or IF NOT EXISTS with triggers or procedures...
DROP TRIGGER IF EXISTS before_external_identity_insert$$
DROP TRIGGER IF EXISTS before_org_external_id_insert$$
DROP TRIGGER IF EXISTS after_external_identity_insert$$
DROP TRIGGER IF EXISTS before_external_identity_update$$
DROP TRIGGER IF EXISTS after_external_identity_update$$
DROP TRIGGER IF EXISTS before_org_external_id_update$$
DROP TRIGGER IF EXISTS after_external_identity_delete$$
DROP PROCEDURE IF EXISTS fillIdentityProviders$$
DROP PROCEDURE IF EXISTS copyExternalIdentity$$
DROP PROCEDURE IF EXISTS copyExternalIdentities$$
DROP PROCEDURE IF EXISTS lookupIDPForOrganization$$
DROP PROCEDURE IF EXISTS lookupOrgExternalIDForIdentity$$
-- endregion

-- region: procedures
--   setup procedures to dry out the upcoming triggers.
-- fill the idp id for all dependent tables.
CREATE PROCEDURE fillIdentityProviders() MODIFIES SQL DATA
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
END $$
CREATE PROCEDURE copyExternalIdentity(
    IN user_id_in INT,
    IN identity_provider_id_in BIGINT,
    IN external_user_id_in VARCHAR(120),
    IN external_organization_id_in VARCHAR(120),
    IN unique_corp_id_in VARCHAR(120),
    IN reporting_id_in VARCHAR(120)
) MODIFIES SQL DATA
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
END $$
CREATE PROCEDURE copyExternalIdentities() MODIFIES SQL DATA
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
END $$
CREATE PROCEDURE lookupIDPForOrganization(
    IN organization_id INT, OUT idp BIGINT
) DETERMINISTIC
BEGIN
    SELECT identity_provider.id INTO idp
        FROM identity_provider
        INNER JOIN organization_external_id
            ON organization_external_id.identity_provider_id = identity_provider.id
            OR organization_external_id.idp = identity_provider.name
        WHERE organization_external_id.organization_id = organization_id
    ;
END $$
CREATE PROCEDURE lookupOrgExternalIDForIdentity(
    IN organization_id INT, OUT external_id VARCHAR(120)
) DETERMINISTIC
BEGIN
    SELECT organization_external_id.external_id INTO external_id
        FROM organization_external_id
        WHERE organization_external_id.organization_id = organization_id
    ;
END $$
-- endregion: procedures

-- region: crud triggers
--   Set up triggers to automatically track changes between tables.

-- region: inserts
-- Always track the identity_provider id for the external identity.
CREATE TRIGGER before_external_identity_insert
    BEFORE INSERT
    ON external_identity FOR EACH ROW
    BEGIN
        IF NEW.identity_provider_id IS NULL THEN
            CALL lookupIDPForOrganization(NEW.organization_id, NEW.identity_provider_id);
        END IF;
        IF NEW.external_organization_id IS NULL THEN
            CALL lookupOrgExternalIDForIdentity(NEW.organization_id, NEW.external_organization_id);
        END IF;
    END $$
-- Always track the identity_provider id for the org external id.
CREATE TRIGGER before_org_external_id_insert
    BEFORE INSERT
    ON organization_external_id FOR EACH ROW
    BEGIN
        IF NEW.identity_provider_id IS NULL THEN
            CALL lookupIDPForOrganization(NEW.organization_id, NEW.identity_provider_id);
        END IF;
    END $$
-- Always copy the identity to the new table.
CREATE TRIGGER after_external_identity_insert
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
    END $$
-- endregion

-- region: updates
--   NOTE: this is functionally equivalent to the above triggers,
--       except this runs for updates instead of inserts.
CREATE TRIGGER before_external_identity_update
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
    END $$
-- Always track the identity_provider id for the org external id.
CREATE TRIGGER before_org_external_id_update
    BEFORE UPDATE
    ON organization_external_id FOR EACH ROW
    BEGIN
        SET @idp = COALESCE(NEW.identity_provider_id, OLD.identity_provider_id);
        SET @org = COALESCE(NEW.organization_id, OLD.organization_id);
        IF @idp IS NULL THEN
            CALL lookupIDPForOrganization(@org, NEW.identity_provider_id);
        END IF;
    END $$
-- Always copy the identity to the new table
CREATE TRIGGER after_external_identity_update
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
    END $$
-- endregion

-- region: deletes
CREATE TRIGGER after_external_identity_delete
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
    END $$
-- endregion

-- endregion

-- region: data migration
CALL fillIdentityProviders()$$
CALL copyExternalIdentities()$$
-- endregion
