import json
from unittest.mock import patch

import pytest

from appointments.utils.booking_flow_search import (
    _create_search_query,
    search_api_booking_flow,
)
from pytests.freezegun import freeze_time

FREEZE_TIME_STR = "2024-03-01T12:00:00"


@pytest.fixture()
def mock_vertical_hits():
    return [
        # Regular vertical
        {
            "_index": "provider_search_index_vertical",
            "_id": "10012",
            "_score": 1.4735041,
            "_source": {
                "promote_messaging": 1,
                "description": "Healthy eating, weight management",
                "pluralized_display_name": "Nutrition Coaches",
                "long_description": "Nutrition Coaches are here to help you understand how diet plays a role in your overall health and well-being, and offer recommendations for foods and small lifestyle changes that can help you feel your best.",
                "model_id": ".elser_model_2_linux-x86_64",
                "display_name": "Nutrition Coach",
                "can_prescribe": 0,
                "deleted_at": None,
                "products": '[{"minutes": 20, "price": 25.0}, {"minutes": 30, "price": 35.0}]',
                "name": "Nutritionist",
                "promo_end": None,
                "filter_by_state": 0,
                "id": 10012,
                "promo_start": None,
            },
        },
        # Deleted vertical
        {
            "_index": "provider_search_index_vertical",
            "_id": "10043",
            "_score": 1.4735041,
            "_source": {
                "promote_messaging": 1,
                "description": "Healthy eating, weight management",
                "pluralized_display_name": "Nutrition Coaches",
                "long_description": "Nutrition Coaches are here to help you understand how diet plays a role in your overall health and well-being, and offer recommendations for foods and small lifestyle changes that can help you feel your best.",
                "model_id": ".elser_model_2_linux-x86_64",
                "display_name": "Nutrition Coach",
                "can_prescribe": 0,
                "deleted_at": "2024-01-05T19:03:46",
                "products": '[{"price": 26.83, "minutes": 20}]',
                "name": "Deleted at 2024-01-05 19:03:46.301212 -- Nutrition Coach",
                "promo_end": None,
                "filter_by_state": 0,
                "id": 10043,
                "promo_start": None,
            },
        },
        # CX vertical
        {
            "_index": "provider_search_index_vertical",
            "_id": "10044",
            "_score": 1.4735041,
            "_source": {
                "promote_messaging": 1,
                "description": "Test desc",
                "pluralized_display_name": "Care Advocates",
                "long_description": "Care Advocate test desc",
                "model_id": ".elser_model_2_linux-x86_64",
                "display_name": "Care Advocate",
                "can_prescribe": 0,
                "deleted_at": None,
                "products": '[{"minutes": 20, "price": 25.0}, {"minutes": 30, "price": 35.0}]',
                "name": "Care Advocate",
                "promo_end": None,
                "filter_by_state": 0,
                "id": 10044,
                "promo_start": None,
            },
        },
    ]


