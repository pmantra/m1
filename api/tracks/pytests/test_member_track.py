from datetime import date, datetime, timedelta
from typing import Tuple
from unittest import mock

import pytest

from common import stats
from models.tracks.client_track import TrackModifiers
from models.tracks.lifecycle import terminate
from models.tracks.member_track import (
    AdoptionMemberTrack,
    BMSMemberTrack,
    EggFreezingMemberTrack,
    FertilityMemberTrack,
    GeneralWellnessMemberTrack,
    GenericMemberTrack,
    MemberTrack,
    MenopauseMemberTrack,
    ParentingMemberTrack,
    PartnerFertilityMemberTrack,
    PartnerPostpartumMemberTrack,
    PartnerPregnancyMemberTrack,
    PostpartumMemberTrack,
    PregnancyLossMemberTrack,
    PregnancyMemberTrack,
    PregnancyOptionsTrack,
    SponsoredMemberTrack,
    StaticMemberTrackMixin,
    SurrogacyMemberTrack,
    TryingToConceiveMemberTrack,
    WeeklyMemberTrackMixin,
)
from models.tracks.phase import PhaseNamePrefix
from models.tracks.track import PhaseType, TrackName, get_track
from pytests.freezegun import freeze_time
from storage.connection import db

ONE_WEEK = timedelta(weeks=1)
TODAY = datetime.utcnow()
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)


@pytest.mark.parametrize(argnames="name", argvalues=[*TrackName])
def test_validate_name(name: TrackName, default_user, org_employee, client_track):
    track = MemberTrack(
        name=name.value,
        user=default_user,
        client_track=client_track,
    )
    assert track.name == name


def test_validate_name_invalid(default_user, org_employee, client_track):
    with pytest.raises(ValueError):
        MemberTrack(
            name="foo",
            user=default_user,
            client_track=client_track,
        )


def test_validate_transitioning_to(default_user, org_employee, client_track):
    track = MemberTrack(
        name=TrackName.PREGNANCY,
        user=default_user,
        client_track=client_track,
    )
    target = track.transitions[0].name
    track.transitioning_to = target
    assert track.transitioning_to == target


def test_valid_needs(factories, db):
    user = factories.DefaultUserFactory.create()
    track = factories.MemberTrackFactory.create(user=user, name=TrackName.PREGNANCY)
    need = factories.NeedFactory.create()
    factories.NeedTrackFactory.create(
        track_name=track.name,
        need_id=need.id,
    )

    db.session.flush()

    need_from_track = track.needs[0]
    assert need_from_track == need


def test_valid_need_categories(factories, db):
    user = factories.DefaultUserFactory.create()
    track = factories.MemberTrackFactory.create(user=user, name=TrackName.PREGNANCY)
    need_category = factories.NeedCategoryFactory.create()
    factories.NeedCategoryTrackFactory.create(
        track_name=track.name,
        need_category_id=need_category.id,
    )

    db.session.flush()

    need_category_track = track.need_categories[0]
    assert need_category_track == need_category


def test_validate_transitioning_to_invalid(default_user, org_employee, client_track):
    track = MemberTrack(
        name=TrackName.PREGNANCY,
        user=default_user,
        client_track=client_track,
    )
    with pytest.raises(ValueError):
        track.transitioning_to = "foo"


