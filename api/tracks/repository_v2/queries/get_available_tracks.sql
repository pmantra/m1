SELECT 
    client_track.id,
    client_track.track as name,
    client_track.active
FROM 
    client_track
LEFT OUTER JOIN 
    member_track 
ON 
    client_track.id = member_track.client_track_id
    AND member_track.user_id = :user_id
    AND member_track.ended_at IS NULL 
    AND member_track.activated_at IS NOT NULL
WHERE
    client_track.organization_id IN (:organization_ids)
    AND client_track.active = TRUE
    AND COALESCE(client_track.launch_date, CURRENT_DATE) <= CURRENT_DATE
    AND member_track.id IS NULL
ORDER BY client_track.launch_date DESC;