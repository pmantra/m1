# Other tests are in api/tests/test_dashboard_metadata.py
import datetime
from unittest import mock
from unittest.mock import patch

import pytest

from appointments.models.appointment import Appointment
from authn.models.user import User
from health.data_models.risk_flag import RiskFlag, RiskFlagSeverity
from health.services.member_risk_service import MemberRiskService
from models.tracks import MemberTrack, TrackName
from models.tracks.client_track import TrackModifiers
from preferences.utils import set_member_communications_preference
from views import dashboard_metadata
from views.dashboard_metadata import get_dashboard_program
from wallet.models import reimbursement_wallet
from wallet.pytests import factories as wallet_factories


@mock.patch("health.services.health_profile_service.HealthProfileServiceClient")
def test_get_user_risk_flags(_, factories, db):
    user = factories.EnterpriseUserFactory.create()
    db.session.add(RiskFlag(severity=RiskFlagSeverity.HIGH_RISK, name="High Risk Flag"))
    db.session.add(
        RiskFlag(severity=RiskFlagSeverity.MEDIUM_RISK, name="Medium Risk Flag")
    )
    db.session.add(RiskFlag(severity=RiskFlagSeverity.LOW_RISK, name="Low Risk Flag"))
    db.session.add(RiskFlag(severity=RiskFlagSeverity.NONE, name="None Risk Flag"))
    db.session.commit()
    service = MemberRiskService(user.id)
    service.set_risk("High Risk Flag")
    service.set_risk("Medium Risk Flag")
    service.set_risk("Low Risk Flag")
    service.set_risk("None Risk Flag")
    db.session.refresh(user)
    risk_flags = user.current_risk_flags()
    risk_flags_names = [risk_flag.name for risk_flag in risk_flags]
    assert len(risk_flags) > 0
    result = dashboard_metadata.get_dashboard_user(user, user.organization)
    assert result.current_risk_flags == risk_flags_names


@mock.patch("health.services.health_profile_service.HealthProfileServiceClient")
@patch("views.dashboard_metadata.eligibility.get_verification_service")
@patch("views.dashboard_metadata.get_org")
def test_get_dashboard_metadata_endpoint_no_org(
    get_org_mock, e9y_svc_mock, _, client, api_helpers, factories
):
    user = factories.EnterpriseUserFactory()
    get_org_mock.return_value = None
    e9y_svc_mock.return_value.is_user_known_to_be_eligible_for_org.return_value = False

    res = client.get(
        f"api/v1/dashboard-metadata/track/{user.active_tracks[0].id}",
        headers=api_helpers.standard_headers(user=user),
    )

    assert res.status_code == 200


@mock.patch("health.services.health_profile_service.HealthProfileServiceClient")
def test_additional_tracks_one(_, factories):
    user = factories.EnterpriseUserFactory(
        tracks__name=TrackName.PREGNANCY,
        enabled_tracks=[TrackName.PREGNANCY, TrackName.PARENTING_AND_PEDIATRICS],
    )
    factories.MemberTrackFactory.create(
        user=user,
        name=TrackName.PARENTING_AND_PEDIATRICS,
    )

    result = dashboard_metadata.get_dashboard_metadata(
        user=user, track_id=user.active_tracks[0].id, phase_name=None
    )

    assert len(result.additional_tracks) == 1
    assert result.additional_tracks[0].name == TrackName.PARENTING_AND_PEDIATRICS


@mock.patch("health.services.health_profile_service.HealthProfileServiceClient")
def test_additional_tracks_none(_, enterprise_user):
    result = dashboard_metadata.get_dashboard_metadata(
        user=enterprise_user, track_id=enterprise_user.active_tracks[0].id
    )

    assert len(result.additional_tracks) == 0