@pytest.mark.parametrize(
    argnames="name,type",
    argvalues=[
        (TrackName.GENERIC, GenericMemberTrack),
        (TrackName.ADOPTION, AdoptionMemberTrack),
        (TrackName.BREAST_MILK_SHIPPING, BMSMemberTrack),
        (TrackName.EGG_FREEZING, EggFreezingMemberTrack),
        (TrackName.FERTILITY, FertilityMemberTrack),
        (TrackName.GENERAL_WELLNESS, GeneralWellnessMemberTrack),
        (TrackName.PARENTING_AND_PEDIATRICS, ParentingMemberTrack),
        (TrackName.PARTNER_FERTILITY, PartnerFertilityMemberTrack),
        (TrackName.PARTNER_NEWPARENT, PartnerPostpartumMemberTrack),
        (TrackName.PARTNER_PREGNANT, PartnerPregnancyMemberTrack),
        (TrackName.POSTPARTUM, PostpartumMemberTrack),
        (TrackName.PREGNANCY, PregnancyMemberTrack),
        (TrackName.PREGNANCYLOSS, PregnancyLossMemberTrack),
        (TrackName.SPONSORED, SponsoredMemberTrack),
        (TrackName.SURROGACY, SurrogacyMemberTrack),
        (TrackName.TRYING_TO_CONCEIVE, TryingToConceiveMemberTrack),
        (TrackName.PREGNANCY_OPTIONS, PregnancyOptionsTrack),
        (TrackName.MENOPAUSE, MenopauseMemberTrack),
    ],
)
def test_polymorphism(name, type, factories):
    track = factories.MemberTrackFactory.create(name=name)
    assert isinstance(track, type)


def test_partner_track_enabled(factories):
    # Given
    track: MemberTrack = factories.MemberTrackFactory.create(name="pregnancy")
    # When
    assert not track.partner_track_enabled
    factories.ClientTrackFactory.create(
        organization=track.organization, track=track.partner_track.name
    )
    # Then
    assert track.partner_track_enabled


_today = date.today()
_today_dt = datetime(_today.year, _today.month, _today.day)


@pytest.mark.parametrize(
    argnames="start", argvalues=[_today - timedelta(weeks=i) for i in range(10)]
)
def test_weekly_track_initial_phase(start: date, factories):
    start_dt = datetime(start.year, start.month, start.day)
    track: FertilityMemberTrack = factories.MemberTrackFactory.create(
        name="fertility",
        created_at=start_dt,
        anchor_date=start,
        start_date=start,
    )
    end = start + ONE_WEEK
    assert track.initial_phase.started_at == start
    assert track.initial_phase.ended_at is None if end > _today else end


def test_pregnancy_track_initial_phase(factories):
    # Given
    due_date = _today + timedelta(weeks=30)
    # When
    track: PregnancyMemberTrack = factories.MemberTrackFactory.create(
        name="pregnancy", created_at=_today_dt, user__health_profile__due_date=due_date
    )
    track.set_anchor_date()
    # Then
    entry_phase_week = int((track.created_at.date() - track.anchor_date) / ONE_WEEK) + 1
    assert track.initial_phase.started_at == track.created_at.date()
    assert track.initial_phase.name == f"week-{entry_phase_week}"  # week-9
    assert track.current_phase == track.initial_phase


@pytest.mark.parametrize(argnames="week", argvalues=[i for i in range(10)])
def test_weekly_track_current_phase(week: int, factories):
    # created_at = 1 day ago, 8 days ago, etc
    created_at = _today_dt - timedelta(days=(7 * week + 1))
    track: FertilityMemberTrack = factories.MemberTrackFactory.create(
        name="fertility",
        created_at=created_at,
        anchor_date=created_at.date(),
        start_date=created_at.date(),
    )

    start = created_at.date() + week * ONE_WEEK
    assert track.current_phase.started_at == start
    assert track.current_phase.ended_at is None
    assert track.current_phase.name == f"week-{week + 1}"


@pytest.mark.parametrize(
    argnames="created_at", argvalues=[_today_dt - timedelta(weeks=i) for i in range(10)]
)
def test_weekly_track_final_phase(created_at: datetime, factories):
    track: FertilityMemberTrack = factories.MemberTrackFactory.create(
        name="fertility", created_at=created_at, anchor_date=created_at.date()
    )
    track.ended_at = created_at + track._config.length
    end = track.ended_at.date()
    start = end - ONE_WEEK
    assert track.final_phase.started_at == start
    assert track.final_phase.ended_at == end


def test_weekly_final_phase_null(factories):
    track: FertilityMemberTrack = factories.MemberTrackFactory.create(name="fertility")
    assert track.final_phase is None


def test_weekly_current_is_initial(factories):
    track: FertilityMemberTrack = factories.MemberTrackFactory.create(name="fertility")
    assert track.current_phase is track.initial_phase


