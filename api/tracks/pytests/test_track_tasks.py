import re
from datetime import datetime, timedelta
from unittest import mock
from unittest.mock import MagicMock, patch

import pytest
from google.protobuf.wrappers_pb2 import Int64Value
from maven.feature_flags import test_data

from common.health_profile.health_profile_service_models import ClinicalStatus
from eligibility import service
from models.tracks import (
    ChangeReason,
    IncompatibleTrackError,
    MismatchedOrganizationError,
    MissingInformationError,
    TrackDateConfigurationError,
    TrackLifecycleError,
    TrackName,
    TransitionNotConfiguredError,
    lifecycle,
)
from models.tracks.member_track import MemberTrackPhaseReporting
from pytests import factories
from pytests.freezegun import freeze_time
from storage.connection import db
from tasks.tracks import (
    auto_transition_or_terminate_member_tracks,
    auto_transition_or_terminate_member_tracks_coordinator,
    ensure_track_state,
    ensure_track_state_coordinator,
    update_current_track_phase,
    update_member_track_phase_history,
    update_member_track_phase_history_coordinator,
    update_pregnancy_in_hps,
)
from utils.exceptions import ProgramLifecycleError


@pytest.fixture
def mock_auto_transition_or_terminate_member_tracks_delay():
    with mock.patch("tasks.tracks.auto_transition_or_terminate_member_tracks") as p:
        mock_delay = MagicMock()
        p.delay = mock_delay
        yield mock_delay


@pytest.mark.parametrize(
    argnames="chunk_size,track_count,expected_executions",
    argvalues=[(2, 1, 1), (1_000, 2_001, 3), (1_000, 3_001, 4)],
)
def test_auto_transition_or_terminate_member_tracks_coordinator(
    chunk_size,
    track_count,
    expected_executions,
    mock_auto_transition_or_terminate_member_tracks_delay,
):

    with mock.patch(
        "tasks.tracks.get_tracks_past_scheduled_end_count"
    ) as get_tracks_past_scheduled_end_count:
        get_tracks_past_scheduled_end_count.return_value = track_count

        auto_transition_or_terminate_member_tracks_coordinator(chunk_size=chunk_size)

        assert (
            mock_auto_transition_or_terminate_member_tracks_delay.call_count
            == expected_executions
        )


@pytest.fixture
def mock_pregnancy_update_functions():
    """Fixture to mock pregnancy update-related functions for all auto transition tests"""
    with mock.patch(
        "tasks.tracks.update_pregnancy_in_hps"
    ) as mock_update_pregnancy, mock.patch(
        "tasks.tracks.get_should_update_pregnancy_in_hps", return_value=False
    ):

        mock_update_pregnancy.delay = MagicMock()
        yield mock_update_pregnancy


def test_auto_transition_or_terminate_member_tracks__auto_transition(
    factories, mock_pregnancy_update_functions
):
    track = factories.MemberTrackFactory.create(
        name=TrackName.PREGNANCY,
        transitioning_to=TrackName.POSTPARTUM,
        anchor_date=datetime.utcnow().date() - timedelta(days=400),
    )
    factories.ClientTrackFactory.create(
        organization=track.client_track.organization,
        track=TrackName.POSTPARTUM,
    )

    user = track.user
    user.health_profile.json.pop("children")
    user.health_profile.due_date = datetime.utcnow().date() - timedelta(weeks=1)

    assert len(user.active_tracks) == 1
    assert not user.inactive_tracks
    assert not user.scheduled_tracks

    auto_transition_or_terminate_member_tracks()

    db.session.expire_all()

    assert len(user.active_tracks) == 1
    active_track = user.active_tracks[0]
    assert active_track.name == TrackName.POSTPARTUM

    assert len(user.inactive_tracks) == 1
    inactive_track = user.inactive_tracks[0]
    assert track is inactive_track

    assert not user.scheduled_tracks