@pytest.fixture()
def mock_provider_hits():
    return [
        {
            "_index": "provider_search_index_practitioner_profile",
            "_id": "877915",
            "_score": 4.8638577,
            "_source": {
                "modified_at": "2023-12-02T13:30:59",
                "created_at": "2023-11-27T21:35:31",
                "user_id": 877915,
                "active": 1,
                "role_id": 1,
                "stripe_account_id": None,
                "default_cancellation_policy_id": 3,
                "phone_number": None,
                "reference_quote": None,
                "state_id": None,
                "education": None,
                "work_experience": None,
                "awards": None,
                "dosespot": "{}",
                "booking_buffer": 0,
                "default_prep_buffer": None,
                "next_availability": None,
                "show_when_unavailable": 0,
                "messaging_enabled": 1,
                "response_time": None,
                "anonymous_allowed": 1,
                "ent_national": 0,
                "is_staff": 0,
                "rating": None,
                "zendesk_email": None,
                "show_in_marketplace": 1,
                "show_in_enterprise": 1,
                "json": "{}",
                "experience_started": None,
                "billing_org": None,
                "credential_start": None,
                "note": None,
                "first_name": "Michael",
                "middle_name": None,
                "last_name": "Good",
                "username": None,
                "zendesk_user_id": None,
                "timezone": "UTC",
                "country_code": None,
                "subdivision_code": None,
                "esp_id": "97669f62-f310-4f18-a819-e5b42729adcb",
                "email": None,
                "video_id": None,
            },
        },
        {
            "_index": "provider_search_index_practitioner_profile",
            "_id": "779309",
            "_score": 4.278592,
            "_source": {
                "modified_at": "2023-10-09T17:54:06",
                "created_at": "2023-10-04T22:49:14",
                "user_id": 779309,
                "active": 1,
                "role_id": 1,
                "stripe_account_id": None,
                "default_cancellation_policy_id": 3,
                "phone_number": None,
                "reference_quote": None,
                "state_id": None,
                "education": None,
                "work_experience": None,
                "awards": None,
                "dosespot": "{}",
                "booking_buffer": 0,
                "default_prep_buffer": None,
                "next_availability": None,
                "show_when_unavailable": 0,
                "messaging_enabled": 1,
                "response_time": None,
                "anonymous_allowed": 1,
                "ent_national": 0,
                "is_staff": 0,
                "rating": None,
                "zendesk_email": None,
                "show_in_marketplace": 1,
                "show_in_enterprise": 1,
                "json": "{}",
                "experience_started": None,
                "billing_org": None,
                "credential_start": None,
                "note": None,
                "first_name": "Frank",
                "middle_name": None,
                "last_name": "Ford",
                "username": None,
                "zendesk_user_id": None,
                "timezone": "UTC",
                "country_code": None,
                "subdivision_code": None,
                "esp_id": "352caae7-aee8-4a1a-9f48-cf59879b25d3",
                "email": None,
                "video_id": None,
            },
        },
    ]


@pytest.fixture
def mock_need_category_hits():
    return [
        {
            "_index": "provider_search_index_need_category",
            "_id": "42",
            "_score": 3.2446494,
            "_source": {
                "created_at": "2022-02-02T16:49:53",
                "description": None,
                "display_order": 57,
                "hide_from_multitrack": 0,
                "id": 42,
                "image_id": "icon-hrt.svg",
                "model_id": ".elser_model_2_linux-x86_64",
                "modified_at": "2024-01-05T16:49:53",
                "name": "Medications",
                "parent_category_id": None,
            },
        },
    ]


@pytest.fixture()
def mock_need_hits():
    return [
        {
            "_index": "provider_search_index_need",
            "_id": "45",
            "_score": 3.4922843,
            "_source": {
                "name": "Nutrition",
                "display_order": 0,
                "promote_messaging": 1,
                "description": "Fertility-friendly foods, supplements, managing your weight",
                "created_at": "2023-05-17T21:50:43",
                "id": 45,
                "model_id": ".elser_model_2_linux-x86_64",
                "modified_at": "2023-05-17T21:50:43",
                "hide_from_multitrack": 0,
                "slug": "fert-nutrition",
            },
        },
        # Need with hide_from_multitrack
        {
            "_index": "provider_search_index_need",
            "_id": "46",
            "_score": 2,
            "_source": {
                "name": "Nutrition",
                "display_order": 0,
                "promote_messaging": 1,
                "description": "Fertility-friendly foods, supplements, managing your weight",
                "created_at": "2023-05-17T21:50:43",
                "id": 46,
                "model_id": ".elser_model_2_linux-x86_64",
                "modified_at": "2023-05-17T21:50:43",
                "hide_from_multitrack": 1,
                "slug": "fert-nutrition",
            },
        },
    ]


