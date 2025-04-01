import json

from models.verticals_and_specialties import vertical_group_specialties


def test_get_verticals_specialties(
    factories,
    client,
    api_helpers,
    practitioner_user,
):
    """
    Tests default behavior of /v1/verticals-specialties with no query params
    based on practitioner with Care Advocate vertical.
    """
    user = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(
        user_id=user.id,
    )
    practitioner_user()
    res = client.get(
        "/api/v1/verticals-specialties", headers=api_helpers.json_headers(user=user)
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert res_data["pagination"]
    assert res_data["meta"]
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 1
    assert res_data["pagination"]["total"] == 1
    assert res_data["pagination"]["offset"] == 0


def test_get_verticals_specialties_practitioner_with_non_CA_vertical(
    factories,
    client,
    api_helpers,
    wellness_coach_user,
):
    """
    Tests default behavior of /v1/verticals-specialties with no query params
    based on practitioner with non-Care Advocate vertical.
    """
    user = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(
        user_id=user.id,
    )
    wellness_coach_user()
    res = client.get(
        "/api/v1/verticals-specialties", headers=api_helpers.json_headers(user=user)
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert res_data["pagination"]
    assert res_data["meta"]
    assert len(res_data["data"]["verticals"]) == 1
    assert len(res_data["data"]["specialties"]) == 1
    assert res_data["pagination"]["total"] == 1
    assert res_data["pagination"]["offset"] == 0


def test_get_verticals_specialties_empty(
    factories,
    client,
    api_helpers,
):
    """Tests the empty response from /v1/verticals-specialties"""
    user = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(
        user_id=user.id,
    )
    res = client.get(
        "/api/v1/verticals-specialties", headers=api_helpers.json_headers(user=user)
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert res_data["pagination"]
    assert res_data["meta"]
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 0


def test_get_verticals_specialties_query(
    factories,
    client,
    api_helpers,
    practitioner_user,
):
    """Tests that the `query` param works based on practitioner with Care Advocate vertical."""
    user = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(
        user_id=user.id,
    )
    practitioner_user()
    res = client.get(
        "/api/v1/verticals-specialties?query=care",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 0

    res = client.get(
        "/api/v1/verticals-specialties?query=work",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 1


def test_get_verticals_specialties_query_practitioner_with_non_CA_vertical(
    factories,
    client,
    api_helpers,
    wellness_coach_user,
):
    """Tests that the `query` param works using practitioner with non-Care Advocate vertical."""
    user = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(
        user_id=user.id,
    )
    wellness_coach_user()
    res = client.get(
        "/api/v1/verticals-specialties?query=care",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 0

    res = client.get(
        "/api/v1/verticals-specialties?query=work",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 1


def test_get_verticals_specialties_pagination(
    factories,
    client,
    api_helpers,
):
    """Tests pagination behavior"""
    user = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(
        user_id=user.id,
    )
    verticals = [
        factories.VerticalFactory.create(name=f"vertical-{i:02d}") for i in range(25)
    ]
    factories.PractitionerUserFactory.create(practitioner_profile__verticals=verticals)

    res = client.get(
        "/api/v1/verticals-specialties?limit=7&order_direction=asc",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    # Expected behavior is that `total` is the `max(num_verticals, num_specialties)`
    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 7
    assert len(res_data["data"]["specialties"]) == 1
    assert res_data["pagination"]["total"] == 25
    assert res_data["pagination"]["offset"] == 0
    assert res_data["data"]["verticals"][0]["name"] == "vertical-00"

    res = client.get(
        "/api/v1/verticals-specialties?offset=21&limit=25&order_direction=asc",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    # Since there are fewer specialties than the provided offset, this should not return any specialties
    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 4
    assert len(res_data["data"]["specialties"]) == 0
    assert res_data["pagination"]["total"] == 25
    assert res_data["pagination"]["offset"] == 21
    assert res_data["data"]["verticals"][0]["name"] == "vertical-21"


def test_get_verticals_specialties_common(
    factories,
    client,
    api_helpers,
    db,
):
    """Tests behavior of /v1/verticals-specialties with is_common query param"""
    member_track = factories.MemberTrackFactory.create()
    user = factories.DefaultUserFactory.create(current_member_track=member_track)

    specialties = [
        factories.SpecialtyFactory.create(
            name=f"specialty-{i:02d}", ordering_weight=10 - i
        )
        for i in range(10)
    ]

    vertical_group_track = factories.VerticalGroupTrackFactory(
        track_name=member_track.name
    )
    db.session.execute(
        vertical_group_specialties.insert(),
        [
            {
                "specialty_id": specialties[0].id,
                "vertical_group_id": vertical_group_track.vertical_group_id,
            },
            {
                "specialty_id": specialties[5].id,
                "vertical_group_id": vertical_group_track.vertical_group_id,
            },
        ],
    )
    factories.PractitionerUserFactory.create(
        practitioner_profile__specialties=specialties
    )
    res = client.get(
        "/api/v1/verticals-specialties?is_common=true",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)

    # we don't get fetch keywords, practitioners, need_categories or needs if is_common=true
    assert len(res_data["data"]["keywords"]) == 0
    assert len(res_data["data"]["practitioners"]) == 0
    assert len(res_data["data"]["need_categories"]) == 0
    assert len(res_data["data"]["needs"]) == 0

    assert len(res_data["data"]["verticals"]) == 1
    assert len(res_data["data"]["specialties"]) == 2
    assert res_data["data"]["specialties"][0]["name"] == "specialty-00"
    assert res_data["data"]["specialties"][1]["name"] == "specialty-05"