@pytest.mark.parametrize(
    argnames="wallet_state,expected_wallet_status",
    argvalues=[
        (
            dashboard_metadata.WalletState.QUALIFIED,
            dashboard_metadata.DashboardUserWalletStatus.ENROLLED,
        ),
        (
            dashboard_metadata.WalletState.PENDING,
            dashboard_metadata.DashboardUserWalletStatus.ELIGIBLE,
        ),
        (
            dashboard_metadata.WalletState.DISQUALIFIED,
            dashboard_metadata.DashboardUserWalletStatus.INELIGIBLE,
        ),
        (
            dashboard_metadata.WalletState.EXPIRED,
            dashboard_metadata.DashboardUserWalletStatus.INELIGIBLE,
        ),
    ],
    ids=[
        "wallet-state-qualified",
        "wallet-state-pending",
        "wallet-state-disqualified",
        "wallet-state-expired",
    ],
)
def test_get_wallet_status_reimbursement_wallet_exists(
    wallet_state, expected_wallet_status, enterprise_user
):
    # Given
    wallet: reimbursement_wallet.ReimbursementWallet = (
        wallet_factories.ReimbursementWalletFactory(state=wallet_state)
    )
    wallet_factories.ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )
    org_id = enterprise_user.organization.id
    # When
    actual_wallet_status = dashboard_metadata.get_wallet_status(enterprise_user, org_id)
    # Then
    assert actual_wallet_status == expected_wallet_status


def test_get_wallet_status_ineligible_no_org_settings(factories):
    # Given
    mt: MemberTrack = factories.MemberTrackFactory()

    # When
    actual_wallet_status: dashboard_metadata.DashboardUserWalletStatus = (
        dashboard_metadata.get_wallet_status(mt.user, mt.user.organization.id)
    )

    # Then
    assert (
        actual_wallet_status == dashboard_metadata.DashboardUserWalletStatus.INELIGIBLE
    )


def test_get_wallet_status_eligible(factories):
    # Given
    mt: MemberTrack = factories.MemberTrackFactory()
    wallet_factories.ReimbursementOrganizationSettingsFactory(
        organization=mt.client_track.organization
    )

    # When
    actual_wallet_status: dashboard_metadata.DashboardUserWalletStatus = (
        dashboard_metadata.get_wallet_status(mt.user, mt.user.organization.id)
    )

    # Then
    assert actual_wallet_status == dashboard_metadata.DashboardUserWalletStatus.ELIGIBLE


@mock.patch("health.services.health_profile_service.HealthProfileServiceClient")
def test_has_care_plan(_, factories):
    member = factories.EnterpriseUserFactory.create()
    factories.ScheduleFactory(user=member)

    dash_user = dashboard_metadata.get_dashboard_user(member, member.organization)
    assert dash_user.has_care_plan is False

    member.member_profile.has_care_plan = True
    dash_user = dashboard_metadata.get_dashboard_user(member, member.organization)
    assert dash_user.has_care_plan is True


@mock.patch("health.services.health_profile_service.HealthProfileServiceClient")
def test_get_dashboard_user_country(_, factories):
    user = factories.EnterpriseUserFactory()
    factories.ScheduleFactory(user=user)
    user.member_profile.country_code = "PH"

    result = dashboard_metadata.get_dashboard_user(user, user.organization)

    assert result.country == "PH"


@mock.patch("health.services.health_profile_service.HealthProfileServiceClient")
def test_get_dashboard_user_no_country(_, factories):
    user = factories.EnterpriseUserFactory()
    factories.ScheduleFactory(user=user)
    user.member_profile.country_code = None

    result = dashboard_metadata.get_dashboard_user(user, user.organization)

    assert result.country is None


@mock.patch("health.services.health_profile_service.HealthProfileServiceClient")
@patch("views.dashboard_metadata.get_org")
def test_get_dashboard_user_no_org(get_org_mock, _, factories):
    user = factories.EnterpriseUserFactory()
    get_org_mock.return_value = None

    result = dashboard_metadata.get_dashboard_user(user=user, org=None)

    assert result.organization is None
    assert result.wallet_status is None
    assert result.has_available_tracks == 0


