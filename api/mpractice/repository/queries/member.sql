-- get_member_by_id
SELECT
    member.id,
    member.first_name,
    member.last_name,
    member.email,
    member.created_at,
    member.health_profile_json,
    member.care_plan_id,
    member.country_code,
    member.dosespot,
    member.phone_number,
    member.subdivision_code,
    member.state_name,
    member.state_abbreviation,
    member_address.count                AS address_count

FROM (
    -- Step 1: get core member info
    SELECT
        user.id,
        user.first_name,
        user.last_name,
        user.email,
        user.created_at,
        member_profile.care_plan_id,
        member_profile.country_code,
        member_profile.dosespot,
        member_profile.phone_number,
        member_profile.subdivision_code,
        # TODO: can we use health_profile.date_of_birth instead of json for dob?
        health_profile.json             AS health_profile_json,
        state.name                      AS state_name,
        state.abbreviation              AS state_abbreviation
    FROM user
        LEFT OUTER JOIN member_profile ON user.id = member_profile.user_id
        LEFT OUTER JOIN health_profile ON user.id = health_profile.user_id
        LEFT OUTER JOIN state on member_profile.state_id = state.id
    WHERE user.id = :member_id
) AS member

LEFT OUTER JOIN (
    -- Step 2: get address of the member.
    -- Address is used for some rx field computation.
    SELECT
        user_id,
        count(*) AS count
    FROM address
    WHERE user_id = :member_id
) AS member_address
ON member.id = member_address.user_id;