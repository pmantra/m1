import json


def test_get_practitioner_with_vertical(factories, client, api_helpers, db):
    member = factories.MemberFactory()
    ob_vertical = factories.VerticalFactory(name="OB-GYN", filter_by_state=False)
    wc_vertical = factories.VerticalFactory(
        name="Wellness Coach", filter_by_state=False
    )
    factories.PractitionerUserFactory(
        practitioner_profile__verticals=[ob_vertical, wc_vertical]
    )
    res = client.get(
        "/api/v1/dashboard-metadata/practitioner?vertical=Wellness Coach",
        headers=api_helpers.json_headers(member),
        # TODO: Figure out why this request fails without this (in real life too!)
        json={},
    )

    assert json.loads(res.data)["verticals"] == ["OB-GYN", "Wellness Coach"]
    assert json.loads(res.data)["vertical"] == "Wellness Coach"


def test_get_practitioner_no_match(factories, client, api_helpers, db):
    member = factories.MemberFactory()
    ob_vertical = factories.VerticalFactory(name="OB-GYN", filter_by_state=False)
    factories.PractitionerUserFactory(practitioner_profile__verticals=[ob_vertical])
    res = client.get(
        "/api/v1/dashboard-metadata/practitioner?vertical=Wellness Coach",
        headers=api_helpers.json_headers(member),
        # TODO: Figure out why this request fails without this (in real life too!)
        json={},
    )
    assert res.status_code == 200
    assert json.loads(res.data) is None