def test_weekly_current_is_final(factories):
    created_at = _today_dt - timedelta(weeks=2)
    track: FertilityMemberTrack = factories.MemberTrackFactory.create(
        name="fertility", created_at=created_at, anchor_date=created_at.date()
    )
    track.ended_at = _today_dt
    assert track.current_phase is track.final_phase


def test_pregnancy_current_is_final(factories):
    # Given
    due_date = _today - timedelta(weeks=4)
    # When
    track: PregnancyMemberTrack = factories.MemberTrackFactory.create(
        name="pregnancy",
        created_at=_today_dt - timedelta(weeks=23),
        user__health_profile__due_date=due_date,
    )
    track.set_anchor_date()
    with freeze_time(_today_dt - timedelta(weeks=1)):
        terminate(track)
    # Then
    assert track.current_phase is track.final_phase
    assert track.final_phase.name == "week-42"


def test_weekly_initial_is_final_and_current(factories):
    track: FertilityMemberTrack = factories.MemberTrackFactory.create(name="fertility")

    track.ended_at = _today_dt
    # any change to the track dates must expire all of the the cached values
    track.expire_phases()

    assert track.initial_phase is track.final_phase is track.current_phase


def test_weekly_end_phase(factories):
    # Given
    track: FertilityMemberTrack = factories.MemberTrackFactory.create(name="fertility")

    # When
    track.anchor_date -= track._config.length + (ONE_WEEK * 3)
    # any change to the track dates must expire all of the the cached values
    track.expire_phases()

    # Then
    assert track.current_phase.name == PhaseNamePrefix.END


def get_pregnancy_member_track(factories) -> Tuple[PregnancyMemberTrack, date, date]:
    # Given
    due_date = date.today()
    scheduled_end_date = due_date + timedelta(weeks=3)
    # When
    track: PregnancyMemberTrack = factories.MemberTrackFactory.create(
        name="pregnancy", user__health_profile__due_date=due_date
    )
    track.set_anchor_date()
    return track, scheduled_end_date, due_date - PregnancyMemberTrack.PREGNANCY_DURATION


def get_postpartum_member_track(factories) -> Tuple[PostpartumMemberTrack, date, date]:
    # Given
    start_date = date.today()
    # When
    track: PostpartumMemberTrack = factories.MemberTrackFactory.create(
        name="postpartum", user__health_profile__last_child_birthday=start_date
    )
    track.set_anchor_date()
    scheduled_end_date = start_date + track.length() + track.grace_period()
    return track, scheduled_end_date, start_date


@pytest.mark.parametrize(
    argnames="case", argvalues=[get_pregnancy_member_track, get_postpartum_member_track]
)
def test_track_start_and_scheduled_end_date(case, factories):
    # When
    track, scheduled_end_date, start_date = case(factories)
    # Then
    assert track.anchor_date == start_date
    assert track.get_scheduled_end_date() == scheduled_end_date


@pytest.mark.parametrize(
    argnames="name",
    argvalues=[
        TrackName.BREAST_MILK_SHIPPING,
        TrackName.GENERIC,
        TrackName.PARENTING_AND_PEDIATRICS,
        TrackName.SPONSORED,
        TrackName.SURROGACY,
    ],
)
def test_static_track_phase(name, factories):
    # Given
    track: MemberTrack = factories.MemberTrackFactory.create(name=name)
    # Then
    assert track.current_phase is track.initial_phase
    assert track.initial_phase.started_at == track.anchor_date
    assert track.initial_phase.ended_at is None


@pytest.mark.parametrize(
    argnames="name",
    argvalues=[
        TrackName.BREAST_MILK_SHIPPING,
        TrackName.GENERIC,
        TrackName.SPONSORED,
    ],
)
def test_static_track_phase_completed(name, factories):
    # Given
    track: MemberTrack = factories.MemberTrackFactory.create(
        name=name, created_at=_today_dt - timedelta(days=1), ended_at=_today_dt
    )
    # Then
    assert track.final_phase is track.current_phase is track.initial_phase
    assert track.initial_phase.started_at == track.anchor_date
    assert track.initial_phase.ended_at == track.ended_at.date()


