import dataclasses
from datetime import date, datetime, timedelta
from unittest import mock

import pytest
from flask.testing import FlaskClient
from maven import feature_flags

from authn.models.user import User
from common import stats
from models.tracks import ClientTrack, TrackName
from models.tracks.client_track import TrackModifiers
from tracks.resources.member_tracks import (
    ActiveMemberTrack,
    InactiveMemberTrack,
    ScheduledMemberTrack,
)
from utils.api_interaction_mixin import APIInteractionMixin


@pytest.fixture
def ff_test_data():
    with feature_flags.test_data() as td:
        yield td


@pytest.fixture()
def client_track(factories) -> ClientTrack:
    return factories.ClientTrackFactory.create(
        organization=factories.OrganizationFactory.create(), track=TrackName.PREGNANCY
    )


@pytest.fixture
def set_up_member_tracks(default_user: User, client_track: ClientTrack, factories):
    factories.MemberTrackFactory.create(
        user=default_user,
        name=TrackName.PARENTING_AND_PEDIATRICS,
        client_track=client_track,
    )
    factories.MemberTrackFactory.create(
        user=default_user,
        name=TrackName.BREAST_MILK_SHIPPING,
        client_track=client_track,
    )
    factories.MemberTrackFactory.create(
        user=default_user,
        ended_at=datetime.today() - timedelta(days=400),
    )
    factories.MemberTrackFactory.create(
        user=default_user,
        ended_at=datetime.today() - timedelta(days=800),
    )
    scheduled_track_1 = factories.MemberTrackFactory.create(
        user=default_user, start_date=date.today() + timedelta(weeks=2)
    )
    scheduled_track_1.activated_at = None
    scheduled_track_2 = factories.MemberTrackFactory.create(
        user=default_user, start_date=date.today() + timedelta(weeks=4)
    )
    scheduled_track_2.activated_at = None
    invalid_track_1 = factories.MemberTrackFactory.create(
        user=default_user,
        ended_at=datetime.today() - timedelta(days=42),
    )
    invalid_track_1.activated_at = None
    invalid_track_2 = factories.MemberTrackFactory.create(
        user=default_user,
        ended_at=datetime.today() - timedelta(days=420),
    )
    invalid_track_2.activated_at = None


def assert_base_track_fields(provided, expected):
    assert provided["id"] == expected.id
    assert provided["name"] == expected.name
    assert provided["display_name"] == expected.display_name
    assert (
        provided["scheduled_end"]
        == expected.get_display_scheduled_end_date().isoformat()
    )


@pytest.mark.parametrize("is_doula_only_track", [True, False])
@mock.patch("models.tracks.client_track.should_enable_doula_only_track")
def test_get_active_tracks(
    mock_should_enable_doula_only_track,
    is_doula_only_track,
    client,
    api_helpers,
    factories,
    default_user,
):
    # Given
    org_1 = factories.OrganizationFactory.create()
    org_2 = factories.OrganizationFactory.create()

    track_modifiers = "doula_only" if is_doula_only_track else None

    org_1_client_track = factories.ClientTrackFactory.create(
        organization=org_1, track=TrackName.PREGNANCY, track_modifiers=track_modifiers
    )
    org_2_client_track = factories.ClientTrackFactory.create(
        organization=org_2,
        track=TrackName.PARENTING_AND_PEDIATRICS,
    )

    pregnancy_track = factories.MemberTrackFactory.create(
        user=default_user, name=TrackName.PREGNANCY, client_track=org_1_client_track
    )
    pnp_track = factories.MemberTrackFactory.create(
        user=default_user,
        name=TrackName.PARENTING_AND_PEDIATRICS,
        client_track=org_2_client_track,
    )

    mock_should_enable_doula_only_track.return_value = is_doula_only_track

    # When
    res = client.get(
        "/api/v1/tracks/active", headers=api_helpers.standard_headers(default_user)
    )

    # Then
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert len(json["active_tracks"]) == 2

    first_track = json["active_tracks"][0]
    second_track = json["active_tracks"][1]

    assert_base_track_fields(first_track, pregnancy_track)
    assert first_track["current_phase"] == pregnancy_track.current_phase.name
    assert first_track["organization"]["id"] == org_1.id

    if is_doula_only_track:
        assert first_track["track_modifiers"] == [TrackModifiers.DOULA_ONLY]
    else:
        assert first_track["track_modifiers"] == []

    assert_base_track_fields(second_track, pnp_track)
    assert second_track["current_phase"] == pnp_track.current_phase.name
    assert second_track["organization"]["id"] == org_2.id

    assert second_track["track_modifiers"] == []