def test_booking_flow_search(
    factories,
    enterprise_user_with_tracks_and_categories,
    practitioner_with_availability,
    search_api_8_hits,
):
    # Set up needs and need_categories in the member's track
    track_name = "adoption"
    member, tracks, need_categories = enterprise_user_with_tracks_and_categories(
        [track_name]
    )
    search_api_8_hits[3]["_source"]["id"] = need_categories[0].id
    need = factories.NeedFactory.create(
        hide_from_multitrack=False,
    )
    factories.NeedTrackFactory.create(
        track_name=track_name,
        need_id=need.id,
    )
    search_api_8_hits[2]["_source"]["id"] = need.id

    expected_provider, _ = practitioner_with_availability
    # Change the expected provider from our mocked search api results
    # to be in line with the expected one from the DB
    search_api_8_hits[0]["_source"]["user_id"] = expected_provider.id

    with patch(
        "appointments.utils.booking_flow_search._query_search_api"
    ) as mock_response:
        mock_response.return_value = search_api_8_hits
        (
            specialties,
            keywords,
            verticals,
            practitioners,
            need_categories,
            needs,
        ) = search_api_booking_flow("search query string", 10, member, False, False)

    assert len(specialties) == 2
    assert len(keywords) == 0
    assert len(verticals) == 1
    assert len(practitioners) == 1
    assert len(need_categories) == 0
    assert len(needs) == 1


def test_booking_flow_search__filters_need_categories__no_exact_match(
    factories,
    enterprise_user_with_tracks_and_categories,
    mock_need_category_hits,
):
    """
    Tests that need_categories are filtered if not an exact match
    """
    # Given
    track_names = ["adoption"]
    (
        member,
        tracks,
        filtered_need_categories,
    ) = enterprise_user_with_tracks_and_categories(track_names)
    mock_need_category_hits[0]["_source"]["id"] = filtered_need_categories[0].id

    # When
    query_str = filtered_need_categories[0].name[:-1]

    with patch(
        "appointments.utils.booking_flow_search._query_search_api"
    ) as mock_response:
        mock_response.return_value = mock_need_category_hits
        (
            specialties,
            keywords,
            verticals,
            practitioners,
            need_categories,
            needs,
        ) = search_api_booking_flow(
            query_str,
            10,
            member,
            False,
            False,
        )
        assert len(specialties) == 0
        assert len(keywords) == 0
        assert len(verticals) == 0
        assert len(practitioners) == 0
        assert len(needs) == 0

        # Then
        assert len(need_categories) == 0


def test_booking_flow_search__filters_need_categories__multitrack_true(
    factories,
    enterprise_user_with_tracks_and_categories,
    mock_need_category_hits,
):
    """
    Tests that need_categories are filtered by multitrack when the user is multitrack
    """
    # Given
    track_names = ["adoption", "pregnancy"]
    (
        member,
        tracks,
        filtered_need_categories,
    ) = enterprise_user_with_tracks_and_categories(track_names)
    mock_need_category_hits[0]["_source"]["id"] = filtered_need_categories[0].id

    # When
    mock_need_category_hits[0]["_source"]["hide_from_multitrack"] = 1

    with patch(
        "appointments.utils.booking_flow_search._query_search_api"
    ) as mock_response:
        mock_response.return_value = mock_need_category_hits
        (
            specialties,
            keywords,
            verticals,
            practitioners,
            need_categories,
            needs,
        ) = search_api_booking_flow(
            filtered_need_categories[0].name,
            10,
            member,
            False,
            False,
        )
        assert len(specialties) == 0
        assert len(keywords) == 0
        assert len(verticals) == 0
        assert len(practitioners) == 0
        assert len(needs) == 0

        # Then
        assert len(need_categories) == 0


def test_booking_flow_search__filters_need_categories__multitrack_false(
    factories,
    enterprise_user_with_tracks_and_categories,
    mock_need_category_hits,
):
    """
    Tests that need_categories are not filtered by multitrack when the user is not
    multitrack
    """
    track_names = ["adoption", "pregnancy"]
    (
        member,
        tracks,
        expected_need_categories,
    ) = enterprise_user_with_tracks_and_categories(track_names)
    mock_need_category_hits[0]["_source"]["id"] = expected_need_categories[0].id
    mock_need_category_hits[0]["_source"]["name"] = expected_need_categories[0].name

    with patch(
        "appointments.utils.booking_flow_search._query_search_api"
    ) as mock_response:
        mock_response.return_value = mock_need_category_hits

        # Should return the need_category
        (
            specialties,
            keywords,
            verticals,
            practitioners,
            need_categories,
            needs,
        ) = search_api_booking_flow(
            expected_need_categories[0].name,
            10,
            member,
            False,
            False,
        )

        assert len(specialties) == 0
        assert len(keywords) == 0
        assert len(verticals) == 0
        assert len(practitioners) == 0
        assert len(need_categories) == 1
        assert len(needs) == 0

        assert need_categories[0]["id"] == expected_need_categories[0].id


