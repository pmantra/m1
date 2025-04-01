from health.models.health_profile import LIFE_STAGES


def test_life_stage_endpoint(default_user, client, api_helpers):
    result = client.get(
        "/api/v1/users/life_stages", headers=api_helpers.json_headers(default_user)
    )
    assert result.status_code == 200
    assert result.json == LIFE_STAGES