def test_set_anchor_date_doesnt_set_null(factories):
    # Given
    track: MemberTrack = factories.MemberTrackFactory.create(
        name=TrackName.POSTPARTUM, current_phase="week-40"
    )
    track.user.health_profile.json = {}
    # When
    track.set_anchor_date()
    # Then
    assert track.anchor_date is not None


def test_beyond_scheduled_end_nullsafe(factories):
    # Given
    track: MemberTrack = factories.MemberTrackFactory.create(
        name=TrackName.POSTPARTUM, anchor_date=None
    )
    # Then
    assert track.beyond_scheduled_end is False


@pytest.mark.parametrize(
    argnames="name",
    argvalues=[
        TrackName.ADOPTION,
        TrackName.FERTILITY,
        TrackName.GENERAL_WELLNESS,
        TrackName.PARENTING_AND_PEDIATRICS,
        TrackName.PARTNER_FERTILITY,
        TrackName.PARTNER_NEWPARENT,
        TrackName.PARTNER_PREGNANT,
        TrackName.POSTPARTUM,
        TrackName.PREGNANCY,
        TrackName.PREGNANCYLOSS,
        TrackName.TRYING_TO_CONCEIVE,
        TrackName.SURROGACY,
    ],
)
def test_phase_type_weekly(name, factories):
    track = factories.MemberTrackFactory.create(name=name)
    assert track.phase_type == PhaseType.WEEKLY
    assert isinstance(track, WeeklyMemberTrackMixin)


@pytest.mark.parametrize(
    argnames="name",
    argvalues=[
        TrackName.BREAST_MILK_SHIPPING,
        TrackName.GENERIC,
        TrackName.SPONSORED,
    ],
)
def test_phase_type_static(name, factories):
    track = factories.MemberTrackFactory.create(name=name)
    assert track.phase_type == PhaseType.STATIC
    assert isinstance(track, StaticMemberTrackMixin)


ALLOWED_TRACKS = [
    TrackName.PARENTING_AND_PEDIATRICS,
    TrackName.PREGNANCY,
    TrackName.POSTPARTUM,
    TrackName.FERTILITY,
]


def test_pregnancy_phase_name_past_scheduled_end(factories):
    # Given
    # Choose the due date such that today is on/after the scheduled end date
    due_date = _today - timedelta(weeks=3, days=1)
    # When
    track: PregnancyMemberTrack = factories.MemberTrackFactory.create(
        name="pregnancy",
        created_at=_today_dt - timedelta(weeks=30),
        user__health_profile__due_date=due_date,
    )
    track.set_anchor_date()
    # Then
    assert track.current_phase.name == "week-42"


def test_pregnancy_track_display_end_includes_postpartum_length(factories):
    user = factories.EnterpriseUserFactory(tracks__name=TrackName.PREGNANCY)
    track = user.active_tracks[0]
    expected_display_end = (
        date.today()
        + track.length()
        + track.grace_period()
        + get_track(TrackName.POSTPARTUM).length
    ).isoformat()
    assert track.get_display_scheduled_end_date().isoformat() == expected_display_end


def test_track_deprecated(factories):
    track = factories.MemberTrackFactory.create(name=TrackName.PREGNANCY)
    assert track.is_deprecated is False

    track = factories.MemberTrackFactory.create(name=TrackName.TRYING_TO_CONCEIVE)
    assert track.is_deprecated is True


@pytest.mark.parametrize(
    argnames="created_at,activated_at,ended_at,status",
    argvalues=[
        (YESTERDAY, YESTERDAY, None, "active"),
        (YESTERDAY, YESTERDAY, TODAY, "inactive"),
        (TODAY, None, None, "scheduled"),
    ],
)
def test_active(created_at, activated_at, ended_at, status, factories):
    track = factories.MemberTrackFactory.create(
        created_at=created_at, ended_at=ended_at
    )
    track.activated_at = activated_at

    db.session.add(track)
    db.session.commit()

    assert getattr(track, status) is True


def test_length(factories):
    track = factories.MemberTrackFactory.create(name="postpartum")
    track.client_track = None
    # should return default value from config
    assert track.length() == timedelta(weeks=24)

    track.client_track = factories.ClientTrackFactory.create(
        track="postpartum", length_in_days=10
    )
    # should return value from client track
    assert track.length() == timedelta(days=10)


