-- get_member_appointments_video_timestamp
SELECT
    a.id,
    a.member_started_at,
    a.member_ended_at,
    a.json as json_str,
    a.practitioner_started_at,
    a.practitioner_ended_at,
    a.cancelled_at,
    a.disputed_at,
    a.scheduled_start,
    a.scheduled_end,
    a.phone_call_at,
    p.user_id as provider_id,
    s.user_id as member_id
FROM appointment a
-- These joins are technically outside the appts domain,
-- but in the apptservice this info will be in the same table.
JOIN product p on a.product_id = p.id
JOIN schedule s on a.member_schedule_id = s.id
WHERE
    a.id = :appointment_id
;

-- set_member_appointments_video_timestamp
-- NOTE: COALESCE returns the first non-null value. In this instance, it is used to 
--       only update the row if the new value is not null
UPDATE appointment
SET 
    member_started_at = COALESCE(:member_started_at, member_started_at),
    member_ended_at = COALESCE(:member_ended_at, member_ended_at),
    practitioner_started_at = COALESCE(:practitioner_started_at, practitioner_started_at),
    practitioner_ended_at = COALESCE(:practitioner_ended_at, practitioner_ended_at),
    phone_call_at = COALESCE(:phone_call_at, phone_call_at),
    modified_at = :modified_at,
    json = COALESCE(:json_str, json)
WHERE id = :appointment_id
;