@pytest.mark.parametrize("is_eligible", [True, False])
@pytest.mark.parametrize("treatment_status", ["status1", "status2", None])
@pytest.mark.parametrize("is_matched_to_care_coach", [True, False])
@patch("views.dashboard_metadata.CareCoachingEligibilityService")
@patch("views.dashboard_metadata.HealthProfileService")
@patch("views.dashboard_metadata.ProviderService")
def test_get_dashboard_metadata_care_coaching(
    mock_provider_service,
    mock_health_profile_service,
    mock_care_coaching_service,
    is_matched_to_care_coach,
    treatment_status,
    is_eligible,
    factories,
):
    user = factories.EnterpriseUserFactory()
    factories.ScheduleFactory(user=user)

    mock_provider_service.return_value.is_member_matched_to_coach_for_active_track.return_value = (
        is_matched_to_care_coach
    )
    mock_care_coaching_service.return_value.is_user_eligible_for_care_coaching.return_value = (
        is_eligible
    )
    mock_health_profile_service.return_value.get_fertility_treatment_status.return_value = (
        treatment_status
    )

    result = dashboard_metadata.get_dashboard_user(user, user.organization)

    assert result.is_eligible_for_care_coaching == (
        is_eligible and is_matched_to_care_coach
    )
    assert mock_care_coaching_service.return_value.is_user_eligible_for_care_coaching.called_once_with(
        user=user, fertility_treatment_status=treatment_status
    )
    assert mock_provider_service.return_value.is_member_matched_to_coach_for_active_track.called_once_with(
        user
    )


def test_get_library_resources_no_org(factories):
    user = factories.EnterpriseUserFactory()

    result = dashboard_metadata.get_library_resources(
        user=user, track_name="pregnancy", phase_name="week-10", org=None
    )

    assert result.org == []


@patch("views.dashboard_metadata.log")
def test_get_scheduled_care_no_schedule(log_mock, factories):
    user = factories.EnterpriseUserFactory()
    result = dashboard_metadata.get_scheduled_care(user)
    assert result is None


@pytest.mark.parametrize("localization_flag", [True, False])
@pytest.mark.parametrize("disco_localization_flag", [True, False])
@pytest.mark.parametrize("locale", ["en", "es"])
def test_get_scheduled_care(
    factories, ff_test_data, localization_flag, disco_localization_flag, locale
):
    tomorrow = datetime.datetime.utcnow() + datetime.timedelta(days=1)

    appointment: Appointment = factories.AppointmentFactory.create(
        is_enterprise_with_track_factory=True, scheduled_start=tomorrow
    )

    with mock.patch("l10n.config.negotiate_locale", return_value=locale):
        ff_test_data.update(
            ff_test_data.flag("release-mono-api-localization").variation_for_all(
                localization_flag
            )
        )
        ff_test_data.update(
            ff_test_data.flag("release-disco-be-localization").variation_for_all(
                disco_localization_flag
            )
        )

        result = dashboard_metadata.get_scheduled_care(appointment.member)

        if localization_flag and disco_localization_flag and locale != "en":
            assert "OB-GYN" != result.practitioner.vertical
        else:
            assert "OB-GYN" == result.practitioner.vertical
        assert appointment.practitioner_id == result.practitioner.id
        assert appointment.api_id == result.appointment.id


def test_get_scheduled_care_current_appointment(factories):
    start_time = datetime.datetime.utcnow() - datetime.timedelta(minutes=5)
    end_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=5)
    tomorrow = datetime.datetime.utcnow() + datetime.timedelta(days=1)

    member = factories.EnterpriseUserFactory.create()
    factories.ScheduleFactory.create(user=member)

    appointment = factories.AppointmentFactory.create(
        member_schedule=member.schedule,
        scheduled_start=start_time,
        scheduled_end=end_time,
    )

    factories.AppointmentFactory.create(
        member_schedule=member.schedule, scheduled_start=tomorrow
    )

    result = dashboard_metadata.get_scheduled_care(member)

    assert "OB-GYN" == result.practitioner.vertical
    assert appointment.practitioner_id == result.practitioner.id
    assert appointment.api_id == result.appointment.id


@patch("views.dashboard_metadata.log")
@patch("views.dashboard_metadata.TrackSelectionService")
def test_get_org_no_org_id(track_service, log_mock, factories):
    user = factories.EnterpriseUserFactory()
    track_service.return_value.get_organization_id_for_user.return_value = None

    result = dashboard_metadata.get_org(user)

    assert result is None
    log_mock.warn.assert_called_with(
        "No organization id found for user", user_id=user.id
    )


