SELECT
    a.max_capacity,
    a.daily_intro_capacity,
    p.booking_buffer,
    p.default_prep_buffer
FROM
    practitioner_profile p
LEFT JOIN
    assignable_advocate a ON a.practitioner_id = p.user_id
WHERE
    p.user_id = :provider_id;


SELECT EXISTS (
    SELECT s.slug
        FROM member_care_team ct
        JOIN practitioner_specialties ps on ps.user_id = ct.practitioner_id
        JOIN specialty s on s.id = ps.specialty_id
        WHERE ct.user_id = :member_id
        AND ct.type = 'CARE_COORDINATOR'
        AND s.slug = :specialty_slug)
;