@pytest.mark.parametrize(
    "exception_type", [TrackLifecycleError, ProgramLifecycleError, Exception]
)
def test_auto_transition_or_terminate_member_tracks__auto_transition_exception(
    exception_type, mock_pregnancy_update_functions
):
    track = factories.MemberTrackFactory.create(
        name=TrackName.PREGNANCY,
        transitioning_to=TrackName.POSTPARTUM,
    )

    user = track.user
    assert len(user.active_tracks) == 1
    assert not user.inactive_tracks
    assert not user.scheduled_tracks

    with mock.patch("tasks.tracks.transition") as mock_transition:
        mock_transition.side_effect = exception_type

        auto_transition_or_terminate_member_tracks()

        db.session.expire_all()

        assert len(user.active_tracks) == 1
        active_track = user.active_tracks[0]
        assert track is active_track

        assert not user.inactive_tracks
        assert not user.scheduled_tracks


def test_auto_transition_or_terminate_member_tracks__auto_transition_not_supported_in_org(
    factories, mock_pregnancy_update_functions
):
    track = factories.MemberTrackFactory.create(
        name=TrackName.PREGNANCY,
        transitioning_to=TrackName.POSTPARTUM,
        anchor_date=datetime.utcnow().date() - timedelta(days=400),
    )

    user = track.user
    user.health_profile.json.pop("children")
    user.health_profile.due_date = datetime.utcnow().date() - timedelta(weeks=1)

    assert len(user.active_tracks) == 1
    assert not user.inactive_tracks
    assert not user.scheduled_tracks

    auto_transition_or_terminate_member_tracks()

    db.session.expire_all()

    assert len(user.active_tracks) == 0
    assert len(user.inactive_tracks) == 1
    inactive_track = user.inactive_tracks[0]
    assert track is inactive_track


@pytest.mark.parametrize(
    argnames="start_date",
    argvalues=(datetime.utcnow().date(), datetime.utcnow().date() - timedelta(days=1)),
)
def test_auto_transition_or_terminate_member_tracks__terminate_with_renewal(
    start_date, mock_pregnancy_update_functions
):
    ending_track = factories.MemberTrackFactory.create(
        name=TrackName.SURROGACY,
        anchor_date=datetime.utcnow().date() - timedelta(days=400),
    )
    user = ending_track.user

    scheduled_track = factories.MemberTrackFactory.create(
        user=user,
        name=TrackName.SURROGACY,
        start_date=start_date,
        previous_member_track_id=ending_track.id,
    )

    scheduled_track.activated_at = None

    db.session.refresh(user)

    assert len(user.active_tracks) == 1
    assert ending_track in user.active_tracks

    assert not user.inactive_tracks

    assert len(user.scheduled_tracks) == 1
    assert scheduled_track in user.scheduled_tracks

    with mock.patch.object(
        service.EnterpriseVerificationService, "is_user_known_to_be_eligible_for_org"
    ) as mock_is_user_known_to_be_eligible_for_org:
        mock_is_user_known_to_be_eligible_for_org.return_value = True

        auto_transition_or_terminate_member_tracks()

        db.session.expire_all()

        assert len(user.active_tracks) == 1
        active_track = user.active_tracks[0]
        assert scheduled_track is active_track

        assert len(user.inactive_tracks) == 1
        inactive_track = user.inactive_tracks[0]
        assert ending_track is inactive_track

        assert not user.scheduled_tracks


@pytest.mark.parametrize(
    argnames="start_date",
    argvalues=(datetime.utcnow().date(), datetime.utcnow().date() - timedelta(days=1)),
)
def test_auto_transition_or_terminate_member_tracks__terminate_with_renewal_updates_sub_population_id(
    start_date, verification_service, mock_pregnancy_update_functions
):
    ending_track = factories.MemberTrackFactory.create(
        name=TrackName.SURROGACY,
        anchor_date=datetime.utcnow().date() - timedelta(days=400),
    )
    user = ending_track.user

    scheduled_track = factories.MemberTrackFactory.create(
        user=user,
        name=TrackName.SURROGACY,
        start_date=start_date,
        previous_member_track_id=ending_track.id,
        sub_population_id=73570,
    )
    scheduled_track.activated_at = None
    db.session.refresh(user)

    assert len(user.active_tracks) == 1
    assert ending_track in user.active_tracks

    assert not user.inactive_tracks

    assert len(user.scheduled_tracks) == 1
    assert scheduled_track in user.scheduled_tracks
    assert scheduled_track.sub_population_id == 73570

    verification_service.e9y.grpc.get_sub_population_id_for_user_and_org.return_value = Int64Value(
        value=73571
    )
    with mock.patch.object(
        service.EnterpriseVerificationService, "is_user_known_to_be_eligible_for_org"
    ) as mock_is_user_known_to_be_eligible_for_org:
        mock_is_user_known_to_be_eligible_for_org.return_value = True

        auto_transition_or_terminate_member_tracks()

        db.session.expire_all()

        assert len(user.active_tracks) == 1
        active_track = user.active_tracks[0]
        assert scheduled_track is active_track
        assert scheduled_track.sub_population_id == 73571

        assert len(user.inactive_tracks) == 1
        inactive_track = user.inactive_tracks[0]
        assert ending_track is inactive_track

        assert not user.scheduled_tracks


