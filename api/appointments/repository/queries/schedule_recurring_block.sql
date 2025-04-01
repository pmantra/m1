-- The where clause follows looks for intersecting recurring blocks
-- refer to existing_events() on ScheduleEvent that the logic mimics
SELECT
    srb.id,
    srb.starts_at,
    srb.ends_at,
    srb.frequency,
    srb.until,
    srb.latest_date_events_created,
    srb.schedule_id
FROM schedule_recurring_block srb
JOIN schedule s ON srb.schedule_id = s.id
WHERE s.user_id = :user_id
    AND (
    (srb.starts_at <= :starts_at AND srb.until >= :until)
        OR
    (srb.starts_at >= :starts_at AND srb.until >= :until AND srb.starts_at <= :until)
        OR
    (srb.starts_at >= :starts_at AND srb.until <= :until)
        OR
    (srb.starts_at <= :starts_at AND srb.until <= :until AND srb.until >= :starts_at)
    )
GROUP BY 1, 2, 3, 4, 5, 6, 7;

-- get the exact matching user_id, starts_at and until blocks
SELECT
    srb.id,
    srb.starts_at,
    srb.ends_at,
    srb.frequency,
    srb.until,
    srb.latest_date_events_created,
    srb.schedule_id
FROM schedule_recurring_block srb
JOIN schedule s ON srb.schedule_id = s.id
WHERE s.user_id = :user_id
    AND srb.starts_at = :starts_at
    AND srb.ends_at = :ends_at
    AND srb.until = :until
GROUP BY 1, 2, 3, 4, 5, 6, 7;

-- get by id
SELECT
    srb.id,
    srb.starts_at,
    srb.ends_at,
    srb.frequency,
    srb.until,
    srb.latest_date_events_created,
    srb.schedule_id
FROM schedule_recurring_block srb
WHERE id = :schedule_recurring_block_id;

-- get by schedule_event_id
SELECT
    srb.id,
    srb.starts_at,
    srb.ends_at,
    srb.frequency,
    srb.until,
    srb.latest_date_events_created,
    srb.schedule_id
FROM schedule_recurring_block srb
JOIN schedule_event se ON srb.id = se.schedule_recurring_block_id
WHERE se.id = :schedule_event_id;

-- get all week_day_index for the associated recurring block
SELECT
    week_days_index
FROM schedule_recurring_block_weekday_index
WHERE schedule_recurring_block_id = :schedule_recurring_block_id;

-- get all the nested schedule_events associated to the recurring block
SELECT
    id,
    starts_at,
    ends_at,
    state
FROM schedule_event
WHERE schedule_recurring_block_id = :schedule_recurring_block_id
ORDER BY starts_at, ends_at;

-- get all appointments booked during a schedule recurring block period
-- follows same logic as _existing_appointments()
SELECT
    COUNT(a.id)
FROM appointment a
JOIN product p ON a.product_id = p.id
WHERE p.user_id = :user_id
    AND a.scheduled_start >= :starts_at
    AND a.scheduled_start < :ends_at
    AND a.cancelled_at IS NULL
    AND a.scheduled_end > :now
    AND (
        a.member_started_at IS NULL AND
        a.practitioner_started_at IS NULL AND
        a.member_started_at IS NULL AND
        a.practitioner_ended_at IS NULL
    );