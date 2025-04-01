-- get_post_appointment_notes
SELECT
    id,
    appointment_id,
    created_at,
    content,
    draft,
    modified_at,
    message_id
FROM appointment_metadata
WHERE appointment_id IN :appointment_ids
ORDER BY appointment_id ASC, modified_at DESC, created_at DESC, id DESC;