def test_auto_transition_or_terminate_member_tracks__terminate_with_renewal_but_ineligible(
    mock_pregnancy_update_functions,
):
    ending_track = factories.MemberTrackFactory.create(
        name=TrackName.SURROGACY,
        anchor_date=datetime.utcnow().date() - timedelta(days=400),
    )
    user = ending_track.user

    scheduled_track = factories.MemberTrackFactory.create(
        user=user,
        name=TrackName.SURROGACY,
        start_date=datetime.utcnow().date(),
        previous_member_track_id=ending_track.id,
    )
    scheduled_track.activated_at = None
    db.session.refresh(user)

    assert len(user.active_tracks) == 1
    assert ending_track in user.active_tracks

    assert not user.inactive_tracks

    assert len(user.scheduled_tracks) == 1
    assert scheduled_track in user.scheduled_tracks

    with mock.patch.object(
        service.EnterpriseVerificationService, "is_user_known_to_be_eligible_for_org"
    ) as mock_is_user_known_to_be_eligible_for_org:
        mock_is_user_known_to_be_eligible_for_org.return_value = False

        auto_transition_or_terminate_member_tracks()

        db.session.expire_all()

        assert not user.active_tracks

        assert len(user.inactive_tracks) == 1
        inactive_track_1 = user.inactive_tracks[0]
        assert ending_track is inactive_track_1

        assert not user.scheduled_tracks


def test_auto_transition_or_terminate_member_tracks__terminate_no_renewal(
    mock_pregnancy_update_functions,
):
    ending_track = factories.MemberTrackFactory.create(
        name=TrackName.SURROGACY,
        anchor_date=datetime.utcnow().date() - timedelta(days=400),
    )
    user = ending_track.user

    assert len(user.active_tracks) == 1
    assert ending_track in user.active_tracks

    assert not user.inactive_tracks

    assert not user.scheduled_tracks

    with mock.patch.object(
        service.EnterpriseVerificationService, "is_user_known_to_be_eligible_for_org"
    ) as mock_is_user_known_to_be_eligible_for_org:
        mock_is_user_known_to_be_eligible_for_org.return_value = True

        auto_transition_or_terminate_member_tracks()

        db.session.expire_all()

        assert not user.active_tracks

        assert len(user.inactive_tracks) == 1
        inactive_track = user.inactive_tracks[0]
        assert ending_track is inactive_track

        assert not user.scheduled_tracks


@pytest.mark.parametrize(
    "exception_type",
    [
        TrackDateConfigurationError,
        TransitionNotConfiguredError,
        MissingInformationError,
        IncompatibleTrackError,
        MismatchedOrganizationError,
        ProgramLifecycleError,
        Exception,
    ],
)
def test_auto_transition_or_terminate_member_tracks__terminate_error(
    exception_type, mock_pregnancy_update_functions
):
    ending_track = factories.MemberTrackFactory.create(
        name=TrackName.SURROGACY,
        anchor_date=datetime.utcnow().date() - timedelta(days=400),
    )
    user = ending_track.user

    assert len(user.active_tracks) == 1
    assert ending_track in user.active_tracks

    assert not user.inactive_tracks

    assert not user.scheduled_tracks

    with mock.patch("tasks.tracks.terminate") as mock_terminate:
        mock_terminate.side_effect = exception_type

        with pytest.raises(
            Exception,
            match=re.escape("Error encountered handling scheduled track transitions."),
        ):
            auto_transition_or_terminate_member_tracks()

        db.session.expire_all()

        assert len(user.active_tracks) == 1
        assert ending_track in user.active_tracks

        assert not user.inactive_tracks
        assert not user.scheduled_tracks


