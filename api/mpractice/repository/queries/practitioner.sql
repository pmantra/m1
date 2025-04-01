-- get_practitioner_by_id
SELECT
    user.id,
    user.first_name,
    user.last_name,
    practitioner_profile.country_code,
    practitioner_profile.dosespot,
    practitioner_profile.messaging_enabled
FROM user
LEFT OUTER JOIN practitioner_profile ON user.id = practitioner_profile.user_id
WHERE user.id = :practitioner_id;

-- get_practitioner_subdivision_codes
SELECT subdivision_code
FROM practitioner_subdivisions
WHERE practitioner_id = :practitioner_id;

-- get_practitioner_verticals
SELECT
    vertical.id,
    vertical.name,
    vertical.can_prescribe,
    vertical.filter_by_state
FROM practitioner_verticals
JOIN vertical ON practitioner_verticals.vertical_id = vertical.id
WHERE practitioner_verticals.user_id = :practitioner_id;

-- get_practitioner_states
SELECT state.abbreviation
FROM practitioner_states
JOIN state ON practitioner_states.state_id = state.id
WHERE practitioner_states.user_id = :practitioner_id;