def test_booking_flow_search__filters_need_categories__member_track_nc_ids(
    factories,
    enterprise_user_with_tracks_and_categories,
    mock_need_category_hits,
):
    """
    Tests that need_categories are filtered by member_tracks
    """
    member_track_name = "adoption"
    member, tracks, _ = enterprise_user_with_tracks_and_categories([member_track_name])

    # Add a different track to the need category
    filtered_track_name = "pregnancy"
    filtered_need_category = factories.NeedCategoryFactory.create()
    mock_need_category_hits[0]["_source"]["id"] = filtered_need_category.id
    factories.NeedCategoryTrackFactory.create(
        track_name=filtered_track_name,
        need_category_id=filtered_need_category.id,
    )

    with patch(
        "appointments.utils.booking_flow_search._query_search_api"
    ) as mock_response:
        mock_response.return_value = mock_need_category_hits
        # Member is multitrack, and both need_category ids are present
        (
            specialties,
            keywords,
            verticals,
            practitioners,
            need_categories,
            needs,
        ) = search_api_booking_flow(
            filtered_need_category.name,
            10,
            member,
            False,
            False,
        )

    assert len(specialties) == 0
    assert len(keywords) == 0
    assert len(verticals) == 0
    assert len(practitioners) == 0
    assert len(needs) == 0

    assert len(need_categories) == 0


def test_booking_flow_search__filters_verticals__deleted_at(
    enterprise_user,
    mock_vertical_hits,
):
    """
    Tests that verticals are filtered by "deleted_at"
    """
    with patch(
        "appointments.utils.booking_flow_search._query_search_api"
    ) as mock_response:
        mock_response.return_value = mock_vertical_hits
        (
            specialties,
            keywords,
            verticals,
            practitioners,
            need_categories,
            needs,
        ) = search_api_booking_flow(
            "search query str",
            10,
            enterprise_user,
            False,
            False,
        )

    assert len(specialties) == 0
    assert len(keywords) == 0
    assert len(practitioners) == 0
    assert len(need_categories) == 0
    assert len(needs) == 0

    # Out of the two verticals, one has "deleted at" set
    assert len(verticals) == 1
    assert verticals[0]["id"] == 10012


def test_booking_flow_search__filters_verticals__cx_name(
    enterprise_user,
    mock_vertical_hits,
):
    """
    Tests that verticals are filtered if CX
    """
    # Only mock_vertical_hits[1] should get filtered, as it is a CX vertical
    mock_hits = [mock_vertical_hits[0], mock_vertical_hits[1]]
    with patch(
        "appointments.utils.booking_flow_search._query_search_api"
    ) as mock_response:
        mock_response.return_value = mock_hits
        (
            specialties,
            keywords,
            verticals,
            practitioners,
            need_categories,
            needs,
        ) = search_api_booking_flow(
            "search query str",
            10,
            enterprise_user,
            False,
            False,
        )

    assert len(specialties) == 0
    assert len(keywords) == 0
    assert len(practitioners) == 0
    assert len(need_categories) == 0
    assert len(needs) == 0

    # Out of the two verticals, one should be filtered because it is CX
    assert len(verticals) == 1
    assert verticals[0]["id"] == 10012


