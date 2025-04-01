from datetime import datetime, timedelta
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest

from eligibility.pytests import factories as e9y_factories
from models.tracks import TrackName
from models.tracks.member_track import MemberTrack
from tracks.constants import ORDERED_TRACK_RECOMMENDATIONS


@pytest.fixture
def patch_is_user_known_to_be_eligible_for_org():
    with patch("eligibility.get_verification_service") as p:
        mock_service = MagicMock()
        mock_service.is_user_known_to_be_eligible_for_org = MagicMock()
        p.return_value = mock_service
        yield mock_service.is_user_known_to_be_eligible_for_org


@pytest.mark.usefixtures("patch_e9y_service_functions")
def test_get_expired_track_dashboard_metadata_with_expired_track(
    client,
    api_helpers,
    default_user,
    factories,
    patch_is_user_known_to_be_eligible_for_org,
):
    expired_track = create_expired_track(user=default_user, factories=factories)
    expected_tracks = ORDERED_TRACK_RECOMMENDATIONS[expired_track.name]

    patch_is_user_known_to_be_eligible_for_org.return_value = True
    verification = e9y_factories.build_verification_from_oe(
        user_id=default_user.id, employee=default_user.organization_employee
    )

    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user",
        return_value=verification,
    ), mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ), mock.patch(
        "tracks.service.tracks.TrackSelectionService.validate_initiation",
        return_value=expired_track.client_track,
    ), mock.patch(
        "eligibility.service.EnterpriseVerificationService.is_verification_active",
        return_value=True,
    ):
        res = client.get(
            f"api/v1/dashboard-metadata/expired-track/{expired_track.id}",
            headers=api_helpers.json_headers(user=default_user),
        ).json

        assert res["is_known_to_be_eligible"]
        assert len(res["available_tracks"]) == len(expected_tracks)
        assert res["available_tracks"][0] == {
            "name": TrackName.PARENTING_AND_PEDIATRICS,
            "display_name": "Parenting & Pediatrics",
            "display_length": "Annual renewal up to age 10",
            "image": "https://storage.googleapis.com/maven-qa-images/Programs/Maven_Pediatrics.png",
            "description": "Boost your parenting confidence and learn about your kids’ development with help from our parenting experts, for parents of children 1 year and up.",
            "enrollment_requirement_description": None,
            "life_stage": "raising",
            "track_selection_category": "parenting_wellness",
            "length_in_days": None,
        }
        assert res["expired_track"] == {
            "description": expired_track.description,
            "display_length": expired_track.display_length,
            "display_name": expired_track.display_name,
            "ended_at": expired_track.ended_at.isoformat(),
            "enrollment_requirement_description": expired_track.enrollment_requirement_description,
            "image": expired_track.image,
            "life_stage": expired_track.life_stage,
            "name": expired_track.name,
            "track_selection_category": expired_track.track_selection_category,
        }
        assert not hasattr(res, "advocate")
        assert res["first_name"] == default_user.first_name


def test_get_expired_track_dashboard_metadata_with_unknown_eligibility(
    default_user,
    client,
    api_helpers,
    factories,
    patch_is_user_known_to_be_eligible_for_org,
):
    expired_track = create_expired_track(user=default_user, factories=factories)

    patch_is_user_known_to_be_eligible_for_org.return_value = False

    res = client.get(
        f"api/v1/dashboard-metadata/expired-track/{expired_track.id}",
        headers=api_helpers.json_headers(user=default_user),
    ).json

    assert not res["is_known_to_be_eligible"]


def test_get_expired_track_dashboard_metadata_with_no_org(
    default_user, client, api_helpers, factories
):
    expired_track = create_expired_track(user=default_user, factories=factories)

    res = client.get(
        f"api/v1/dashboard-metadata/expired-track/{expired_track.id}",
        headers=api_helpers.json_headers(user=default_user),
    ).json

    assert len(res["available_tracks"]) == 0


def test_get_expired_track_dashboard_metadata_with_active_track(
    default_user, client, api_helpers, factories
):
    active_track = factories.MemberTrackFactory.create(
        user=default_user,
    )

    res = client.get(
        f"api/v1/dashboard-metadata/expired-track/{active_track.id}",
        headers=api_helpers.json_headers(user=default_user),
    )

    assert res.status_code == 400
    assert (
        res.json["errors"][0]["detail"]
        == f"Track with ID = {active_track.id} has not expired"
    )


def test_get_expired_track_dashboard_metadata_with_no_user(client):
    res = client.get(
        "api/v1/dashboard-metadata/expired-track/1",
    )

    assert res.status_code == 401


def test_get_expired_track_dashboard_metadata_with_non_existent_track(
    default_user, client, api_helpers
):
    assert_expired_track_not_found(client, api_helpers, default_user, 123456)


def test_get_expired_track_dashboard_metadata_with_other_users_track(
    default_user, client, api_helpers, factories
):
    expired_track = factories.MemberTrackFactory.create(
        user=default_user,
        ended_at=datetime.today() - timedelta(days=800),
    )

    assert_expired_track_not_found(
        client, api_helpers, factories.EnterpriseUserFactory.create(), expired_track.id
    )


def assert_expired_track_not_found(client, api_helpers, user, track_id):
    res = client.get(
        f"api/v1/dashboard-metadata/expired-track/{track_id}",
        headers=api_helpers.json_headers(user=user),
    )

    assert res.status_code == 404
    assert (
        res.json["errors"][0]["detail"]
        == f"User with ID = {user.id} has no track with ID = {track_id}"
    )


def create_expired_track(user, factories) -> MemberTrack:
    all_track_names = [*TrackName]
    org = factories.OrganizationFactory.create(allowed_tracks=all_track_names)
    return factories.MemberTrackFactory.create(
        user=user,
        ended_at=datetime.today() - timedelta(days=800),
        name=TrackName.POSTPARTUM,
        client_track=factories.ClientTrackFactory(organization=org),
    )