def test_auto_transition_or_terminate_member_tracks__ignores_empty_user(
    mock_pregnancy_update_functions,
):
    ending_track_with_user = factories.MemberTrackFactory.create(
        name=TrackName.SURROGACY,
        anchor_date=datetime.utcnow().date() - timedelta(days=400),
    )
    ending_track_without_user = factories.MemberTrackFactory.create(
        name=TrackName.SURROGACY,
        anchor_date=datetime.utcnow().date() - timedelta(days=400),
    )
    ending_track_without_user.user_id = 0

    with mock.patch("tasks.tracks.terminate") as mock_terminate:
        auto_transition_or_terminate_member_tracks()

        mock_terminate.assert_called_once_with(
            ending_track_with_user, change_reason=ChangeReason.AUTO_JOB_TERMINATE
        )


def test_auto_transition_or_terminate_member_tracks__multiple_tracks(
    mock_pregnancy_update_functions,
):
    factories.MemberTrackFactory.create(
        name=TrackName.SURROGACY,
        anchor_date=datetime.utcnow().date() - timedelta(days=400),
    )

    factories.MemberTrackFactory.create(
        name=TrackName.ADOPTION,
        anchor_date=datetime.utcnow().date() - timedelta(days=400),
    )

    with mock.patch(
        "tasks.tracks.handle_auto_transition_or_terminate_member_tracks"
    ) as mock_handle:
        mock_handle.side_effect = [True, False]

        with pytest.raises(
            Exception,
            match=re.escape("Error encountered handling scheduled track transitions."),
        ):
            auto_transition_or_terminate_member_tracks()


@pytest.fixture
def mock_ensure_track_state_delay():
    with mock.patch("tasks.tracks.ensure_track_state") as p:
        mock_delay = MagicMock()
        p.delay = mock_delay
        yield mock_delay


@pytest.mark.parametrize(
    argnames="chunk_size,active_track_count,expected_executions",
    argvalues=[(2, 1, 1), (1_000, 2_001, 3), (1_000, 3_001, 4)],
)
def test_ensure_track_state_coordinator(
    chunk_size, active_track_count, expected_executions, mock_ensure_track_state_delay
):

    with mock.patch(
        "tasks.tracks.get_active_track_query_count"
    ) as get_active_track_query_count:
        get_active_track_query_count.return_value = active_track_count

        ensure_track_state_coordinator(chunk_size)

        assert mock_ensure_track_state_delay.call_count == expected_executions


@pytest.mark.parametrize(
    "exception_type",
    [
        TrackDateConfigurationError,
        TransitionNotConfiguredError,
        MissingInformationError,
        IncompatibleTrackError,
        MismatchedOrganizationError,
        ProgramLifecycleError,
        Exception,
    ],
)
def test_ensure_track_state__check_track_state_error(exception_type):
    tracks_count = 5

    for _ in range(tracks_count):
        factories.MemberTrackFactory.create(
            name=TrackName.SURROGACY,
        )

    with mock.patch("tasks.tracks.check_track_state") as mock_check_track_state:
        mock_check_track_state.side_effect = exception_type

        with pytest.raises(
            Exception, match=re.escape("Error encountered while ensuring track state.")
        ):
            ensure_track_state()

        assert mock_check_track_state.call_count == tracks_count


@pytest.mark.parametrize(
    argnames="chunk,chunk_size,active_track_count,expected_executions",
    argvalues=[(0, 2, 4, 2), (0, 4, 2, 2), (1, 2, 3, 1)],
)
def test_ensure_track_state_chunk(
    chunk, chunk_size, active_track_count, expected_executions
):
    for _ in range(active_track_count):
        factories.MemberTrackFactory.create(
            name=TrackName.SURROGACY,
        )

    track_without_user = factories.MemberTrackFactory.create(
        name=TrackName.SURROGACY,
    )
    track_without_user.user_id = 0

    with mock.patch("tasks.tracks.check_track_state") as mock_check_track_state:
        ensure_track_state(chunk=chunk, chunk_size=chunk_size)

        assert mock_check_track_state.call_count == expected_executions