@patch("views.dashboard_metadata.log")
@patch("views.dashboard_metadata.TrackSelectionService")
def test_get_org_no_org(track_service, log_mock, factories):
    user = factories.EnterpriseUserFactory()
    org_id = -1
    track_service.return_value.get_organization_id_for_user.return_value = org_id

    result = dashboard_metadata.get_org(user)

    assert result is None
    log_mock.warn.assert_called_with(
        "No organization found for user", user_id=user.id, org_id=org_id
    )


@patch("views.dashboard_metadata.TrackSelectionService")
def test_get_org_retries(track_service, factories):
    user = factories.EnterpriseUserFactory()
    track_service.return_value.get_organization_id_for_user.return_value = None

    dashboard_metadata.get_org(user)

    track_service.return_value.get_organization_id_for_user.assert_called_with(
        user_id=user.id
    )
    assert track_service.return_value.get_organization_id_for_user.call_count == 2


def test_get_dashboard_program(factories):
    member_track = factories.MemberTrackFactory()
    dashboard_program = get_dashboard_program(
        member_track, member_track.current_phase.name
    )
    assert dashboard_program.name == member_track.name
    assert dashboard_program.display_name == member_track.display_name
    assert dashboard_program.selected_phase == member_track.current_phase.name
    assert dashboard_program.current_phase == member_track.current_phase.name
    assert dashboard_program.transitioning_to == member_track.transitioning_to
    assert dashboard_program.auto_transitioned == member_track.auto_transitioned
    assert dashboard_program.length_in_days == member_track.length().days
    assert dashboard_program.anchor_date == member_track.anchor_date.isoformat()
    assert (
        dashboard_program.scheduled_end_date
        == member_track.get_scheduled_end_date().isoformat()
    )
    assert (
        dashboard_program.eligible_for_renewal == member_track.is_eligible_for_renewal()
    )
    assert dashboard_program.qualified_for_optout == bool(
        member_track.qualified_for_optout
    )
    assert dashboard_program.total_phases == member_track.total_phases
    assert dashboard_program.track_modifiers == []


@mock.patch("models.tracks.client_track.should_enable_doula_only_track")
def test_get_dashboard_program_doula_only_member(
    mock_should_enable_doula_only_track, create_doula_only_member: User
):
    member_track = create_doula_only_member.active_tracks[0]
    dashboard_program = get_dashboard_program(
        member_track, member_track.current_phase.name
    )
    assert dashboard_program.track_modifiers == [TrackModifiers.DOULA_ONLY]


@mock.patch("health.services.health_profile_service.HealthProfileServiceClient")
@patch("views.dashboard_metadata.eligibility.get_verification_service")
@patch("views.dashboard_metadata.get_org")
@pytest.mark.parametrize("preference_value", [True, False])
def test_get_dashboard_metadata_enterprise_has_email_preference(
    get_org_mock, e9y_svc_mock, _, client, api_helpers, factories, preference_value
):
    get_org_mock.return_value = None
    e9y_svc_mock.return_value.is_user_known_to_be_eligible_for_org.return_value = False
    user = factories.EnterpriseUserFactory()
    set_member_communications_preference(user.id, preference_value)
    res = client.get(
        f"api/v1/dashboard-metadata/track/{user.active_tracks[0].id}",
        headers=api_helpers.standard_headers(user=user),
    )

    assert res.status_code == 200
    assert res.json["user"]["subscribed_to_promotional_email"] is preference_value


@pytest.mark.parametrize("has_had_intro_response", [True, False])
@mock.patch("views.dashboard_metadata.HealthProfileService")
@mock.patch("views.dashboard_metadata.AvailabilityTools.has_had_ca_intro_appointment")
def test_get_dashboard_metadata_intro_appt(
    mock_has_had_intro, _, has_had_intro_response, factories
):
    user = factories.EnterpriseUserFactory()
    factories.ScheduleFactory(user=user)

    mock_has_had_intro.return_value = has_had_intro_response
    result = dashboard_metadata.get_dashboard_user(user, user.organization)
    assert result.has_had_intro_appointment == has_had_intro_response
