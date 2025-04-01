SELECT
    member_track.id,
    member_track.name,
    member_track.anchor_date,
    member_track.start_date,
    member_track.activated_at,
    client_track.length_in_days,
    organization.id as org_id,
    organization.name as org_name,
    organization.display_name as org_display_name,
    CASE 
        WHEN member_track.ended_at IS NULL AND member_track.activated_at IS NOT NULL THEN TRUE 
        ELSE FALSE 
    END AS is_active
FROM
    member_track
LEFT JOIN client_track ON member_track.client_track_id = client_track.id
LEFT JOIN organization ON client_track.organization_id = organization.id
WHERE
    member_track.user_id = :user_id
ORDER BY
    member_track.created_at ASC;