def test_booking_flow_search__filters_providers__cx(
    factories,
    vertical_ca,
    enterprise_user,
    mock_provider_hits,
    vertical_wellness_coach_can_prescribe,
):
    """
    Tests that providers are filtered if CX
    """
    # Create a matching provider for each mock provider
    expected_provider = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[vertical_wellness_coach_can_prescribe],
    )
    mock_provider_hits[1]["_source"]["user_id"] = expected_provider.id

    # This provider should get filtered because their vertical is CX
    filtered_provider = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[vertical_ca],
    )
    mock_provider_hits[0]["_source"]["user_id"] = filtered_provider.id

    with patch(
        "appointments.utils.booking_flow_search._query_search_api"
    ) as mock_response:
        mock_response.return_value = mock_provider_hits
        (
            specialties,
            keywords,
            verticals,
            practitioners,
            need_categories,
            needs,
        ) = search_api_booking_flow(
            "search query",
            10,
            enterprise_user,
            False,
            False,
        )

    assert len(specialties) == 0
    assert len(keywords) == 0
    assert len(verticals) == 0
    assert len(need_categories) == 0
    assert len(needs) == 0

    assert len(practitioners) == 1
    assert expected_provider.id == practitioners[0].id


def test_booking_flow_search__filters_providers__show_in_enterprise(
    factories,
    enterprise_user,
    mock_provider_hits,
    vertical_wellness_coach_can_prescribe,
):
    """
    Tests that providers are filtered in accordance with "show_in_enterprise"
    """
    # Create a matching provider for each mock provider
    expected_provider = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[vertical_wellness_coach_can_prescribe],
        practitioner_profile__show_in_enterprise=True,
    )
    mock_provider_hits[0]["_source"]["user_id"] = expected_provider.id

    # This provider should get filtered because show_in_enterprise is false
    filtered_provider = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[vertical_wellness_coach_can_prescribe],
        practitioner_profile__show_in_enterprise=False,
    )
    mock_provider_hits[1]["_source"]["user_id"] = filtered_provider.id
    mock_provider_hits[1]["_source"]["show_in_enterprise"] = 0

    with patch(
        "appointments.utils.booking_flow_search._query_search_api"
    ) as mock_response:
        mock_response.return_value = mock_provider_hits
        (
            specialties,
            keywords,
            verticals,
            practitioners,
            need_categories,
            needs,
        ) = search_api_booking_flow(
            "search query",
            10,
            enterprise_user,
            False,
            False,
        )

    assert len(specialties) == 0
    assert len(keywords) == 0
    assert len(verticals) == 0
    assert len(need_categories) == 0
    assert len(needs) == 0

    assert len(practitioners) == 1
    assert expected_provider.id == practitioners[0].id


def test_booking_flow_search__filters_providers__show_in_marketplace(
    factories,
    mock_provider_hits,
    marketplace_user,
    vertical_wellness_coach_can_prescribe,
):
    """
    Tests that providers are filtered in accordance with "show_in_marketplace"
    """
    # Create a matching provider for each mock provider
    expected_provider = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[vertical_wellness_coach_can_prescribe],
        practitioner_profile__show_in_marketplace=True,
    )
    mock_provider_hits[0]["_source"]["user_id"] = expected_provider.id

    # This provider should get filtered because show_in_marketplace is false
    filtered_provider = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[vertical_wellness_coach_can_prescribe],
        practitioner_profile__show_in_marketplace=False,
    )
    mock_provider_hits[1]["_source"]["user_id"] = filtered_provider.id
    mock_provider_hits[1]["_source"]["show_in_marketplace"] = 0

    with patch(
        "appointments.utils.booking_flow_search._query_search_api"
    ) as mock_response:
        mock_response.return_value = mock_provider_hits
        (
            specialties,
            keywords,
            verticals,
            practitioners,
            need_categories,
            needs,
        ) = search_api_booking_flow(
            "search query",
            10,
            marketplace_user,
            False,
            False,
        )

    assert len(specialties) == 0
    assert len(keywords) == 0
    assert len(verticals) == 0
    assert len(need_categories) == 0
    assert len(needs) == 0

    assert len(practitioners) == 1
    assert expected_provider.id == practitioners[0].id


