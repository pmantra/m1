from contextlib import nullcontext as does_not_raise
from datetime import date, timedelta
from unittest import mock
from unittest.mock import ANY, patch

import pytest
from marshmallow import ValidationError

from models.tracks import TrackConfig, TrackName, get_track, validate_names
from models.tracks.client_track import TrackModifiers
from storage.connection import db

today = date.today()


@pytest.mark.parametrize(
    argnames="active,launch_date,expected",
    argvalues=[
        (True, None, True),  # default launch date = None
        (True, today, True),
        (True, today - timedelta(weeks=1), True),  # past launch date
        (True, today + timedelta(weeks=1), False),  # future launch date
        (False, None, False),  # inactive track without launch date
        (False, today, False),  # inactive track with launch date
    ],
)
def test_launch_dates(active, launch_date, expected, factories):
    client_track = factories.ClientTrackFactory.create(
        active=active, launch_date=launch_date
    )
    assert client_track.is_available_to_members == expected


def test_client_track_is_extended(default_user, factories):
    options = {"Short": 90, "Medium": 180, "Long": 365}
    postpartum_with_custom_lengths = {
        **get_track(TrackName.POSTPARTUM).__dict__,
        "length_in_days_options": options,
    }
    track_config = TrackConfig(**postpartum_with_custom_lengths)

    long_track = factories.MemberTrackFactory.create(
        name=TrackName.POSTPARTUM, client_track__length_in_days=options["Long"]
    )
    short_track = factories.MemberTrackFactory.create(
        name=TrackName.POSTPARTUM, client_track__length_in_days=options["Short"]
    )
    with patch(
        "models.tracks.client_track.ClientTrack._config",
        new_callable=lambda: track_config,
    ):
        assert long_track.is_extended
        assert not short_track.is_extended


def test_client_track_is_extended_with_only_one_length(default_user, factories):
    options = {"Default": 90}
    postpartum_with_custom_lengths = {
        **get_track(TrackName.PREGNANCY).__dict__,
        "length_in_days_options": options,
    }
    track_config = TrackConfig(**postpartum_with_custom_lengths)

    member_track = factories.MemberTrackFactory.create(
        name=TrackName.PREGNANCY, client_track__length_in_days=options["Default"]
    )
    with patch(
        "models.tracks.client_track.ClientTrack._config",
        new_callable=lambda: track_config,
    ):
        assert not member_track.is_extended


@pytest.mark.parametrize(
    "is_doula_only_track,track_modifiers,expected_track_modifiers_list",
    [
        (True, "doula_only", [TrackModifiers.DOULA_ONLY]),
        (False, None, []),
    ],
)
@mock.patch("models.tracks.client_track.should_enable_doula_only_track")
def test_client_track_track_modifiers_list(
    mock_should_enable_doula_only_track,
    is_doula_only_track,
    track_modifiers,
    expected_track_modifiers_list,
    default_user,
    factories,
):

    # Given
    client_track = factories.ClientTrackFactory.create(
        track="pregnancy", track_modifiers=track_modifiers
    )

    # When/Then
    mock_should_enable_doula_only_track.return_value = is_doula_only_track

    if is_doula_only_track:
        assert client_track.track_modifiers_list == expected_track_modifiers_list
    else:
        assert client_track.track_modifiers_list == []


@mock.patch("models.tracks.client_track.should_enable_doula_only_track")
def test_client_track_track_modifiers_list__value_error(
    mock_should_enable_doula_only_track, factories
):
    # Given
    invalid_track_modifier = "ca_only"
    client_track = factories.ClientTrackFactory.create(
        track="pregnancy", track_modifiers=invalid_track_modifier
    )

    # When/ Then
    # assert we raise a ValueError when we attempt to map an invalid value to the TrackModifiers enum
    with pytest.raises(ValueError):
        assert client_track.track_modifiers_list == ["Test"]


class TestValidateNames:
    @pytest.mark.parametrize(
        argnames="valid_track_names",
        argvalues=[
            ["pregnancy"],
            ["pregnancy", "adoption"],
        ],
    )
    def test_validate_names__valid(self, valid_track_names):
        # Given valid track_names

        # When
        are_valid_names = validate_names(valid_track_names)

        # Then
        assert are_valid_names

    @pytest.mark.parametrize(
        argnames="invalid_track_names",
        argvalues=[["something_ivalid"], ["pregnancy", "something_ivalid"]],
    )
    def test_validate_names__invalid(self, invalid_track_names):
        # Given invalid track names

        # Then
        with pytest.raises(ValidationError):
            # When
            validate_names(invalid_track_names)


class TestValidateTrackModifiers:
    @pytest.mark.parametrize(
        "track_name,expected_response",
        [
            ("pregnancy", does_not_raise()),
            ("fertility", pytest.raises(ValueError)),
        ],
    )
    def test_validate_track_modifiers__with_doula_only_modifier(
        self, track_name, expected_response, factories
    ):
        # Given
        client_track = factories.ClientTrackFactory.create(track=track_name)

        # When/Then
        with expected_response:
            client_track.track_modifiers = "doula_only"

    @pytest.mark.parametrize(
        "track_name,expected_response",
        [
            ("pregnancy", does_not_raise()),
            ("fertility", does_not_raise()),
        ],
    )
    def test_validate_track_modifiers__wihtout_doula_only_modifier(
        self, track_name, expected_response, factories
    ):
        # Given
        client_track = factories.ClientTrackFactory.create(track=track_name)

        # When/Then
        with expected_response:
            client_track.track_modifiers = None


class TestClientTrackListeners:
    @mock.patch("messaging.services.zendesk.update_zendesk_org.delay")
    def test_update_organization_on_track_creation(
        self,
        mock_update_zd_org,
        factories,
    ):
        # Given
        # When - new org + track
        org = factories.OrganizationFactory.create()
        mock_update_zd_org.reset_mock()
        track = factories.ClientTrackFactory.create(
            organization=org, track=TrackName.ADOPTION
        )
        db.session.commit()

        # then
        mock_update_zd_org.assert_called_once_with(
            org.id, org.name, ANY, org.US_restricted, track.name
        )

    @mock.patch("messaging.services.zendesk.update_zendesk_org.delay")
    def test_update_organization_on_track_update(
        self,
        mock_update_zd_org,
        factories,
    ):
        # Given org + track
        org = factories.OrganizationFactory.create()
        track_1 = factories.ClientTrackFactory.create(
            organization=org, track=TrackName.ADOPTION
        )
        track_2 = factories.ClientTrackFactory.create(
            organization=org, track=TrackName.PREGNANCY
        )
        db.session.commit()

        # When - clear mocks + make track inactive
        mock_update_zd_org.reset_mock()
        track_1.active = 0
        db.session.commit()

        # then
        mock_update_zd_org.assert_called_once_with(
            org.id, org.name, ANY, org.US_restricted, track_1.name
        )
        call_args = mock_update_zd_org.call_args[0]
        assert call_args[2][0].active == track_1.active
        assert call_args[2][0].name == track_1.name
        assert call_args[2][0].display_name == track_1.display_name
        assert call_args[2][1].active == track_2.active
        assert call_args[2][1].name == track_2.name
        assert call_args[2][1].display_name == track_2.display_name
