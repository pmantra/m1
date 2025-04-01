import datetime
import json
from unittest.mock import patch

import pytest

from models.tracks.track import TrackName
from models.verticals_and_specialties import vertical_group_specialties


def test_get_booking_flow_search(
    factories,
    client,
    api_helpers,
    practitioner_user,
):
    """
    Tests default behavior of /v1/booking_flow/search with no query params

    The tests are based on the vertical, specialty, keywords and name of the
    practitioner_user().
    Vertical: "Care Advocate"
    Specialty: "Back to work coaching"
    Keywords: "coach"
    """
    user = factories.DefaultUserFactory.create()
    practitioner_user()
    factories.MemberProfileFactory.create(
        user_id=user.id,
    )

    res = client.get(
        "/api/v1/booking_flow/search", headers=api_helpers.json_headers(user=user)
    )

    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert res_data["pagination"]
    assert res_data["meta"]
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 1
    assert len(res_data["data"]["keywords"]) == 1
    assert len(res_data["data"]["practitioners"]) == 1
    assert res_data["pagination"]["total"] == 1
    assert res_data["pagination"]["offset"] == 0


def test_get_booking_flow_search_practitioner_with_non_CA_vertical(
    factories,
    client,
    api_helpers,
    wellness_coach_user,
):
    """
    Tests default behavior of /v1/booking_flow/search with no query params

    The tests are based on the vertical, specialty, keywords and name of the
    wellness_coach_user().
    Vertical: "Wellness Coach"
    Specialty: "Back to work coaching"
    Keywords: "coach"
    """
    user = factories.DefaultUserFactory.create()
    wellness_coach_user()
    factories.MemberProfileFactory.create(
        user_id=user.id,
    )

    res = client.get(
        "/api/v1/booking_flow/search", headers=api_helpers.json_headers(user=user)
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert res_data["pagination"]
    assert res_data["meta"]
    assert len(res_data["data"]["verticals"]) == 1
    assert len(res_data["data"]["specialties"]) == 1
    assert len(res_data["data"]["keywords"]) == 1
    assert len(res_data["data"]["practitioners"]) == 1
    assert res_data["pagination"]["total"] == 1
    assert res_data["pagination"]["offset"] == 0


def test_get_booking_flow_search_empty(
    factories,
    client,
    api_helpers,
):
    """Tests the empty response from /v1/booking_flow/search"""
    user = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(
        user_id=user.id,
    )
    res = client.get(
        "/api/v1/booking_flow/search", headers=api_helpers.json_headers(user=user)
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert res_data["pagination"]
    assert res_data["meta"]
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 0
    assert len(res_data["data"]["keywords"]) == 0
    assert len(res_data["data"]["practitioners"]) == 0


@pytest.mark.skip(reason="flaky test - temporarily ignoring this")
def test_get_booking_flow_search_query(
    factories,
    client,
    api_helpers,
    practitioner_user,
):
    """Tests that the `query` param works

    The tests are based on the vertical, specialty, keywords and name of the
    practitioner_user().
    Vertical: "Care Advocate"
    Specialty: "Back to work coaching"
    Keywords: "coach"
    """
    user = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(
        user_id=user.id,
    )
    practitioner = practitioner_user()
    res = client.get(
        "/api/v1/booking_flow/search?query=care",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 0
    assert len(res_data["data"]["keywords"]) == 0
    assert len(res_data["data"]["practitioners"]) == 0
    res = client.get(
        "/api/v1/booking_flow/search?query=work",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 1
    assert len(res_data["data"]["keywords"]) == 0
    assert len(res_data["data"]["practitioners"]) == 0
    res = client.get(
        "/api/v1/booking_flow/search?query=coach",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 1
    assert len(res_data["data"]["keywords"]) == 1
    assert len(res_data["data"]["practitioners"]) == 0
    res = client.get(
        f"/api/v1/booking_flow/search?query={practitioner.first_name[1:-1]}",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 0
    assert len(res_data["data"]["keywords"]) == 0
    assert len(res_data["data"]["practitioners"]) == 0
    res = client.get(
        f"/api/v1/booking_flow/search?query={practitioner.last_name[1:-1]}",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 0
    assert len(res_data["data"]["keywords"]) == 0
    assert len(res_data["data"]["practitioners"]) == 0
    res = client.get(
        f"/api/v1/booking_flow/search?query={practitioner.first_name}%20{practitioner.last_name}",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 0
    assert len(res_data["data"]["keywords"]) == 0
    assert len(res_data["data"]["practitioners"]) == 0
    res = client.get(
        f"/api/v1/booking_flow/search?query={practitioner.first_name}{practitioner.last_name}",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 0
    assert len(res_data["data"]["keywords"]) == 0
    assert len(res_data["data"]["practitioners"]) == 0
    res = client.get(
        f"/api/v1/booking_flow/search?query={practitioner.last_name}%20{practitioner.first_name}",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 0
    assert len(res_data["data"]["keywords"]) == 0
    assert len(res_data["data"]["practitioners"]) == 0
    res = client.get(
        f"/api/v1/booking_flow/search?query={practitioner.last_name}{practitioner.first_name}",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 0
    assert len(res_data["data"]["keywords"]) == 0
    assert len(res_data["data"]["practitioners"]) == 0


@pytest.mark.skip(reason="flaky test - temporarily ignoring this")
def test_get_booking_flow_search_query_practitioner_with_non_CA_vertical(
    factories,
    client,
    api_helpers,
    wellness_coach_user,
):
    """
    Tests that the `query` param works

    The tests are based on the vertical, specialty, keywords and name of the
    wellness_coach_user().
    Vertical: "Wellness Coach"
    Specialty: "Back to work coaching"
    Keywords: "coach"
    """
    user = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(
        user_id=user.id,
    )
    practitioner = wellness_coach_user()
    res = client.get(
        "/api/v1/booking_flow/search?query=wellness",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 1
    assert len(res_data["data"]["specialties"]) == 0
    assert len(res_data["data"]["keywords"]) == 0
    assert len(res_data["data"]["practitioners"]) == 0
    res = client.get(
        "/api/v1/booking_flow/search?query=work",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 1
    assert len(res_data["data"]["keywords"]) == 0
    assert len(res_data["data"]["practitioners"]) == 0
    res = client.get(
        "/api/v1/booking_flow/search?query=coach",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 1
    assert len(res_data["data"]["specialties"]) == 1
    assert len(res_data["data"]["keywords"]) == 1
    assert len(res_data["data"]["practitioners"]) == 0
    res = client.get(
        f"/api/v1/booking_flow/search?query={practitioner.first_name[1:-1]}",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 0
    assert len(res_data["data"]["keywords"]) == 0
    assert len(res_data["data"]["practitioners"]) == 1
    res = client.get(
        f"/api/v1/booking_flow/search?query={practitioner.last_name[1:-1]}",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 0
    assert len(res_data["data"]["keywords"]) == 0
    assert len(res_data["data"]["practitioners"]) == 1
    res = client.get(
        f"/api/v1/booking_flow/search?query={practitioner.first_name}%20{practitioner.last_name}",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 0
    assert len(res_data["data"]["keywords"]) == 0
    assert len(res_data["data"]["practitioners"]) == 1
    res = client.get(
        f"/api/v1/booking_flow/search?query={practitioner.first_name}{practitioner.last_name}",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 0
    assert len(res_data["data"]["keywords"]) == 0
    assert len(res_data["data"]["practitioners"]) == 1
    res = client.get(
        f"/api/v1/booking_flow/search?query={practitioner.last_name}%20{practitioner.first_name}",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 0
    assert len(res_data["data"]["keywords"]) == 0
    assert len(res_data["data"]["practitioners"]) == 1
    res = client.get(
        f"/api/v1/booking_flow/search?query={practitioner.last_name}{practitioner.first_name}",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 0
    assert len(res_data["data"]["keywords"]) == 0
    assert len(res_data["data"]["practitioners"]) == 1


def test_get_booking_flow_search_query__no_deleted_verticals(
    factories,
    client,
    api_helpers,
):
    """
    Tests that soft deleted verticals don't show up in the search
    """
    user = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(
        user_id=user.id,
    )
    verticals = [
        factories.VerticalFactory.create(
            name="test_vert",
            deleted_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=5),
        )
    ]
    factories.PractitionerUserFactory.create(practitioner_profile__verticals=verticals)

    query = "test_vert"
    res = client.get(
        f"/api/v1/booking_flow/search?query={query}",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 0
    assert len(res_data["data"]["specialties"]) == 0
    assert len(res_data["data"]["keywords"]) == 0
    assert len(res_data["data"]["practitioners"]) == 0


def test_get_booking_flow_search_pagination(
    factories,
    client,
    api_helpers,
):
    """Tests pagination behavior"""
    user = factories.DefaultUserFactory.create()
    verticals = [
        factories.VerticalFactory.create(name=f"vertical-{i:02d}") for i in range(25)
    ]
    factories.PractitionerUserFactory.create(practitioner_profile__verticals=verticals)
    factories.MemberProfileFactory.create(
        user_id=user.id,
    )
    res = client.get(
        "/api/v1/booking_flow/search?limit=7&order_direction=asc",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    # Expected behavior is that `total` is the `max(num_verticals, num_specialties, num_keywords)`
    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 7
    assert len(res_data["data"]["specialties"]) == 1
    assert len(res_data["data"]["keywords"]) == 1
    assert res_data["pagination"]["total"] == 25
    assert res_data["pagination"]["offset"] == 0
    assert res_data["data"]["verticals"][0]["name"] == "vertical-00"

    res = client.get(
        "/api/v1/booking_flow/search?offset=21&limit=25&order_direction=asc",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 200

    # Since there are fewer specialties than the provided offset, this should not return any specialties
    res_data = json.loads(res.data)
    assert len(res_data["data"]["verticals"]) == 4
    assert len(res_data["data"]["specialties"]) == 0
    assert len(res_data["data"]["keywords"]) == 0
    assert len(res_data["data"]["practitioners"]) == 0
    assert res_data["pagination"]["total"] == 25
    assert res_data["pagination"]["offset"] == 21
    assert res_data["data"]["verticals"][0]["name"] == "vertical-21"


@pytest.mark.parametrize(
    argnames="search_api_enabled",
    argvalues=[True, False],
    ids=[
        "search_api_enabled",
        "search_api_disabled",
    ],
)
def test_get_booking_flow_search_common(
    search_api_enabled,
    factories,
    client,
    api_helpers,
    db,
):
    """Tests behavior of /v1/booking_flow/search with is_common param"""
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

    with patch(
        "appointments.resources.booking.feature_flags.bool_variation",
        side_effect=[True, search_api_enabled, False, False, False],
    ):
        res = client.get(
            "/api/v1/booking_flow/search?is_common=true",
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


def test_get_booking_flow_search_query_and_is_common_fail(
    factories,
    client,
    api_helpers,
):
    """Tests that sending the is_common flag with a query value to the
    booking_flow search endpoint will cause a 400 HTTP error
    to be returned.
    """
    user = factories.DefaultUserFactory.create()
    res = client.get(
        "/api/v1/booking_flow/search?is_common=true&query=fail",
        headers=api_helpers.json_headers(user=user),
    )
    assert res.status_code == 400


@pytest.fixture
def assert_need_category_need_search_response(client, api_helpers):
    def _assert_need_category_need_search_response(
        expected_data, response_name, user, search_query=""
    ):
        search_url = f"/api/v1/booking_flow/search?query={search_query}"

        res = client.get(
            search_url,
            headers=api_helpers.json_headers(user=user),
        )
        res_data = json.loads(res.data)
        assert res_data.get("pagination", {}).get("total", 0) == len(expected_data)

        retrieved_items = res_data.get("data", {}).get(response_name, [])
        for item_dict in expected_data:
            assert item_dict in retrieved_items

    return _assert_need_category_need_search_response


def test_get_booking_flow_search_queries_need_table(
    factories,
    assert_need_category_need_search_response,
):
    """Tests that every query is evaluated against the Need table"""
    user = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(
        user_id=user.id,
    )
    track = factories.MemberTrackFactory.create(user=user, name=TrackName.PREGNANCY)

    common_query_needs = [
        factories.NeedFactory.create(name="first name with common terms"),
        factories.NeedFactory.create(name="second name with common terms"),
    ]

    all_needs = [*common_query_needs, factories.NeedFactory.create(name="plain text")]

    # Add track to all needs
    for n in all_needs:
        factories.NeedTrackFactory.create(
            track_name=track.name,
            need_id=n.id,
        )

    # Search for all items
    expected_data = [
        {"id": need.id, "name": need.name, "description": need.description}
        for need in all_needs
    ]
    assert_need_category_need_search_response(
        expected_data=expected_data,
        response_name="needs",
        user=user,
    )

    # Search for items matching search_query
    expected_data = [
        {"id": need.id, "name": need.name, "description": need.description}
        for need in common_query_needs
    ]
    assert_need_category_need_search_response(
        expected_data=expected_data,
        response_name="needs",
        user=user,
        search_query="common",
    )


def test_get_booking_flow_search_need_query_filters_by_track(
    factories,
    assert_need_category_need_search_response,
):
    """Tests that querying by need filters by a member's tracks"""
    user = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(
        user_id=user.id,
    )
    track = factories.MemberTrackFactory.create(user=user, name=TrackName.PREGNANCY)

    common_query_needs = [
        factories.NeedFactory.create(name="first name with common terms"),
        factories.NeedFactory.create(name="second name with common terms"),
    ]
    matching_needs = [
        factories.NeedFactory.create(name="matching_0"),
        factories.NeedFactory.create(name="matching_1"),
    ]
    all_needs = [
        *common_query_needs,
        factories.NeedFactory.create(name="plain text_0"),
        factories.NeedFactory.create(name="plain text_1"),
    ]
    # Add a non-matching track to all needs
    for n in all_needs:
        factories.NeedTrackFactory.create(
            track_name=TrackName.ADOPTION,
            need_id=n.id,
        )
    # Add an additional,matching track to matching needs
    factories.NeedTrackFactory.create(
        track_name=track.name,
        need_id=matching_needs[0].id,
    )
    factories.NeedTrackFactory.create(
        track_name=track.name,
        need_id=matching_needs[1].id,
    )

    # Search for all items
    expected_data = [
        {"id": need.id, "name": need.name, "description": need.description}
        for need in matching_needs
    ]
    assert_need_category_need_search_response(
        expected_data=expected_data,
        response_name="needs",
        user=user,
    )


def test_get_booking_flow_search_marketplace_user(
    factories, assert_need_category_need_search_response
):
    """Tests that marketplace members get needs from the General Wellness track"""
    GENERAL_WELLNESS_TRACK_NAME = "general_wellness"

    member = factories.MemberFactory.create()
    category = factories.NeedCategoryFactory.create()
    category.name = "general wellness category"
    factories.NeedCategoryTrackFactory.create(
        track_name="general_wellness",
        need_category_id=category.id,
    )

    need = factories.NeedFactory.create(name="matching_0", categories=[category])
    factories.NeedTrackFactory.create(
        track_name=GENERAL_WELLNESS_TRACK_NAME,
        need_id=need.id,
    )

    # Search for all items
    expected_data = [
        {"id": need.id, "name": need.name, "description": need.description}
    ]
    assert_need_category_need_search_response(
        expected_data=expected_data,
        response_name="needs",
        user=member,
    )


def test_get_booking_flow_search_multitrack_user(factories, client, api_helpers):
    """
    Tests that multitrack users get the union of their need categories and needs with some designated
    ones excluded.
    """
    user = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(
        user_id=user.id,
    )
    factories.MemberTrackFactory.create(user=user, name=TrackName.GENERAL_WELLNESS)
    factories.MemberTrackFactory.create(
        user=user,
        name=TrackName.PARENTING_AND_PEDIATRICS,
    )

    gw_category = factories.NeedCategoryFactory.create(name="general wellness category")
    factories.NeedCategoryTrackFactory.create(
        track_name=TrackName.GENERAL_WELLNESS,
        need_category_id=gw_category.id,
    )
    gw_need = factories.NeedFactory.create(name="gw need", categories=[gw_category])
    factories.NeedTrackFactory.create(
        track_name=TrackName.GENERAL_WELLNESS, need_id=gw_need.id
    )

    pnp_category = factories.NeedCategoryFactory.create(name="pnp category")
    factories.NeedCategoryTrackFactory.create(
        track_name=TrackName.PARENTING_AND_PEDIATRICS,
        need_category_id=pnp_category.id,
    )
    pnp_need = factories.NeedFactory.create(name="pnp need", categories=[pnp_category])
    factories.NeedTrackFactory.create(
        track_name=TrackName.PARENTING_AND_PEDIATRICS, need_id=pnp_need.id
    )

    pnp_category_non_multi = factories.NeedCategoryFactory.create(
        name="pnp category non multi", hide_from_multitrack=True
    )
    factories.NeedCategoryTrackFactory.create(
        track_name=TrackName.PARENTING_AND_PEDIATRICS,
        need_category_id=pnp_category_non_multi.id,
    )
    pnp_need_non_multi = factories.NeedFactory.create(
        name="pnp need non multi",
        categories=[pnp_category_non_multi],
        hide_from_multitrack=True,
    )
    factories.NeedTrackFactory.create(
        track_name=TrackName.PARENTING_AND_PEDIATRICS, need_id=pnp_need_non_multi.id
    )

    search_url = "/api/v1/booking_flow/search?query="

    res = client.get(
        search_url,
        headers=api_helpers.json_headers(user=user),
    )
    res_data = json.loads(res.data)

    returned_nc_names = [nc["name"] for nc in res_data["data"]["need_categories"]]
    assert gw_category.name in returned_nc_names
    assert pnp_category.name in returned_nc_names
    assert pnp_category_non_multi.name not in returned_nc_names

    returned_need_names = [n["name"] for n in res_data["data"]["needs"]]
    assert gw_need.name in returned_need_names
    assert pnp_need.name in returned_need_names
    assert pnp_need_non_multi.name not in returned_need_names


def test_get_booking_flow_search_queries_need_category_table(
    factories,
    assert_need_category_need_search_response,
):
    """Tests that every query is evaluated against the NeedCategory table"""
    user = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(
        user_id=user.id,
    )
    track = factories.MemberTrackFactory.create(user=user, name=TrackName.PREGNANCY)

    common_query_categories = [
        factories.NeedCategoryFactory.create(name="first name with common terms"),
        factories.NeedCategoryFactory.create(name="second name with common terms"),
    ]
    all_categories = [
        *common_query_categories,
        factories.NeedCategoryFactory.create(name="plain text"),
    ]
    # Add track to all categories
    for c in all_categories:
        factories.NeedCategoryTrackFactory.create(
            track_name=track.name,
            need_category_id=c.id,
        )

    # Search for all items
    expected_data = [
        {
            "id": category.id,
            "name": category.name,
        }
        for category in all_categories
    ]
    assert_need_category_need_search_response(
        expected_data=expected_data,
        response_name="need_categories",
        user=user,
    )

    # Search for items matching search_query
    expected_data = [
        {
            "id": category.id,
            "name": category.name,
        }
        for category in common_query_categories
    ]
    assert_need_category_need_search_response(
        expected_data=expected_data,
        response_name="need_categories",
        user=user,
        search_query="common",
    )


def test_get_booking_flow_search_category_query_filters_by_track(
    factories,
    assert_need_category_need_search_response,
):
    """Tests that every query is evaluated against the NeedCategory table"""
    user = factories.DefaultUserFactory.create()
    factories.MemberProfileFactory.create(
        user_id=user.id,
    )
    track = factories.MemberTrackFactory.create(user=user, name=TrackName.PREGNANCY)

    common_query_categories = [
        factories.NeedCategoryFactory.create(name="first name with common terms"),
        factories.NeedCategoryFactory.create(name="second name with common terms"),
    ]
    matching_categories = [
        factories.NeedCategoryFactory.create(name="matching_0"),
        factories.NeedCategoryFactory.create(name="matching_1"),
    ]
    all_categories = [
        *common_query_categories,
        factories.NeedCategoryFactory.create(name="plain text_0"),
        factories.NeedCategoryFactory.create(name="plain text_1"),
    ]
    # Add a non-matching track to all categories
    for c in all_categories:
        factories.NeedCategoryTrackFactory.create(
            track_name=TrackName.ADOPTION,
            need_category_id=c.id,
        )
    # Add an additional, matching track to matching categories
    factories.NeedCategoryTrackFactory.create(
        track_name=track.name,
        need_category_id=matching_categories[0].id,
    )
    factories.NeedCategoryTrackFactory.create(
        track_name=track.name,
        need_category_id=matching_categories[1].id,
    )

    expected_data = [
        {
            "id": category.id,
            "name": category.name,
        }
        for category in matching_categories
    ]
    assert_need_category_need_search_response(
        expected_data=expected_data,
        response_name="need_categories",
        user=user,
    )


def test_get_booking_flow_common_search_does_strips_whitespace(
    factories,
    client,
    api_helpers,
):
    """Tests that a search query bookended with whitespace returns results when flag is on"""
    member = factories.MemberFactory.create()
    vertical = factories.VerticalFactory.create(name="temp-vertical")
    search_query = "     temp-vertical    "

    res = client.get(
        f"/api/v1/booking_flow/search?query={search_query}",
        headers=api_helpers.json_headers(user=member),
    )

    res_data = json.loads(res.data)
    payload = res_data.get("data")
    assert res_data.get("pagination", {}).get("total", 10) == 1
    assert payload is not None

    retrieved_vertical = payload.get("verticals", [])[0]
    assert retrieved_vertical.get("id") == vertical.id
    assert retrieved_vertical.get("name") == vertical.name
    assert retrieved_vertical.get("description") == vertical.description


def test_get_booking_flow_common_search_returns_verticals_alphabetically(
    factories,
    client,
    api_helpers,
):
    """Tests that a common search returns verticals in alphabetical order when flag is on"""
    member = factories.MemberFactory.create()

    verticals = [
        factories.VerticalFactory.create(name=f"vertical-{i}") for i in range(5)
    ]

    res = client.get(
        "/api/v1/booking_flow/search?is_common=true",
        headers=api_helpers.json_headers(user=member),
    )

    res_data = json.loads(res.data)
    assert res_data.get("pagination", {}).get("total", 0) == len(verticals)

    payload = res_data.get("data")
    assert payload is not None

    retrieved_verticals = payload.get("verticals", [])
    for i, retrieved_vertical in enumerate(retrieved_verticals):
        expected_vertical = verticals[i]
        assert retrieved_vertical.get("id") == expected_vertical.id
        assert retrieved_vertical.get("name") == expected_vertical.name
        assert retrieved_vertical.get("description") == expected_vertical.description


def test_get_booking_flow_search_queries_for_needs_linked_to_need_categories_in_correct_order(
    factories,
    client,
    api_helpers,
):
    """Tests that every query is evaluated against the NeedCategory table"""
    member = factories.MemberFactory.create()
    track = factories.MemberTrackFactory.create(user=member, name=TrackName.PREGNANCY)

    common_query_categories = [
        factories.NeedCategoryFactory.create(name="first name with common terms"),
        factories.NeedCategoryFactory.create(
            name="second name with common terms", display_order=2
        ),
        factories.NeedCategoryFactory.create(
            name="third name with common terms", display_order=1
        ),
    ]
    category_with_non_common_needs = common_query_categories[0]

    common_query_needs = [
        factories.NeedFactory.create(
            name="first name with common terms", display_order=3
        ),
        factories.NeedFactory.create(
            name="second name with common terms", display_order=1
        ),
    ]

    non_common_needs = [
        factories.NeedFactory.create(
            name="plain text", categories=[category_with_non_common_needs]
        ),
        factories.NeedFactory.create(
            name="different plain text",
            categories=[category_with_non_common_needs],
            display_order=4,
        ),
        factories.NeedFactory.create(
            name="more plain text",
            categories=[category_with_non_common_needs],
            display_order=2,
        ),
    ]

    all_needs = [
        common_query_needs[1],
        non_common_needs[2],
        common_query_needs[0],
        non_common_needs[1],
        non_common_needs[0],
    ]

    # Add tracks
    for c in common_query_categories:
        factories.NeedCategoryTrackFactory.create(
            track_name=track.name,
            need_category_id=c.id,
        )
    for n in all_needs:
        factories.NeedTrackFactory.create(
            track_name=track.name,
            need_id=n.id,
        )

    expected_needs_data = [
        {
            "id": need.id,
            "name": need.name,
            "description": need.description,
        }
        for need in all_needs
    ]

    common_query_categories.reverse()
    expected_need_categories_data = [
        {
            "id": category.id,
            "name": category.name,
        }
        for category in common_query_categories
    ]

    search_url = "/api/v1/booking_flow/search?query=common"
    res = client.get(
        search_url,
        headers=api_helpers.json_headers(user=member),
    )

    res_data = json.loads(res.data)
    assert res_data.get("pagination", {}).get("total", 0) == len(expected_needs_data)

    retrieved_categories = res_data["data"]["need_categories"]
    assert len(retrieved_categories) == len(expected_need_categories_data)

    assert retrieved_categories == expected_need_categories_data

    retrieved_needs = res_data["data"]["needs"]
    assert retrieved_needs == expected_needs_data


@pytest.mark.parametrize("locale", [None, "en", "es", "fr", "fr_CA"])
def test_get_booking_flow_search__with_locale(
    locale,
    factories,
    client,
    api_helpers,
    practitioner_user,
    enterprise_user_with_tracks_and_categories,
):
    factories.SpecialtyFactory.create()
    factories.VerticalFactory.create()
    factories.PractitionerUserFactory.create()

    track_names = [TrackName.PREGNANCY]
    member, tracks, categories = enterprise_user_with_tracks_and_categories(track_names)
    need = factories.NeedFactory.create(
        name="need name",
        categories=[categories[0]],
    )
    factories.NeedTrackFactory.create(
        track_name=track_names[0],
        need_id=need.id,
    )
    need_2 = factories.NeedFactory.create(
        name="need name 2",
        categories=[categories[0]],
    )
    factories.NeedTrackFactory.create(
        track_name=track_names[0],
        need_id=need_2.id,
    )

    expected_translation = "translated text"
    with patch(
        "appointments.resources.booking.BookingFlowSearchResource._get_feature_flags",
        return_value=(True, False, False, True),
    ), patch(
        "appointments.resources.booking.TranslateDBFields._get_translated_string_from_slug",
    ) as translation_mock:
        translation_mock.return_value = expected_translation
        res = client.get(
            "/api/v1/booking_flow/search",
            headers=api_helpers.with_locale_header(
                api_helpers.standard_headers(member), locale=locale
            ),
        )

    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert res_data["pagination"]
    assert res_data["meta"]
    assert len(res_data["data"]["verticals"]) == 1
    assert len(res_data["data"]["specialties"]) == 1
    assert len(res_data["data"]["practitioners"]) == 2
    assert len(res_data["data"]["need_categories"]) == 1
    assert len(res_data["data"]["needs"]) == 2
    assert res_data["pagination"]["total"] == 2
    assert res_data["pagination"]["offset"] == 0

    # 1 call for specialties, 1 for verticals, and 4 for needs
    assert translation_mock.call_count == 6
    assert res_data["data"]["specialties"][0]["name"] == expected_translation
    assert res_data["data"]["verticals"][0]["name"] == expected_translation
    assert res_data["data"]["needs"][0]["name"] == expected_translation
    assert res_data["data"]["needs"][0]["description"] == expected_translation
    assert res_data["data"]["needs"][1]["name"] == expected_translation
    assert res_data["data"]["needs"][1]["description"] == expected_translation


def test_get_booking_flow_search__search_api_enabled(
    factories,
    client,
    api_helpers,
    search_api_8_hits,
    practitioner_with_availability,
):
    member_track = factories.MemberTrackFactory.create(id=42, name=TrackName.PREGNANCY)
    nc = factories.NeedCategoryFactory.create(
        id=search_api_8_hits[3]["_source"]["id"],
        name=search_api_8_hits[3]["_source"]["name"],
    )
    factories.NeedCategoryTrackFactory.create(
        track_name=TrackName.PREGNANCY,
        need_category_id=nc.id,
    )
    search_api_8_hits[3]["_source"]["id"] = nc.id

    need = factories.NeedFactory.create()
    factories.NeedTrackFactory.create(
        track_name=TrackName.PREGNANCY,
        need_id=need.id,
    )
    search_api_8_hits[2]["_source"]["id"] = need.id

    user = factories.DefaultUserFactory.create(current_member_track=member_track)
    factories.MemberProfileFactory.create(user_id=user.id)

    expected_provider, _ = practitioner_with_availability
    # Change the expected practitioner from our mocked search api results
    # to be in line with the expected one from the DB
    search_api_8_hits[0]["_source"]["user_id"] = expected_provider.id

    # This provider should get filtered because they do not have availability
    filtered_provider = factories.PractitionerUserFactory.create(
        practitioner_profile__next_availability=None,
        practitioner_profile__show_when_unavailable=False,
    )
    search_api_8_hits[1]["_source"]["user_id"] = filtered_provider.id

    with patch(
        "appointments.resources.booking.feature_flags.bool_variation", return_value=True
    ), patch(
        "appointments.utils.booking_flow_search._query_search_api"
    ) as mock_response:
        mock_response.return_value = search_api_8_hits
        res = client.get(
            "/api/v1/booking_flow/search?query=food",
            headers=api_helpers.json_headers(user=user),
        )

    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert res_data["pagination"]
    assert res_data["meta"]
    assert len(res_data["data"]["specialties"]) == 2
    assert len(res_data["data"]["keywords"]) == 0
    assert len(res_data["data"]["verticals"]) == 1
    assert len(res_data["data"]["practitioners"]) == 1
    assert len(res_data["data"]["need_categories"]) == 0
    assert len(res_data["data"]["needs"]) == 1
    assert res_data["data"]["needs"][0]["id"] == need.id
    assert res_data["pagination"]["total"] == 2
    assert res_data["pagination"]["offset"] == 0


def test_get_booking_flow_search__search_api_enabled__fallback(
    factories,
    client,
    api_helpers,
    enterprise_user,
    practitioner_with_availability,
):
    """
    Tests that the search api will fall back to the older flow when there is an error
    """
    with patch(
        "appointments.resources.booking.feature_flags.bool_variation", return_value=True
    ), patch(
        "appointments.resources.booking._get_need_categories"
    ) as mock_get_need_categories, patch(
        "appointments.utils.booking_flow_search.requests.post"
    ) as mock_response:
        mock_get_need_categories.return_value = ([], 0)
        mock_response.side_effect = Exception("error")
        res = client.get(
            "/api/v1/booking_flow/search?query=food",
            headers=api_helpers.json_headers(user=enterprise_user),
        )

        assert res.status_code == 200
        mock_get_need_categories.assert_called_once()


@pytest.mark.parametrize("locale", [None, "en", "es", "fr", "fr_CA"])
def test_get_booking_flow_search__with_search_api__with_locale(
    locale,
    factories,
    client,
    api_helpers,
    practitioner_with_availability,
    search_api_8_hits,
):
    member_track = factories.MemberTrackFactory.create(id=42, name=TrackName.PREGNANCY)
    nc = factories.NeedCategoryFactory.create(
        id=search_api_8_hits[3]["_source"]["id"],
        name=search_api_8_hits[3]["_source"]["name"],
    )
    factories.NeedCategoryTrackFactory.create(
        track_name=TrackName.PREGNANCY,
        need_category_id=nc.id,
    )
    search_api_8_hits[3]["_source"]["id"] = nc.id

    need = factories.NeedFactory.create()
    factories.NeedTrackFactory.create(
        track_name=TrackName.PREGNANCY,
        need_id=need.id,
    )
    search_api_8_hits[2]["_source"]["id"] = need.id

    user = factories.DefaultUserFactory.create(current_member_track=member_track)
    factories.MemberProfileFactory.create(user_id=user.id)

    expected_provider, _ = practitioner_with_availability
    # Change the expected practitioner from our mocked search api results
    # to be in line with the expected one from the DB
    search_api_8_hits[0]["_source"]["user_id"] = expected_provider.id

    # This provider should get filtered because they do not have availability
    filtered_provider = factories.PractitionerUserFactory.create(
        practitioner_profile__next_availability=None,
        practitioner_profile__show_when_unavailable=False,
    )
    search_api_8_hits[1]["_source"]["user_id"] = filtered_provider.id

    expected_translation = "translated text"
    with patch(
        "appointments.resources.booking.BookingFlowSearchResource._get_feature_flags",
        return_value=(True, True, False, True),
    ), patch(
        "appointments.resources.booking.TranslateDBFields._get_translated_string_from_slug",
    ) as translation_mock, patch(
        "appointments.utils.booking_flow_search._query_search_api"
    ) as mock_response:
        translation_mock.return_value = expected_translation
        mock_response.return_value = search_api_8_hits
        res = client.get(
            "/api/v1/booking_flow/search?query=food",
            headers=api_helpers.with_locale_header(
                api_helpers.standard_headers(user), locale=locale
            ),
        )

    assert res.status_code == 200

    res_data = json.loads(res.data)
    assert res_data["pagination"]
    assert res_data["meta"]
    assert len(res_data["data"]["specialties"]) == 2
    assert len(res_data["data"]["keywords"]) == 0
    assert len(res_data["data"]["verticals"]) == 1
    assert len(res_data["data"]["practitioners"]) == 1
    assert len(res_data["data"]["needs"]) == 1

    # 2 calls for specialties, 1 for verticals, and 2 for needs
    assert translation_mock.call_count == 6
    assert res_data["data"]["specialties"][0]["name"] == expected_translation
    assert res_data["data"]["specialties"][1]["name"] == expected_translation
    assert res_data["data"]["verticals"][0]["name"] == expected_translation
    assert res_data["data"]["needs"][0]["name"] == expected_translation
    assert res_data["data"]["needs"][0]["description"] == expected_translation