@freeze_time(FREEZE_TIME_STR)
def test_booking_flow_search__filters_providers__next_availability(
    factories,
    enterprise_user,
    practitioner_with_availability,
    mock_provider_hits,
    vertical_wellness_coach_can_prescribe,
):
    """
    Tests that providers are filtered if they don't have upcoming availability
    """
    # Create a matching provider for each mock provider
    expected_provider, _ = practitioner_with_availability

    # Change the expected providers from our mocked search api results
    # to be in line with the expected one from the DB
    mock_provider_hits[0]["_source"]["user_id"] = expected_provider.id

    # This provider should get filtered because they do not have availability
    filtered_provider = factories.PractitionerUserFactory.create(
        practitioner_profile__next_availability=None,
        practitioner_profile__show_when_unavailable=False,
        practitioner_profile__verticals=[vertical_wellness_coach_can_prescribe],
    )
    mock_provider_hits[1]["_source"]["user_id"] = filtered_provider.id

    with patch(
        "appointments.utils.booking_flow_search._query_search_api"
    ) as mock_response:
        mock_response.return_value = mock_provider_hits
        (
            specialties,
            keywords,
            verticals,
            practitioners,
            need_categories,
            needs,
        ) = search_api_booking_flow(
            "search query",
            10,
            enterprise_user,
            False,
            False,
        )

    assert len(specialties) == 0
    assert len(keywords) == 0
    assert len(verticals) == 0
    assert len(need_categories) == 0
    assert len(needs) == 0

    assert len(practitioners) == 1
    assert expected_provider.id == practitioners[0].id


@freeze_time(FREEZE_TIME_STR)
def test_booking_flow_search__filters_providers__show_when_unavailable(
    factories,
    enterprise_user,
    practitioner_with_availability,
    mock_provider_hits,
    vertical_wellness_coach_can_prescribe,
):
    """
    Tests that providers aren't filtered if they have show_when_unavailable
    """
    # Create a matching provider for each mock provider
    expected_provider = factories.PractitionerUserFactory.create(
        practitioner_profile__next_availability=None,
        practitioner_profile__show_when_unavailable=True,
        practitioner_profile__verticals=[vertical_wellness_coach_can_prescribe],
    )
    mock_provider_hits[0]["_source"]["user_id"] = expected_provider.id
    mock_provider_hits[0]["_source"]["show_when_unavailable"] = 1

    # This provider should get filtered because they do not have availability
    filtered_provider = factories.PractitionerUserFactory.create(
        id=mock_provider_hits[1]["_source"]["user_id"],
        practitioner_profile__next_availability=None,
        practitioner_profile__show_when_unavailable=False,
        practitioner_profile__verticals=[vertical_wellness_coach_can_prescribe],
    )
    mock_provider_hits[1]["_source"]["user_id"] = filtered_provider.id

    with patch(
        "appointments.utils.booking_flow_search._query_search_api"
    ) as mock_response:
        mock_response.return_value = mock_provider_hits
        (
            specialties,
            keywords,
            verticals,
            practitioners,
            need_categories,
            needs,
        ) = search_api_booking_flow(
            "search query str",
            10,
            enterprise_user,
            False,
            False,
        )

    assert len(specialties) == 0
    assert len(keywords) == 0
    assert len(verticals) == 0
    assert len(need_categories) == 0
    assert len(needs) == 0

    assert len(practitioners) == 1
    assert expected_provider.id == practitioners[0].id


