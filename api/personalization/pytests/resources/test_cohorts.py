from pytests.factories import EnterpriseUserFactory


def test_get_personalization_cohorts(client, api_helpers):
    user = EnterpriseUserFactory.create()
    response = client.get(
        "/api/v1/-/personalization/cohorts",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 200
    json = api_helpers.load_json(response)
    assert len(json["personalization_cohorts"]) == 4
    assert "sex_at_birth" in json["personalization_cohorts"]
    assert "targeted_for_cycle_tracking" in json["personalization_cohorts"]
    assert "targeted_for_ovulation_tracking" in json["personalization_cohorts"]
    assert "targeted_for_ovulation_medication" in json["personalization_cohorts"]
