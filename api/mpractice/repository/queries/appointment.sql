-- get_appointment_by_id
SELECT
    appointment.id,
    appointment.scheduled_start,
    appointment.scheduled_end,
    appointment.client_notes,
    appointment.json,
    appointment.privacy,
    appointment.privilege_type,
    appointment.purpose,
    appointment.video,
    appointment.cancelled_at,
    appointment.disputed_at,
    appointment.member_started_at,
    appointment.member_ended_at,
    appointment.practitioner_started_at,
    appointment.practitioner_ended_at,
    appointment.phone_call_at,
    cancellation_policy.name             AS cancellation_policy_name,
    need.id                              AS need_id,
    need.name                            AS need_name,
    need.description                     AS need_description,
    schedule.user_id                     AS member_id,
    product.user_id                      AS practitioner_id,
    vertical.id                          AS vertical_id
FROM appointment
LEFT OUTER JOIN cancellation_policy ON appointment.cancellation_policy_id = cancellation_policy.id
LEFT OUTER JOIN need_appointment ON appointment.id = need_appointment.appointment_id
LEFT OUTER JOIN need ON need_appointment.need_id = need.id
LEFT OUTER JOIN schedule ON appointment.member_schedule_id = schedule.id
LEFT OUTER JOIN product ON appointment.product_id = product.id
LEFT OUTER JOIN vertical ON product.vertical_id = vertical.id
WHERE appointment.id = :appointment_id;

-- get_latest_post_session_note
SELECT
    content AS notes,
    draft,
    created_at
FROM appointment_metadata
WHERE appointment_id = :appointment_id
ORDER BY modified_at DESC, created_at DESC, id DESC;

-- get_post_session_notes_by_appointment_ids
SELECT
    appointment_id,
    content AS notes,
    draft,
    created_at,
    modified_at
FROM appointment_metadata
WHERE appointment_id IN :appointment_ids
ORDER BY appointment_id, modified_at DESC, created_at DESC, id DESC;