def test_set_scheduled_end_date(factories):
    track = factories.MemberTrackFactory.create(name=TrackName.PARENTING_AND_PEDIATRICS)

    scheduled_end_date = date.today() + timedelta(days=10)

    track.set_scheduled_end_date(scheduled_end_date)

    assert track.get_scheduled_end_date() == scheduled_end_date


def test_set_scheduled_end_date_fails_for_pregnancy(factories):
    track = factories.MemberTrackFactory.create(name=TrackName.PREGNANCY)

    with pytest.raises(NotImplementedError):
        track.set_scheduled_end_date(date.today())


@pytest.mark.parametrize("is_doula_only_client_track", [True, False])
@mock.patch("models.tracks.client_track.should_enable_doula_only_track")
def test_is_doula_only(
    mock_should_enable_doula_only_track,
    is_doula_only_client_track,
    factories,
    client_track,
):
    # Given

    track_modifiers = "doula_only" if is_doula_only_client_track else None
    client_track = factories.ClientTrackFactory.create(
        track="pregnancy", track_modifiers=track_modifiers
    )
    member_track = factories.MemberTrackFactory.create(
        name=TrackName.PREGNANCY, client_track=client_track
    )

    # When/Then
    mock_should_enable_doula_only_track.return_value = is_doula_only_client_track

    if is_doula_only_client_track:
        assert member_track.track_modifiers == [TrackModifiers.DOULA_ONLY]
    else:
        assert member_track.track_modifiers == []


@pytest.mark.parametrize("should_enable_update_zendesk_user_profile", [True, False])
@mock.patch("messaging.services.zendesk.feature_flags.bool_variation")
@mock.patch("messaging.services.zendesk.update_zendesk_user.delay")
@mock.patch("models.tracks.member_track.log.info")
def test_member_profile__update_zendesk_user_on_tracks_insert(
    mock_log_info,
    mock_update_zendesk_user,
    mock_should_update_zendesk_user_profile,
    should_enable_update_zendesk_user_profile,
    factories,
):
    # Given
    mock_should_update_zendesk_user_profile.return_value = (
        should_enable_update_zendesk_user_profile
    )
    # we have an existing User Member Profile
    member = factories.DefaultUserFactory.create()
    mock_log_info.reset_mock()
    mock_update_zendesk_user.reset_mock()

    # When
    # new track created
    track = factories.MemberTrackFactory.create(
        user=member, activated_at=datetime.now()  # noqa
    )

    # Then
    if not should_enable_update_zendesk_user_profile:
        mock_update_zendesk_user.assert_not_called()
    # assert we update the Zendesk profile for a member
    else:
        mock_log_info.assert_called_once_with(
            "Updating Zendesk Profile for user track change",
            user_id=member.id,
            track_name=track.name,
            track_id=track.id,
        )
        mock_update_zendesk_user.assert_called_once()


@mock.patch("messaging.services.zendesk.update_zendesk_user.delay")
@mock.patch("models.tracks.member_track.log.info")
def test_member_profile__update_zendesk_user_on_tracks_insert_inactive_track(
    mock_log_info,
    mock_update_zendesk_user,
    factories,
):
    # Given
    # we have an existing User Member Profile
    member = factories.DefaultUserFactory.create()
    mock_log_info.reset_mock()
    mock_update_zendesk_user.reset_mock()
    # When
    # new track created without activated at
    factories.MemberTrackFactory.create(user=member)

    # Then
    mock_update_zendesk_user.assert_not_called()


