-- get_appointment_transaction_info
SELECT
    appt_payment.payment_amount,
    appt_payment.payment_captured_at,
    appt_credits.total_used_credits,
    appt_credits.latest_used_at      AS credit_latest_used_at,
    appt_fees.count                  AS fees_count
FROM (
    -- Step 1: credit info
    SELECT
        appointment.id        AS appointment_id,
        max(credit.used_at)   AS latest_used_at,
        sum(credit.amount)    AS total_used_credits
    FROM appointment
    LEFT OUTER JOIN credit ON appointment.id = credit.appointment_id
    WHERE appointment.id = :appointment_id AND credit.used_at IS NOT NULL
) AS appt_credits

LEFT OUTER JOIN (
    -- Step 2: fee info
    SELECT
        appointment_id,
        count(*) AS count
    FROM fee_accounting_entry
    WHERE appointment_id = :appointment_id
) as appt_fees
ON appt_fees.appointment_id = appt_credits.appointment_id

LEFT OUTER JOIN (
    -- Step 3: payment info
    SELECT
        appointment_id,
        amount         AS payment_amount,
        captured_at    AS payment_captured_at
    FROM payment_accounting_entry
    WHERE appointment_id = :appointment_id
) AS appt_payment
ON appt_payment.appointment_id = appt_credits.appointment_id;