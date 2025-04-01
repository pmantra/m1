/*
This script performs 4 operations. The order of operations is important!

1. "Repair" end phases by
    (a) deleting all duplicates except the first created.
    (b) ensuring the end_date matches the track end_date.

2. Delete all duplicated end phases, keeping the maximum.

3. Delete all phases which started after the end phase.

4. "Repair" unfinished (open) phases in tracks which have ended by:
    (a) Pull in the open phases
    (b) Find the next phase if it exists.
    (c) Set the ended_at for the open phase to either the next or track ended_at,
        whichever is not null, in that order.
*/
-- Delete "early" phases, which "existed" before the track ever did.
DELETE FROM maven.member_track_phase
WHERE
    id in (
    SELECT id FROM (
        SELECT
            member_track_phase.id
        from maven.member_track_phase
        INNER JOIN maven.member_track
            ON member_track_phase.member_track_id = member_track.id
        WHERE date(member_track_phase.ended_at) <= date(member_track.created_at)
    ) to_delete
);


-- Delete "duplicate" phases - there should only ever be one for a given time-frame.
DELETE FROM maven.member_track_phase
WHERE id not in (
    SELECT id FROM (
        SELECT min(id)
        FROM maven.member_track_phase mtp
        GROUP BY mtp.member_track_id, date(mtp.started_at), mtp.name
    ) as to_keep
);


-- Delete all duplicate end phases, leaving the first created.
-- Slightly different logic than the above, hence the separate operation.
DELETE FROM maven.member_track_phase
WHERE
    -- Have to nest the query so the query optimizer will run it.
    id not in (
        SELECT id FROM (
            SELECT min(id) as id
            FROM maven.member_track_phase
            WHERE name like '%end'
            GROUP BY member_track_id, name
        ) as to_keep
)
AND name LIKE '%end'
;
-- Set the ended_at for the remaining end phase to the member_track.ended_at.
UPDATE
    maven.member_track_phase,
    maven.member_track
SET
    maven.member_track_phase.ended_at = member_track.ended_at
WHERE
    member_track_phase.name LIKE '%end'
    AND member_track_phase.member_track_id = member_track.id
;


-- Delete all phases which started after the end phase
DELETE FROM maven.member_track_phase
WHERE id in (
    SELECT id FROM (
        SELECT DISTINCT member_track_phase.id
        from maven.member_track_phase
            INNER JOIN (
                SELECT
                      id,
                      member_track_id,
                      name,
                      started_at
               FROM maven.member_track_phase
               WHERE name LIKE '%end'
            ) AS end_phase
                ON end_phase.member_track_id = member_track_phase.member_track_id
        WHERE CAST(member_track_phase.started_at AS date) >
            CAST(end_phase.started_at AS date)
        AND member_track_phase.id != end_phase.id
   ) AS to_delete
);

-- Fix phases in ended tracks with no ended_at filled in.
UPDATE
    maven.member_track_phase,
    (
        SELECT
            -- Get the target ID
            mtp.id,
            -- Get the first non-null value out of the potential end dates.
            COALESCE(next_phase.started_at, mt.ended_at) as corrected_ended_at
        FROM maven.member_track_phase mtp
        INNER JOIN maven.member_track mt ON mtp.member_track_id = mt.id
        -- Fetch the minimum started_at for all phases after the target phase
        LEFT JOIN (
            SELECT
                nmtp.member_track_id,
                min(nmtp.started_at) as started_at
            FROM maven.member_track_phase nmtp
            JOIN maven.member_track_phase cmtp
                ON nmtp.member_track_id = cmtp.member_track_id
                AND cmtp.ended_at IS NULL
            WHERE nmtp.started_at > cmtp.started_at
            GROUP BY nmtp.member_track_id
        ) AS next_phase ON next_phase.member_track_id = mtp.member_track_id
        WHERE mtp.ended_at IS NULL
    ) as open_phase
SET
    member_track_phase.ended_at = open_phase.corrected_ended_at
WHERE member_track_phase.id = open_phase.id;


-- Finally, make sure the "current" phase for all active tracks is not marked as ended.
UPDATE
    maven.member_track_phase,
    (
        SELECT
            mtp.id
        FROM (
            SELECT
                max(id) as id, member_track_id
            FROM maven.member_track_phase
            GROUP BY member_track_id
        ) mtp
        INNER JOIN member_track mt
            ON mtp.member_track_id = mt.id AND mt.ended_at IS NULL

    ) as cmtp
SET ended_at = NULL
WHERE member_track_phase.id = cmtp.id;