def test_booking_flow_search__filters_needs__member_track(
    factories,
    enterprise_user_with_tracks_and_categories,
    mock_need_hits,
):
    """
    Tests that needs are filtered by member_tracks
    """
    expected_track_name = "pregnancy"
    filtered_track_name = "adoption"
    member, tracks, need_categories = enterprise_user_with_tracks_and_categories(
        [expected_track_name]
    )

    expected_need = factories.NeedFactory.create(
        hide_from_multitrack=False,
    )
    factories.NeedTrackFactory.create(
        track_name=expected_track_name,
        need_id=expected_need.id,
    )
    mock_need_hits[0]["_source"]["id"] = expected_need.id
    mock_need_hits[0]["_source"]["name"] = expected_need.name

    # This need should be filtered because they are not associated with the member's track
    filtered_need = factories.NeedFactory.create(
        hide_from_multitrack=False,
    )
    factories.NeedTrackFactory.create(
        track_name=filtered_track_name,
        need_id=filtered_need.id,
    )
    mock_need_hits[1]["_source"]["id"] = filtered_need.id
    mock_need_hits[1]["_source"]["name"] = filtered_need.name

    with patch(
        "appointments.utils.booking_flow_search._query_search_api"
    ) as mock_response:
        mock_response.return_value = mock_need_hits
        (
            specialties,
            keywords,
            verticals,
            practitioners,
            need_categories,
            needs,
        ) = search_api_booking_flow(
            "search query str",
            10,
            member,
            False,
            False,
        )

    assert len(specialties) == 0
    assert len(keywords) == 0
    assert len(verticals) == 0
    assert len(practitioners) == 0
    assert len(need_categories) == 0

    assert len(needs) == 1
    assert needs[0].id == expected_need.id


def test_booking_flow_search__filters_needs__multitrack_true(
    factories,
    enterprise_user_with_tracks_and_categories,
    mock_need_hits,
):
    """
    Tests that needs are filtered by multitrack when the user is multitrack
    """
    track_names = ["adoption", "pregnancy"]
    member, tracks, _ = enterprise_user_with_tracks_and_categories(track_names)

    expected_need = factories.NeedFactory.create(
        hide_from_multitrack=False,
    )
    factories.NeedTrackFactory.create(
        track_name=tracks[0].name,
        need_id=expected_need.id,
    )
    mock_need_hits[0]["_source"]["id"] = expected_need.id
    mock_need_hits[0]["_source"]["name"] = expected_need.name

    # This need should be filtered because "hide_from_multitrack" is set to True
    filtered_need = factories.NeedFactory.create(
        hide_from_multitrack=True,
    )
    factories.NeedTrackFactory.create(
        track_name=tracks[1].name,
        need_id=filtered_need.id,
    )
    mock_need_hits[1]["_source"]["id"] = filtered_need.id
    mock_need_hits[1]["_source"]["name"] = filtered_need.name

    with patch(
        "appointments.utils.booking_flow_search._query_search_api"
    ) as mock_response:
        mock_response.return_value = mock_need_hits
        (
            specialties,
            keywords,
            verticals,
            practitioners,
            need_categories,
            needs,
        ) = search_api_booking_flow(
            "search query str",
            10,
            member,
            False,
            False,
        )

    assert len(specialties) == 0
    assert len(keywords) == 0
    assert len(verticals) == 0
    assert len(practitioners) == 0
    assert len(need_categories) == 0

    assert len(needs) == 1
    assert needs[0].id == expected_need.id


def test_booking_flow_search__filters_needs__multitrack_false(
    factories,
    enterprise_user_with_tracks_and_categories,
    mock_need_hits,
):
    """
    Tests that needs are not filtered by multitrack when the user is not multitrack
    """
    track_name = "adoption"
    member, tracks, _ = enterprise_user_with_tracks_and_categories([track_name])

    expected_need_1 = factories.NeedFactory.create(
        hide_from_multitrack=False,
    )
    factories.NeedTrackFactory.create(
        track_name=track_name,
        need_id=expected_need_1.id,
    )
    mock_need_hits[0]["_source"]["id"] = expected_need_1.id
    mock_need_hits[0]["_source"]["name"] = expected_need_1.name

    expected_need_2 = factories.NeedFactory.create(
        hide_from_multitrack=True,
    )
    factories.NeedTrackFactory.create(
        track_name=track_name,
        need_id=expected_need_2.id,
    )
    mock_need_hits[1]["_source"]["id"] = expected_need_2.id
    mock_need_hits[1]["_source"]["name"] = expected_need_2.name

    with patch(
        "appointments.utils.booking_flow_search._query_search_api"
    ) as mock_response:
        mock_response.return_value = mock_need_hits
        (
            specialties,
            keywords,
            verticals,
            practitioners,
            need_categories,
            needs,
        ) = search_api_booking_flow(
            "search query str",
            10,
            member,
            False,
            False,
        )

    assert len(specialties) == 0
    assert len(keywords) == 0
    assert len(verticals) == 0
    assert len(practitioners) == 0
    assert len(need_categories) == 0

    assert len(needs) == 2
    expected_need_ids = {expected_need_1.id, expected_need_2.id}
    actual_need_ids = {needs[0].id, needs[1].id}
    assert actual_need_ids == expected_need_ids


