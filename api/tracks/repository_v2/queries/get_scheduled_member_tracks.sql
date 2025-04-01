-- get_scheduled_member_tracks
SELECT
    member_track.id,
    member_track.name,
    member_track.anchor_date,
    member_track.start_date,
    client_track.length_in_days
FROM member_track 
LEFT OUTER JOIN client_track ON member_track.client_track_id = client_track.id
WHERE user_id = :user_id
AND member_track.ended_at IS NULL
AND member_track.activated_at IS NULL;
