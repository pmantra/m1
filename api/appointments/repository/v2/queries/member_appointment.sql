-- Get member appointment by id
SELECT
    a.id,
    a.schedule_event_id,
    a.member_schedule_id,
    a.product_id,
    a.scheduled_start,
    a.scheduled_end,
    a.member_started_at,
    a.member_ended_at,
    a.privacy,
    a.privilege_type,
    a.practitioner_started_at,
    a.practitioner_ended_at,
    a.cancelled_at,
    a.client_notes,
    a.disputed_at,
    a.plan_segment_id,
    a.phone_call_at,
    a.json as json_str,
    a.video
FROM appointment a 
WHERE a.id = :appointment_id
;

-- Get current or next appointment for user
SELECT
    a.id,
    a.schedule_event_id,
    a.member_schedule_id,
    a.product_id,
    a.scheduled_start,
    a.scheduled_end,
    a.member_started_at,
    a.member_ended_at,
    a.privacy,
    a.privilege_type,
    a.practitioner_started_at,
    a.practitioner_ended_at,
    a.cancelled_at,
    a.client_notes,
    a.disputed_at,
    a.plan_segment_id,
    a.phone_call_at,
    a.json as json_str,
    a.video
FROM appointment a
INNER JOIN schedule s ON s.id = a.member_schedule_id
WHERE
    s.user_id = :member_id AND a.cancelled_at is NULL AND a.scheduled_end > UTC_TIMESTAMP()
ORDER BY a.scheduled_start ASC
LIMIT 1
;