@pytest.mark.parametrize(
    "track_name, expected_dashboard",
    [
        (TrackName.PREGNANCY, "dashboard2020"),
        (TrackName.PARENTING_AND_PEDIATRICS, "dashboard2020"),
    ],
)
def test_get_active_tracks_dashboard_variations(
    track_name: TrackName,
    expected_dashboard: str,
    client: FlaskClient,
    api_helpers: APIInteractionMixin,
    factories,
    default_user: User,
):
    factories.MemberTrackFactory.create(user=default_user, name=track_name)

    response = client.get(
        "/api/v1/tracks/active", headers=api_helpers.standard_headers(default_user)
    )
    json = api_helpers.load_json(response)
    assert json["active_tracks"][0]["dashboard"] == expected_dashboard


def test_get_inactive_tracks(client, api_helpers, factories, default_user):
    older_track = factories.MemberTrackFactory.create(
        user=default_user,
        ended_at=datetime.today() - timedelta(days=800),
    )
    newer_track = factories.MemberTrackFactory.create(
        user=default_user,
        ended_at=datetime.today() - timedelta(days=400),
    )

    res = client.get(
        "/api/v1/tracks/inactive", headers=api_helpers.standard_headers(default_user)
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert len(json["inactive_tracks"]) == 2

    first_track = json["inactive_tracks"][0]
    second_track = json["inactive_tracks"][1]

    assert_base_track_fields(first_track, newer_track)
    assert first_track["ended_at"] == newer_track.ended_at.isoformat()

    assert_base_track_fields(second_track, older_track)
    assert second_track["ended_at"] == older_track.ended_at.isoformat()


def test_get_active_tracks_benefits_url(factories, client, api_helpers, default_user):
    # Given
    member_track = factories.MemberTrackFactory.create(
        user=default_user, name="pregnancy"
    )
    organization = member_track.organization
    organization.benefits_url = "testurl.com"
    factories.ClientTrackFactory.create(
        organization=member_track.organization, track=member_track.partner_track.name
    )

    # When
    res = client.get(
        "/api/v1/tracks/active", headers=api_helpers.standard_headers(default_user)
    )

    # Then
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert len(json["active_tracks"]) == 1
    active_tracks = json["active_tracks"][0]
    assert active_tracks["organization"]["benefits_url"] == "testurl.com"


@mock.patch("common.stats.increment")
def test_get_active_tracks_v2(
    mock_stats_incr, client, api_helpers, factories, default_user, ff_test_data
):
    ff_test_data.update(
        ff_test_data.flag("track-service-v2-activeTracksResource").variation_for_all(
            True
        )
    )
    older_track = factories.MemberTrackFactory.create(
        user=default_user,
        name=TrackName.POSTPARTUM,
        anchor_date=(date.today() - timedelta(weeks=6)),
        created_at=(date.today() - timedelta(weeks=6)),
        start_date=(date.today() - timedelta(weeks=6)),
    )
    newer_track = factories.MemberTrackFactory.create(
        user=default_user,
        name=TrackName.PARENTING_AND_PEDIATRICS,
        anchor_date=(date.today() - timedelta(weeks=2)),
        created_at=(date.today() - timedelta(weeks=2)),
        start_date=(date.today() - timedelta(weeks=2)),
    )
    res = client.get(
        "/api/v1/tracks/active", headers=api_helpers.standard_headers(default_user)
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert len(json["active_tracks"]) == 2

    first_track = json["active_tracks"][0]
    second_track = json["active_tracks"][1]

    assert_base_track_fields(first_track, older_track)
    assert first_track["current_phase"] == "week-46"  # 39 + 7

    assert_base_track_fields(second_track, newer_track)
    assert second_track["current_phase"] == "week-3"

    mock_stats_incr.assert_called_with(
        metric_name="mono.tracks.3lp.active_tracks_resource",
        pod_name=stats.PodNames.ENROLLMENTS,
        tags=["match:true"],
    )


@mock.patch("common.stats.increment")
def test_get_inactive_tracks_v2(
    mock_stats_incr, client, api_helpers, factories, default_user, ff_test_data
):
    ff_test_data.update(
        ff_test_data.flag("track-service-v2-InactiveTracksResource").variation_for_all(
            True
        )
    )

    # we make these with microseconds set to 0 because sql can't store them,
    # but the flask object factories pretend they're there
    older_track = factories.MemberTrackFactory.create(
        user=default_user,
        ended_at=datetime.today().replace(microsecond=0) - timedelta(days=800),
    )
    newer_track = factories.MemberTrackFactory.create(
        user=default_user,
        ended_at=datetime.today().replace(microsecond=0) - timedelta(days=400),
    )
    res = client.get(
        "/api/v1/tracks/inactive", headers=api_helpers.standard_headers(default_user)
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert len(json["inactive_tracks"]) == 2

    first_track = json["inactive_tracks"][0]
    second_track = json["inactive_tracks"][1]

    assert_base_track_fields(first_track, newer_track)
    assert first_track["ended_at"] == newer_track.ended_at.isoformat()

    assert_base_track_fields(second_track, older_track)
    assert second_track["ended_at"] == older_track.ended_at.isoformat()

    mock_stats_incr.assert_called_with(
        metric_name="mono.tracks.3lp.inactive_tracks_resource",
        pod_name=stats.PodNames.ENROLLMENTS,
        tags=["match:true"],
    )


def test_get_scheduled_tracks(client, api_helpers, factories, default_user):
    scheduled_track = factories.MemberTrackFactory.create(
        user=default_user, start_date=date.today() + timedelta(weeks=2)
    )
    scheduled_track.activated_at = None

    res = client.get(
        "/api/v1/tracks/scheduled", headers=api_helpers.standard_headers(default_user)
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert len(json["scheduled_tracks"]) == 1

    first_track = json["scheduled_tracks"][0]

    assert_base_track_fields(first_track, scheduled_track)
    assert first_track["start_date"] == scheduled_track.start_date.isoformat()


@mock.patch("common.stats.increment")
def test_get_scheduled_tracks_v2(
    mock_stats_incr, client, api_helpers, factories, default_user, ff_test_data
):
    ff_test_data.update(
        ff_test_data.flag(
            "track-service-v-2-scheduled-tracks-resource"
        ).variation_for_all(True)
    )
    scheduled_track = factories.MemberTrackFactory.create(
        user=default_user, start_date=date.today() + timedelta(weeks=2)
    )
    scheduled_track.activated_at = None

    res = client.get(
        "/api/v1/tracks/scheduled", headers=api_helpers.standard_headers(default_user)
    )
    json = api_helpers.load_json(res)

    assert res.status_code == 200
    assert len(json["scheduled_tracks"]) == 1

    first_track = json["scheduled_tracks"][0]

    assert_base_track_fields(first_track, scheduled_track)
    assert first_track["start_date"] == scheduled_track.start_date.isoformat()

    mock_stats_incr.assert_called_with(
        metric_name="mono.tracks.3lp.scheduled_tracks_resource",
        pod_name=stats.PodNames.ENROLLMENTS,
        tags=["match:true"],
    )


@pytest.mark.parametrize(
    argnames="path_suffix",
    argvalues=[
        "active",
        "inactive",
        "scheduled",
        "123/onboarding_assessment",
    ],
)
def test_returns_401_when_unauthenticated(client, path_suffix):
    res = client.get(f"/api/v1/tracks/{path_suffix}")

    assert res.status_code == 401


def test_get_onboarding_assessment_with_id_and_slug(
    client, api_helpers, default_user, factories
):
    factories.AssessmentLifecycleTrackFactory.create(
        track_name=TrackName.PREGNANCY, assessment_versions=[1]
    )
    track = factories.MemberTrackFactory.create(
        name=TrackName.PREGNANCY,
        user=default_user,
    )
    factories.AssessmentTrackFactory.create(
        assessment_onboarding_slug="test-slug", track_name=TrackName.PREGNANCY
    )

    res = client.get(
        f"/api/v1/tracks/{track.id}/onboarding_assessment",
        headers=api_helpers.standard_headers(default_user),
    )
    json = api_helpers.load_json(res)

    assert (
        json["onboarding_assessment_id"]
        == track.onboarding_assessment_lifecycle.latest_assessment.id
    )
    assert json["onboarding_assessment_slug"] == "test-slug"


def test_get_onboarding_assessment_returns_404_when_track_doesnt_exist(
    client, api_helpers, default_user, factories
):
    res = client.get(
        "/api/v1/tracks/123123/onboarding_assessment",
        headers=api_helpers.standard_headers(default_user),
    )

    assert res.status_code == 404


def test_get_onboarding_assessment_returns_404_when_track_is_inactive(
    client, api_helpers, default_user, factories
):
    inactive_track = factories.MemberTrackFactory.create(
        user=default_user,
        ended_at=datetime.today() - timedelta(days=800),
    )

    res = client.get(
        f"/api/v1/tracks/{inactive_track.id}/onboarding_assessment",
        headers=api_helpers.standard_headers(default_user),
    )

    assert res.status_code == 404


def test_get_track_active_track(
    client_track: ClientTrack,
    set_up_member_tracks,
    client: FlaskClient,
    api_helpers: APIInteractionMixin,
    default_user: User,
    factories,
):
    member_track = factories.MemberTrackFactory.create(
        user=default_user, name=TrackName.PREGNANCY, client_track=client_track
    )

    response = client.get(
        f"/api/v1/-/tracks/{member_track.id}",
        headers=api_helpers.standard_headers(default_user),
    )

    assert response.status_code == 200
    assert api_helpers.load_json(response) == dataclasses.asdict(
        ActiveMemberTrack.from_member_track(member_track)
    )


def test_get_track_inactive_track(
    client_track: ClientTrack,
    set_up_member_tracks,
    client: FlaskClient,
    api_helpers: APIInteractionMixin,
    default_user: User,
    factories,
):
    member_track = factories.MemberTrackFactory.create(
        user=default_user,
        ended_at=datetime.today() - timedelta(days=2),
    )

    response = client.get(
        f"/api/v1/-/tracks/{member_track.id}",
        headers=api_helpers.standard_headers(default_user),
    )

    assert response.status_code == 200
    assert api_helpers.load_json(response) == dataclasses.asdict(
        InactiveMemberTrack.from_member_track(member_track)
    )


def test_get_track_scheduled_track(
    client_track: ClientTrack,
    set_up_member_tracks,
    client: FlaskClient,
    api_helpers: APIInteractionMixin,
    default_user: User,
    factories,
):
    member_track = factories.MemberTrackFactory.create(
        user=default_user, start_date=date.today() + timedelta(weeks=42)
    )
    member_track.activated_at = None

    response = client.get(
        f"/api/v1/-/tracks/{member_track.id}",
        headers=api_helpers.standard_headers(default_user),
    )

    assert response.status_code == 200
    assert api_helpers.load_json(response) == dataclasses.asdict(
        ScheduledMemberTrack.from_member_track(member_track)
    )


def test_get_track_invalid_track(
    client_track: ClientTrack,
    set_up_member_tracks,
    client: FlaskClient,
    api_helpers: APIInteractionMixin,
    default_user: User,
    factories,
):
    member_track = factories.MemberTrackFactory.create(
        user=default_user,
        ended_at=datetime.today() - timedelta(days=2),
    )
    member_track.activated_at = None

    response = client.get(
        f"/api/v1/-/tracks/{member_track.id}",
        headers=api_helpers.standard_headers(default_user),
    )

    assert response.status_code == 500


def test_get_track_track_does_not_exist(
    client_track: ClientTrack,
    set_up_member_tracks,
    client: FlaskClient,
    api_helpers: APIInteractionMixin,
    default_user: User,
    factories,
):
    response = client.get(
        "/api/v1/tracks/525600", headers=api_helpers.standard_headers(default_user)
    )

    assert response.status_code == 404


def test_get_track_member_has_no_tracks(
    client: FlaskClient, api_helpers: APIInteractionMixin, default_user: User, factories
):
    response = client.get(
        "/api/v1/tracks/1", headers=api_helpers.standard_headers(default_user)
    )

    assert response.status_code == 404


def test_get_track_track_belongs_to_another_user(
    client: FlaskClient, api_helpers: APIInteractionMixin, default_user: User, factories
):
    member_track = factories.MemberTrackFactory.create(
        user=factories.EnterpriseUserFactory.create(),
        ended_at=datetime.today() - timedelta(days=2),
    )
    response = client.get(
        f"/api/v1/tracks/{member_track.id}",
        headers=api_helpers.standard_headers(default_user),
    )

    assert response.status_code == 404


def test_get_track_not_authenticated(
    client_track: ClientTrack,
    set_up_member_tracks,
    client: FlaskClient,
    api_helpers: APIInteractionMixin,
    default_user: User,
    factories,
):
    member_track = factories.MemberTrackFactory.create(
        user=factories.EnterpriseUserFactory.create(),
        ended_at=datetime.today() - timedelta(days=2),
    )
    response = client.get(f"/api/v1/-/tracks/{member_track.id}")
    assert response.status_code == 401
