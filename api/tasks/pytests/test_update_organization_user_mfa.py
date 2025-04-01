from unittest import mock

from pytests.freezegun import freeze_time
from tasks.enterprise import (
    update_organization_all_users_company_mfa,
    update_organization_all_users_company_mfa_job,
)


def test_update_organization_user_mfa_job_with_users(factories):
    # Given
    user_1 = factories.DefaultUserFactory.create()
    user_2 = factories.DefaultUserFactory.create()
    organization_1 = factories.OrganizationFactory.create()
    uoe_1 = factories.UserOrganizationEmployeeFactory.create(user=user_1)
    uoe_2 = factories.UserOrganizationEmployeeFactory.create(user=user_2)
    client_track_1 = factories.ClientTrackFactory.create(organization=organization_1)
    factories.MemberTrackFactory.create(user=uoe_1.user, client_track=client_track_1)
    factories.MemberTrackFactory.create(user=uoe_2.user, client_track=client_track_1)
    mock_candidate = (1,)
    mock_list = [mock_candidate]

    # When
    with mock.patch("maven.feature_flags.bool_variation", return_value=True):
        with mock.patch(
            "authn.domain.service.MFAService.update_user_company_mfa_to_auth0"
        ) as auth0_sync_call:
            with mock.patch(
                "authn.domain.service.MFAService.update_mfa_status_and_sms_phone_number"
            ) as db_sync_call:
                update_organization_all_users_company_mfa_job(
                    to_be_updated_users=mock_list, mfa_required=True
                )

                # Then
                assert auth0_sync_call.call_count == 1
                assert db_sync_call.call_count == 1


def test_update_organization_user_mfa_job_with_empty_users(factories):
    # Given
    mock_list = []

    # When
    with mock.patch("maven.feature_flags.bool_variation", return_value=False):
        with mock.patch(
            "authn.domain.service.MFAService.update_user_company_mfa_to_auth0"
        ) as auth0_sync_call:
            with mock.patch(
                "authn.domain.service.MFAService.update_mfa_status_and_sms_phone_number"
            ) as db_sync_call:
                update_organization_all_users_company_mfa_job(
                    to_be_updated_users=mock_list, mfa_required=False
                )

                # Then
                assert auth0_sync_call.call_count == 0
                assert db_sync_call.call_count == 0


@freeze_time("2023-12-23 18:45:00")
def test_update_organization_user_mfa_with_ff_on(factories):
    # Given
    organization_1 = factories.OrganizationFactory.create()
    mock_candidate = (1,)
    mock_list = [mock_candidate]

    # When
    with mock.patch("maven.feature_flags.bool_variation", return_value=True):
        with mock.patch(
            "tracks.service.tracks.TrackSelectionService.get_users_by_org_id",
            return_value=mock_list,
        ):
            with mock.patch(
                "tasks.enterprise.update_organization_all_users_company_mfa_job"
            ) as mock_job:
                update_organization_all_users_company_mfa(
                    org_id=organization_1.id, mfa_required=False
                )

                # Then
                assert mock_job.delay is not None


def test_update_organization_user_mfa_with_ff_on_with_empty_list(factories):
    # Given
    organization_1 = factories.OrganizationFactory.create()

    # When
    with mock.patch("maven.feature_flags.bool_variation", return_value=True):
        with mock.patch(
            "tracks.service.tracks.TrackSelectionService.get_users_by_org_id",
            return_value=[],
        ):
            with mock.patch(
                "tasks.enterprise.update_organization_all_users_company_mfa_job"
            ) as mock_job:
                update_organization_all_users_company_mfa(
                    org_id=organization_1.id, mfa_required=False
                )

                # Then
                assert mock_job.call_count == 0


def test_update_organization_user_mfa_with_ff_off(factories):
    # Given
    organization_1 = factories.OrganizationFactory.create()

    # When
    with mock.patch("maven.feature_flags.bool_variation", return_value=False):
        with mock.patch(
            "tracks.service.tracks.TrackSelectionService.get_users_by_org_id"
        ) as mock_get_users_by_org_id:
            update_organization_all_users_company_mfa(
                org_id=organization_1.id, mfa_required=False
            )

            # Then
            assert mock_get_users_by_org_id.call_count == 0
