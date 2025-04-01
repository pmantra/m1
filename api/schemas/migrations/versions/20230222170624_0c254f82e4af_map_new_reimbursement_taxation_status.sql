-- migrate: up

UPDATE reimbursement_wallet rw,
    (
        SELECT
            id,
            CASE taxation_status
                WHEN 'QUALIFIED' THEN 'NON_TAXABLE'
                WHEN  'NON_QUALIFIED' THEN 'TAXABLE'
            END AS new_taxation_status
        FROM reimbursement_wallet
        WHERE taxation_status IN ('QUALIFIED', 'NON_QUALIFIED')
    ) statuses
SET rw.taxation_status = statuses.new_taxation_status
WHERE rw.id = statuses.id;
UPDATE reimbursement_organization_settings ros,
    (
        SELECT
            id,
            CASE taxation_status
                WHEN 'QUALIFIED' THEN 'NON_TAXABLE'
                WHEN  'NON_QUALIFIED' THEN 'TAXABLE'
            END AS new_taxation_status
        FROM reimbursement_organization_settings
        WHERE taxation_status IN ('QUALIFIED', 'NON_QUALIFIED')
    ) statuses
SET ros.taxation_status = statuses.new_taxation_status
WHERE ros.id = statuses.id;
UPDATE reimbursement_request rr,
    (
        SELECT
            id,
            CASE taxation_status
                WHEN 'QUALIFIED' THEN 'NON_TAXABLE'
                WHEN  'NON_QUALIFIED' THEN 'TAXABLE'
            END AS new_taxation_status
        FROM reimbursement_request
        WHERE taxation_status IN ('QUALIFIED', 'NON_QUALIFIED')
    ) statuses
SET rr.taxation_status = statuses.new_taxation_status
WHERE rr.id = statuses.id;

/* break */

-- migrate: down

UPDATE reimbursement_wallet rw,
    (
        SELECT
            id,
            CASE taxation_status
                WHEN 'NON_TAXABLE' THEN 'QUALIFIED'
                WHEN 'TAXABLE' THEN 'NON_QUALIFIED'
            END AS new_taxation_status
        FROM reimbursement_wallet
        WHERE taxation_status IN ('TAXABLE', 'NON_TAXABLE')
    ) statuses
SET rw.taxation_status = statuses.new_taxation_status
WHERE rw.id = statuses.id;
UPDATE reimbursement_organization_settings ros,
    (
        SELECT
            id,
            CASE taxation_status
                WHEN 'NON_TAXABLE' THEN 'QUALIFIED'
                WHEN 'TAXABLE' THEN 'NON_QUALIFIED'
            END AS new_taxation_status
        FROM reimbursement_organization_settings
        WHERE taxation_status IN ('TAXABLE', 'NON_TAXABLE')
    ) statuses
SET ros.taxation_status = statuses.new_taxation_status
WHERE ros.id = statuses.id;
UPDATE reimbursement_request rr,
    (
        SELECT
            id,
            CASE taxation_status
                WHEN 'NON_TAXABLE' THEN 'QUALIFIED'
                WHEN 'TAXABLE' THEN 'NON_QUALIFIED'
            END AS new_taxation_status
        FROM reimbursement_request
        WHERE taxation_status IN ('TAXABLE', 'NON_TAXABLE')
    ) statuses
SET rr.taxation_status = statuses.new_taxation_status
WHERE rr.id = statuses.id;