@pytest.fixture
def mock_update_member_track_phase_history_delay():
    with mock.patch("tasks.tracks.update_member_track_phase_history") as p:
        mock_delay = MagicMock()
        p.delay = mock_delay
        yield mock_delay


@pytest.mark.parametrize(
    argnames="chunk_size,active_track_count,expected_executions",
    argvalues=[(2, 1, 1), (1_000, 2_001, 3), (1_000, 3_001, 4)],
)
def test_update_member_track_phase_history_coordinator(
    chunk_size,
    active_track_count,
    expected_executions,
    mock_update_member_track_phase_history_delay,
):

    with mock.patch(
        "tasks.tracks.get_active_track_query_count"
    ) as get_active_track_query_count:
        get_active_track_query_count.return_value = active_track_count

        update_member_track_phase_history_coordinator(chunk_size)

        assert (
            mock_update_member_track_phase_history_delay.call_count
            == expected_executions
        )


@mock.patch("tracks.service.tracks.TrackSelectionService.validate_initiation")
def test_member_track_phase_reporting(mock_validate_initiation):
    user = factories.DefaultUserFactory.create()
    org = factories.OrganizationFactory.create(allowed_tracks=[TrackName.FERTILITY])
    mock_validate_initiation.return_value = factories.ClientTrackFactory.create(
        track=TrackName.FERTILITY, organization=org
    )

    # TODO: is there a way we could use a "generic" weekly track here instead of
    #  forcing fertility?
    client_track_1 = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.FERTILITY
    )
    with mock.patch(
        "tracks.service.tracks.TrackSelectionService.validate_initiation",
        return_value=client_track_1,
    ):
        lifecycle.initiate(
            user,
            track=TrackName.FERTILITY,
            eligibility_organization_id=org.id,
        )

        # Should be one phase created during initiate
        phase_count = db.session.query(MemberTrackPhaseReporting).count()
        assert phase_count == 1

        # For every one of the next 9 days, run phase reporting job
        for i in range(0, 9):
            with freeze_time(datetime.utcnow() + timedelta(days=i)):
                update_member_track_phase_history()

        phases = (
            db.session.query(MemberTrackPhaseReporting)
            .order_by(MemberTrackPhaseReporting.created_at)
            .all()
        )
        assert len(phases) == 2
        assert [phase.name for phase in phases] == ["week-1", "week-2"]
        assert phases[1].started_at == datetime.utcnow().date() + timedelta(days=7)


def test_braze_export_during_phase_reporting_with_braze_enabled(mock_queue):
    track = factories.MemberTrackFactory.create()
    mock_queue.enqueue.reset_mock()

    # For every one of the next 9 days, run phase reporting job
    for i in range(0, 9):
        with test_data() as td, freeze_time(datetime.utcnow() + timedelta(days=i)):
            td.update(td.flag("kill-switch-braze-api-requests").variation_for_all(True))

            update_member_track_phase_history()

    phases = db.session.query(MemberTrackPhaseReporting).all()
    calls = mock_queue.enqueue.call_args_list
    braze_tracking_calls = [
        args for args, _ in calls if args[0] == update_current_track_phase
    ]
    # Braze tracking should be called once per phase
    assert len(braze_tracking_calls) == len(phases)
    assert all(args[1] == track.id for args in braze_tracking_calls)


def test_braze_export_during_phase_reporting_with_braze_disabled(mock_queue):
    factories.MemberTrackFactory.create()
    mock_queue.enqueue.reset_mock()

    # For every one of the next 9 days, run phase reporting job
    for i in range(0, 9):
        with test_data() as td, freeze_time(datetime.utcnow() + timedelta(days=i)):
            td.update(
                td.flag("kill-switch-braze-api-requests").variation_for_all(False)
            )

            update_member_track_phase_history()

    calls = mock_queue.enqueue.call_args_list
    braze_tracking_calls = [
        args for args, _ in calls if args[0] == update_current_track_phase
    ]

    assert len(braze_tracking_calls) == 0


