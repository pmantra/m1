-- get_cancel_appointment_struct_by_id
SELECT
    a.id,
    a.product_id,
    a.scheduled_start,
    a.scheduled_end,
    a.member_started_at,
    a.member_ended_at,
    a.practitioner_started_at,
    a.practitioner_ended_at,
    a.cancelled_at,
    a.disputed_at,
    a.json              AS json_str,
    product.price       AS product_price,
    product.user_id     AS practitioner_id,
    schedule.user_id     AS member_id
FROM appointment a 
LEFT OUTER JOIN product product ON product.id = a.product_id
LEFT OUTER JOIN schedule schedule ON schedule.id = a.member_schedule_id
WHERE a.id = :appointment_id;


-- update_appointment_for_cancel
-- Note: COALESCE returns the first non-null value. In this case, it is used to
--       only update the row if the new value is not null
UPDATE appointment a
    SET cancelled_at = :cancelled_at,
        cancelled_by_user_id = :user_id,
        modified_at = :modified_at,
        json = COALESCE(:json_str, json)
    WHERE a.id = :appointment_id;


-- get_cancelled_by_user_id
SELECT
    appointment.cancelled_by_user_id
FROM appointment
WHERE appointment.id = :appointment_id;