def test_booking_flow_search__filters_needs__matching_nc__exact_match(
    factories,
    enterprise_user_with_tracks_and_categories,
    practitioner_with_availability,
    search_api_8_hits,
):
    """
    Tests that when there is an exact match on need_categories we do not return any
    needs except the ones that are associated with the need_category
    """
    # Set up needs and need_categories in the member's track
    track_name = "adoption"
    member, tracks, n_categories = enterprise_user_with_tracks_and_categories(
        [track_name]
    )
    expected_need_category = n_categories[0]
    search_api_8_hits[3]["_source"]["id"] = n_categories[0].id
    search_api_8_hits[3]["_source"]["name"] = n_categories[0].name

    # filtered_need_1 should get filtered because it is not associated with the expected_need_category
    filtered_need_1 = factories.NeedFactory.create(
        hide_from_multitrack=False,
    )
    factories.NeedTrackFactory.create(
        track_name=track_name,
        need_id=filtered_need_1.id,
    )
    search_api_8_hits[2]["_source"]["id"] = filtered_need_1.id

    # expected_need_2 and expected_need_3 should be returned because they belong to
    # expected_need_category above
    expected_need_1 = factories.NeedFactory.create(
        hide_from_multitrack=False, categories=[expected_need_category]
    )
    factories.NeedTrackFactory.create(
        track_name=track_name,
        need_id=expected_need_1.id,
    )
    expected_need_2 = factories.NeedFactory.create(
        hide_from_multitrack=False, categories=[expected_need_category]
    )
    factories.NeedTrackFactory.create(
        track_name=track_name,
        need_id=expected_need_2.id,
    )

    expected_provider, _ = practitioner_with_availability
    # Change the expected provider from our mocked search api results
    # to be in line with the expected one from the DB
    search_api_8_hits[0]["_source"]["user_id"] = expected_provider.id

    with patch(
        "appointments.utils.booking_flow_search._query_search_api"
    ) as mock_response:
        mock_response.return_value = search_api_8_hits
        (
            specialties,
            keywords,
            verticals,
            practitioners,
            need_categories,
            needs,
        ) = search_api_booking_flow(
            expected_need_category.name, 10, member, False, False
        )

    assert len(specialties) == 2
    assert len(keywords) == 0
    assert len(verticals) == 1
    assert len(practitioners) == 1

    assert len(need_categories) == 1
    assert need_categories[0]["id"] == expected_need_category.id
    assert len(needs) == 2
    expected_need_ids = {expected_need_1.id, expected_need_2.id}
    actual_need_ids = {needs[0].id, needs[1].id}
    assert actual_need_ids == expected_need_ids


@pytest.mark.parametrize(
    argnames="flag_on, expected_query_len",
    argvalues=[(True, 9), (False, 5)],
    ids=[
        "booking_flow_search_prefix_matching_flag_on",
        "booking_flow_search_prefix_matching_flag_off",
    ],
)
def test_create_search_query(flag_on: bool, expected_query_len: int):
    """
    Tests that create search query returns the correct result depending on the
    "booking-flow-search-prefix-matching" feature flag
    """
    with patch("maven.feature_flags.bool_variation", return_value=flag_on):
        actual_query = json.loads(_create_search_query("query"))

    actual_query_should_len = len(actual_query["bool"]["should"])
    assert actual_query_should_len == expected_query_len