@pytest.mark.parametrize(
    "exception_type", [TrackLifecycleError, ProgramLifecycleError, Exception]
)
def test_update_pregnancy_in_hps(exception_type, factories):
    # Create user with pregnancy track and health profile
    track = factories.MemberTrackFactory.create(name=TrackName.PREGNANCY)
    user = track.user
    user.health_profile.due_date = datetime.utcnow().date()
    user_id = user.id

    # Set up mocks for the HPS interactions
    with patch(
        "tasks.tracks.HealthProfileServiceClient"
    ) as mock_hps_client_class, patch(
        "tasks.tracks.get_or_create_pregnancy"
    ) as mock_get_pregnancy, patch(
        "tasks.tracks.log"
    ) as mock_log:

        # Set up mock pregnancy
        mock_hps_client = MagicMock()
        mock_hps_client_class.return_value = mock_hps_client
        mock_pregnancy = MagicMock()
        mock_pregnancy.id = "preg-123"
        mock_pregnancy.estimated_date = datetime.utcnow().date()
        mock_get_pregnancy.return_value = mock_pregnancy

        # Call the function
        update_pregnancy_in_hps(user_id, datetime.utcnow())

        # Verify health profile client created
        mock_hps_client_class.assert_called_once()

        # Verify get_or_create_pregnancy called
        mock_get_pregnancy.assert_called_once()

        # Verify pregnancy status updated
        assert mock_pregnancy.status == ClinicalStatus.RESOLVED

        # Verify put_pregnancy called
        mock_hps_client.put_pregnancy.assert_called_once_with(mock_pregnancy)

        # Verify log message
        mock_log.info.assert_called_with("update_pregnancy_in_hps finished")


def test_update_pregnancy_in_hps_no_due_date(factories):
    # Create user with pregnancy track but no due date
    track = factories.MemberTrackFactory.create(name=TrackName.PREGNANCY)
    user = track.user
    user.health_profile.due_date = None
    user_id = user.id

    # Set up mocks for the HPS interactions
    with patch(
        "tasks.tracks.HealthProfileServiceClient"
    ) as mock_hps_client_class, patch(
        "tasks.tracks.get_or_create_pregnancy"
    ) as mock_get_pregnancy, patch(
        "tasks.tracks.log"
    ) as mock_log:

        # Set up mock pregnancy with no estimated date
        mock_hps_client = MagicMock()
        mock_hps_client_class.return_value = mock_hps_client
        mock_pregnancy = MagicMock()
        mock_pregnancy.estimated_date = None
        mock_get_pregnancy.return_value = mock_pregnancy

        # Call the function
        update_pregnancy_in_hps(user_id, None)

        # Verify health profile client created
        mock_hps_client_class.assert_called_once()

        # Verify get_or_create_pregnancy called
        mock_get_pregnancy.assert_called_once()

        # Verify put_pregnancy not called
        mock_hps_client.put_pregnancy.assert_not_called()

        # Verify warning log
        mock_log.warn.assert_called_once_with(
            f"update_pregnancy_in_hps skipped during auto transition because of no estimated date for user: {user_id}"
        )


def test_update_pregnancy_in_hps_user_not_found():
    # Use a non-existent user ID
    fake_user_id = 99999

    # Set up mock for the User query
    with patch("tasks.tracks.User") as mock_user_class, patch(
        "tasks.tracks.HealthProfileServiceClient"
    ) as mock_hps_client_class, patch("tasks.tracks.log") as mock_log:

        # Set User.query.get to return None
        mock_user_class.query.get.return_value = None

        # Call the function
        update_pregnancy_in_hps(fake_user_id, datetime.utcnow())

        # Verify User.query.get was called
        mock_user_class.query.get.assert_called_once_with(fake_user_id)

        # Verify HPS client was not created
        mock_hps_client_class.assert_not_called()

        # Verify error was logged
        mock_log.error.assert_called_once_with(
            f"update_pregnancy_in_hps skipping because no user was found for id {fake_user_id}"
        )


def test_update_pregnancy_in_hps_no_user_id():
    # Set up mock for the logger
    with patch("tasks.tracks.User") as mock_user_class, patch(
        "tasks.tracks.log"
    ) as mock_log:

        # Call the function with None
        update_pregnancy_in_hps(None, datetime.utcnow())

        # Verify User.query.get was NOT called
        mock_user_class.query.get.assert_not_called()

        # Verify error was logged
        mock_log.error.assert_called_once_with(
            "update_pregnancy_in_hps skipping because of no user id"
        )