@pytest.mark.parametrize("should_enable_update_zendesk_user_profile", [True])
@mock.patch("messaging.services.zendesk.feature_flags.bool_variation")
@mock.patch("messaging.services.zendesk.update_zendesk_user.delay")
@mock.patch("models.tracks.member_track.log.info")
@mock.patch(
    "models.tracks.client_track.should_enable_doula_only_track", return_value=True
)
@mock.patch("models.tracks.member_track.feature_flags.bool_variation", True)
def test_member_profile__update_zendesk_user_on_tracks_update(
    mock_enable_doula_only_track,
    mock_log_info,
    mock_update_zendesk_user,
    mock_should_update_zendesk_user_profile,
    should_enable_update_zendesk_user_profile,
    factories,
):
    # Given
    mock_should_update_zendesk_user_profile.return_value = (
        should_enable_update_zendesk_user_profile
    )
    # we have an existing User Member Profile
    member = factories.DefaultUserFactory.create()
    # existing active track
    track = factories.MemberTrackFactory.create(user=member)
    db.session.commit()
    # reset mocks to clear initial track creation
    mock_update_zendesk_user.reset_mock()
    mock_log_info.reset_mock()
    # confirm track active initially
    assert track.active is True

    # when track changed to inactive
    track.ended_at = YESTERDAY
    db.session.commit()
    assert track.active is False

    # Then
    if not should_enable_update_zendesk_user_profile:
        mock_update_zendesk_user.assert_not_called()
    # assert we update the Zendesk profile for a member
    else:
        mock_log_info.assert_called_once_with(
            "Updating Zendesk Profile for user track change",
            user_id=member.id,
            track_name=track.name,
            track_id=track.id,
        )


@mock.patch("models.tracks.member_track.log.info")
@mock.patch("models.tracks.member_track.stats.increment")
def test_after_update_listener(mock_stats_increment, mock_log_info, factories):
    organization = factories.OrganizationFactory.create(name="TestOrg")
    client_track = factories.ClientTrackFactory.create(organization=organization)
    user = factories.DefaultUserFactory.create()
    member_track = factories.MemberTrackFactory.create(
        user=user, client_track=client_track
    )

    member_track.transitioning_to = "postpartum"
    db.session.commit()

    assert any(
        call
        == mock.call(
            "[Member Track] Successfully updated MemberTrack",
            user_id=member_track.user_id,
            track_name=member_track.name,
            track_id=member_track.id,
            org_id=organization.id,
            change_reason=member_track.change_reason,
            transitioning_to=member_track.transitioning_to,
            anchor_date=member_track.anchor_date,
            is_multi_track=False,
        )
        for call in mock_log_info.mock_calls
    )
    assert any(
        call
        == mock.call(
            metric_name="member_track.update.success",
            pod_name=stats.PodNames.ENROLLMENTS,
            tags=[
                f"track_name:{member_track.name}",
                f"org:{organization.id}",
                f"change_reason:{member_track.change_reason}",
            ],
        )
        for call in mock_stats_increment.mock_calls
    )


@mock.patch("models.tracks.member_track.log.info")
@mock.patch("models.tracks.member_track.stats.increment")
def test_after_insert_listener(mock_stats_increment, mock_log_info, factories):
    organization = factories.OrganizationFactory.create(name="TestOrg")
    client_track = factories.ClientTrackFactory.create(organization=organization)
    user = factories.DefaultUserFactory.create()
    member_track = factories.MemberTrackFactory.build(
        user=user, client_track=client_track
    )

    db.session.add(member_track)
    db.session.flush()
    assert any(
        call
        == mock.call(
            metric_name="member_track.create.attempt",
            pod_name=stats.PodNames.ENROLLMENTS,
            tags=[
                f"track_name:{member_track.name}",
                f"org:{organization.id}",
            ],
        )
        for call in mock_stats_increment.mock_calls
    )

    assert any(
        call
        == mock.call(
            "[Member Track] Successfully created MemberTrack",
            user_id=member_track.user_id,
            track_name=member_track.name,
            track_id=member_track.id,
            org_id=organization.id,
            change_reason=None,
            transitioning_to=None,
            anchor_date=member_track.anchor_date,
            is_multi_track=False,
        )
        for call in mock_log_info.mock_calls
    )
    assert any(
        call
        == mock.call(
            metric_name="member_track.create.success",
            pod_name=stats.PodNames.ENROLLMENTS,
            tags=[
                f"track_name:{member_track.name}",
                f"org:{organization.id}",
                "change_reason:None",
            ],
        )
        for call in mock_stats_increment.mock_calls
    )
