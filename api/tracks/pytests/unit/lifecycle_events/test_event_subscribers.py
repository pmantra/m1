from datetime import datetime, timezone
from unittest import mock
from unittest.mock import patch

from models.tracks.track import TrackName
from tracks.lifecycle_events.events_subscribers import (
    SECOND_TRACK_SELECTION_BRAZE_EVENT,
    TRACK_SELECTION_BRAZE_EVENT,
    send_braze_event_after_track_initiation,
    send_braze_event_after_track_transition,
)


@mock.patch("tracks.lifecycle_events.events_subscribers.send_braze_event")
@mock.patch("tracks.lifecycle_events.event_system.dispatch_initiate_event")
def test_after_insert_listener_two_tracks_pp_combo(
    mock_dispatch_initiate, mock_send_braze, factories
):
    user = factories.DefaultUserFactory.create()

    target_name = TrackName.FERTILITY
    org = factories.OrganizationFactory.create()
    client_track = factories.ClientTrackFactory.create(
        organization=org, track=target_name
    )

    from models.tracks import lifecycle

    with patch(
        "tracks.service.tracks.TrackSelectionService.validate_initiation"
    ) as mock_validate:
        mock_validate.return_value = client_track

        track1 = lifecycle.initiate(
            user=user,
            track=target_name,
            with_validation=True,
            eligibility_organization_id=org.id,
        )

    mock_dispatch_initiate.assert_called_with(track=track1, user=user)
    send_braze_event_after_track_initiation(track1.id, user.id)
    mock_send_braze.assert_not_called()
    mock_dispatch_initiate.reset_mock()

    target_name2 = TrackName.PARENTING_AND_PEDIATRICS
    client_track2 = factories.ClientTrackFactory.create(
        organization=org, track=target_name2
    )

    with patch(
        "tracks.service.tracks.TrackSelectionService.validate_initiation"
    ) as mock_validate:
        mock_validate.return_value = client_track2

        track2 = lifecycle.initiate(
            user=user,
            track=target_name2,
            with_validation=True,
            eligibility_organization_id=org.id,
        )

    mock_dispatch_initiate.assert_called_with(track=track2, user=user)

    send_braze_event_after_track_initiation(track2.id, user.id)
    mock_send_braze.assert_called_once_with(
        external_id=str(track2.id),
        event_name=SECOND_TRACK_SELECTION_BRAZE_EVENT,
        properties={
            "first_track": track1.name,
            "second_track": track2.name,
        },
    )


@mock.patch("tracks.lifecycle_events.events_subscribers.send_braze_event")
@mock.patch("tracks.lifecycle_events.event_system.dispatch_initiate_event")
def test_after_insert_listener_single_track_new(
    mock_dispatch_initiate, mock_send_braze, factories
):
    user = factories.DefaultUserFactory.create()

    target_name = TrackName.FERTILITY
    org = factories.OrganizationFactory.create()
    client_track = factories.ClientTrackFactory.create(
        organization=org, track=target_name
    )

    from models.tracks import lifecycle

    with patch(
        "tracks.service.tracks.TrackSelectionService.validate_initiation"
    ) as mock_validate:
        mock_validate.return_value = client_track

        track = lifecycle.initiate(
            user=user,
            track=target_name,
            with_validation=True,
            eligibility_organization_id=org.id,
        )

    mock_send_braze.reset_mock()

    send_braze_event_after_track_initiation(track.id, user.id)

    # Verify that no event is sent for first track with no inactive tracks
    mock_send_braze.assert_not_called()


@mock.patch("tracks.lifecycle_events.events_subscribers.send_braze_event")
@mock.patch("tracks.lifecycle_events.event_system.dispatch_initiate_event")
def test_after_insert_listener_single_track_with_inactive(
    mock_dispatch_initiate, mock_send_braze, factories
):
    user = factories.DefaultUserFactory.create()

    target_name = TrackName.FERTILITY
    org = factories.OrganizationFactory.create()
    client_track = factories.ClientTrackFactory.create(
        organization=org, track=target_name
    )

    from models.tracks import lifecycle

    track1 = factories.MemberTrackFactory.create(
        user=user,
        name=TrackName.ADOPTION,
    )
    track1.ended_at = datetime.now(timezone.utc)

    with patch(
        "tracks.service.tracks.TrackSelectionService.validate_initiation"
    ) as mock_validate:
        mock_validate.return_value = client_track

        track2 = lifecycle.initiate(
            user=user,
            track=target_name,
            with_validation=True,
            eligibility_organization_id=org.id,
        )

    mock_send_braze.reset_mock()

    send_braze_event_after_track_initiation(track2.id, user.id)
    mock_send_braze.assert_called_once_with(
        external_id=str(track2.id),
        event_name=TRACK_SELECTION_BRAZE_EVENT,
        properties={
            "primary_track": track2.name,
            "secondary_track": None,
            "multitrack_at_onboarding": False,
        },
    )


@mock.patch("tracks.lifecycle_events.events_subscribers.send_braze_event")
def test_track_transition_simplified(mock_send_braze, factories):
    user = factories.DefaultUserFactory.create()

    source_track = factories.MemberTrackFactory.create(
        user=user,
        name=TrackName.FERTILITY,
    )

    target_track = factories.MemberTrackFactory.create(
        user=user,
        name=TrackName.PREGNANCY,
    )

    send_braze_event_after_track_transition(source_track.id, target_track.id, user.id)

    mock_send_braze.assert_called_once_with(
        external_id=str(target_track.id),
        event_name=TRACK_SELECTION_BRAZE_EVENT,
        properties={
            "primary_track": target_track.name,
            "last_track": source_track.name,
            "multitrack_at_onboarding": False,
            "secondary_track": None,
        },
    )
