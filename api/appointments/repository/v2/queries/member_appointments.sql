-- get_member_appointments_asc
SELECT
    a.id,
    a.client_notes,
    a.cancelled_at,
    a.disputed_at,
    a.json as json_str,
    a.member_started_at,
    a.member_ended_at,
    a.privacy,
    a.privilege_type,
    a.phone_call_at,
    a.practitioner_started_at,
    a.practitioner_ended_at,
    a.product_id,
    a.scheduled_start,
    a.scheduled_end
FROM appointment a 
INNER JOIN schedule s ON s.id = a.member_schedule_id
WHERE
    s.user_id = :member_id
    AND a.scheduled_start >= :scheduled_start
    AND a.scheduled_end <= :scheduled_end
ORDER BY a.scheduled_start ASC
LIMIT :limit
OFFSET :offset
;

-- get_member_appointments_desc
SELECT
    a.id,
    a.client_notes,
    a.cancelled_at,
    a.disputed_at,
    a.json as json_str,
    a.member_started_at,
    a.member_ended_at,
    a.privacy,
    a.privilege_type,
    a.phone_call_at,
    a.practitioner_started_at,
    a.practitioner_ended_at,
    a.product_id,
    a.scheduled_start,
    a.scheduled_end
FROM appointment a 
INNER JOIN schedule s ON s.id = a.member_schedule_id
WHERE
    s.user_id = :member_id
    AND a.scheduled_start >= :scheduled_start
    AND a.scheduled_end <= :scheduled_end
ORDER BY a.scheduled_start DESC
LIMIT :limit
OFFSET :offset
;

-- get_member_appointments_count
SELECT
    count(*)
FROM appointment a
INNER JOIN schedule s ON s.id = a.member_schedule_id
WHERE
    s.user_id = :member_id
    AND a.scheduled_start >= :scheduled_start
    AND a.scheduled_end <= :scheduled_end
;

-- get_payment_pending_appointment_ids
SELECT a.id from appointment a
LEFT JOIN payment_accounting_entry pae on pae.appointment_id = a.id
LEFT JOIN credit c on c.appointment_id = a.id
WHERE
    a.scheduled_start >= :scheduled_start_cutoff
    AND a.cancelled_at IS NULL
    AND a.disputed_at IS NULL
    AND a.member_ended_at IS NOT NULL
    AND a.practitioner_ended_at IS NOT NULL
    AND pae.captured_at IS NULL
    AND c.used_at IS NULL
;
