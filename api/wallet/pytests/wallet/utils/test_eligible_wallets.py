import datetime
from unittest import mock

import pytest

from eligibility import EnterpriseVerificationError
from models.marketing import ResourceContentTypes, ResourceTypes
from models.tracks import TrackName
from pytests.factories import ChannelFactory
from pytests.freezegun import freeze_time
from wallet.models.constants import WalletState, WalletUserStatus, WalletUserType
from wallet.pytests.factories import (
    ReimbursementOrganizationSettingsFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
)
from wallet.utils.eligible_wallets import (
    active_reimbursement_wallet,
    get_eligible_wallet_org_settings,
    get_user_eligibility_start_date,
    qualified_reimbursement_wallet,
)


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_future_eligible_wallet_check(enterprise_user):
    """setting the start date for organization settings renders the user's organization ineligible"""
    future_start_date = datetime.datetime.now() + datetime.timedelta(days=7)  # noqa
    ReimbursementOrganizationSettingsFactory.create(
        started_at=future_start_date, organization_id=enterprise_user.organization_v2.id
    )
    eligible_data = get_eligible_wallet_org_settings(enterprise_user.id)
    assert len(eligible_data) == 0


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_eligible_wallet_check(enterprise_user):
    """test that only the correct org is returned for eligibility"""
    past_start_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=7
    )
    ReimbursementOrganizationSettingsFactory.create(
        started_at=past_start_date, organization_id=enterprise_user.organization_v2.id
    )
    eligible_data = get_eligible_wallet_org_settings(enterprise_user.id)
    assert len(eligible_data) == 1


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_eligible_wallet_check_filter_out_existing_wallets(enterprise_user):
    """Test that ROSes with existing wallets are filtered out"""
    # Given
    ros = ReimbursementOrganizationSettingsFactory.create(
        started_at=datetime.datetime(year=2000, month=1, day=1),
        organization_id=enterprise_user.organization_v2.id,
    )
    wallet = ReimbursementWalletFactory.create(reimbursement_organization_settings=ros)
    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id, user_id=enterprise_user.id
    )

    # When
    eligible_roses_all = get_eligible_wallet_org_settings(
        enterprise_user.id, filter_out_existing_wallets=False
    )
    eligible_roses_filter_out_existing = get_eligible_wallet_org_settings(
        enterprise_user.id, filter_out_existing_wallets=True
    )

    # Then
    assert len(eligible_roses_all) == 1
    assert not eligible_roses_filter_out_existing


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_eligible_wallet_check_filter_out_existing_wallets_within_same_org(
    enterprise_user,
):
    """Test that ROSes with existing wallets are filtered out for orgs with multiple ROSes in the same org"""
    # Given
    ros_1 = ReimbursementOrganizationSettingsFactory.create(
        started_at=datetime.datetime(year=2000, month=1, day=1),
        organization_id=enterprise_user.organization_v2.id,
    )
    ros_2 = ReimbursementOrganizationSettingsFactory.create(
        started_at=datetime.datetime(year=2000, month=1, day=1),
        organization_id=enterprise_user.organization_v2.id,
    )
    wallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings=ros_1
    )
    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id, user_id=enterprise_user.id
    )

    # When
    eligible_roses_all = get_eligible_wallet_org_settings(
        enterprise_user.id, filter_out_existing_wallets=False
    )
    eligible_roses_filter_out_existing = get_eligible_wallet_org_settings(
        enterprise_user.id, filter_out_existing_wallets=True
    )

    # Then
    assert len(eligible_roses_all) == 2
    assert len(eligible_roses_filter_out_existing) == 1
    assert eligible_roses_filter_out_existing[0] == ros_2


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_me_response_eligible_wallet(enterprise_user, client, api_helpers):
    past_start_date = datetime.datetime.now() - datetime.timedelta(days=7)  # noqa
    organization_settings = ReimbursementOrganizationSettingsFactory.create(
        started_at=past_start_date, organization_id=enterprise_user.organization_v2.id
    )
    res = client.get("/api/v1/me", headers=api_helpers.json_headers(enterprise_user))
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert len(content["wallet"]["eligible"]) == 1
    assert len(content["wallet"]["enrolled"]) == 0
    wallet = content["wallet"]["eligible"].pop()
    assert wallet["state"] is None
    assert wallet["benefit_faq_resource"] is not None
    assert wallet["organization_setting_id"] == str(organization_settings.id)
    assert wallet["survey_url"].endswith("/app/wallet/apply")
    assert "channel_id" not in wallet


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_me_response_eligible_wallet_auto_qualification(
    enterprise_user, client, api_helpers
):
    past_start_date = datetime.datetime.now() - datetime.timedelta(days=7)  # noqa
    organization_settings = ReimbursementOrganizationSettingsFactory.create(
        started_at=past_start_date, organization_id=enterprise_user.organization_v2.id
    )
    with mock.patch("utils.launchdarkly.feature_flags.bool_variation") as feature_flag:
        feature_flag.return_value = True
        res = client.get(
            "/api/v1/me", headers=api_helpers.json_headers(enterprise_user)
        )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert len(content["wallet"]["eligible"]) == 1
    assert len(content["wallet"]["enrolled"]) == 0
    wallet = content["wallet"]["eligible"].pop()
    assert wallet["state"] is None
    assert wallet["benefit_faq_resource"] is not None
    assert wallet["organization_setting_id"] == str(organization_settings.id)
    # New Wallet Application URL
    assert wallet["survey_url"].endswith("/app/wallet/apply")
    assert "channel_id" not in wallet


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_not_eligible_due_to_inactive_track(factories):
    user = factories.EnterpriseUserFactory.create(
        tracks__name=TrackName.PREGNANCY, enabled_tracks=[TrackName.PREGNANCY]
    )

    yesterday = datetime.datetime.now() - datetime.timedelta(days=1)  # noqa
    pregnancy_settings = ReimbursementOrganizationSettingsFactory.create(
        started_at=yesterday, organization_id=user.organization.id
    )
    pregnancy_settings.required_module = factories.WeeklyModuleFactory.create(
        name=TrackName.PREGNANCY
    )

    tomorrow = datetime.datetime.now() + datetime.timedelta(days=1)  # noqa
    pediatrics_settings = ReimbursementOrganizationSettingsFactory.create(
        started_at=tomorrow, organization_id=user.organization.id
    )
    pediatrics_settings.required_module = factories.WeeklyModuleFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS
    )

    # Assert that the Pediatrics settings are filtered from the eligible list
    eligibile_org_settings = get_eligible_wallet_org_settings(user.id)

    assert pregnancy_settings in eligibile_org_settings
    assert pediatrics_settings not in eligibile_org_settings


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_not_eligible_due_to_disabled_track(factories):
    user = factories.EnterpriseUserFactory.create(
        tracks__name=TrackName.PREGNANCY, enabled_tracks=[TrackName.PREGNANCY]
    )

    pregnancy_settings = ReimbursementOrganizationSettingsFactory.create(
        organization_id=user.organization.id
    )
    pregnancy_settings.required_module = factories.WeeklyModuleFactory.create(
        name=TrackName.PREGNANCY
    )

    pediatrics_settings = ReimbursementOrganizationSettingsFactory.create(
        organization_id=user.organization.id
    )
    pediatrics_settings.required_module = factories.WeeklyModuleFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS
    )

    # Assert that the Pediatrics settings are filtered from the eligible list
    eligibile_org_settings = get_eligible_wallet_org_settings(user.id)

    assert pregnancy_settings in eligibile_org_settings
    assert pediatrics_settings not in eligibile_org_settings


@mock.patch("wallet.utils.eligible_wallets.tracks_service")
def test_get_eligible_wallet_org_settings_user_not_enterprise(
    tracks_service, default_user
):
    tracks_svc_instance = mock.Mock()
    tracks_service.TrackSelectionService.return_value = tracks_svc_instance
    tracks_svc_instance.is_enterprise.return_value = False

    assert get_eligible_wallet_org_settings(default_user.id) == []


@mock.patch("wallet.utils.eligible_wallets.tracks_service")
@mock.patch("wallet.utils.eligible_wallets.e9y_service")
def test_get_eligible_wallet_org_settings_without_org_id_arg(
    e9y_service, tracks_service, enterprise_user
):
    e9y_svc_instance = mock.Mock()
    e9y_service.EnterpriseVerificationService.return_value = e9y_svc_instance
    e9y_svc_instance.get_organization_id_for_user.return_value = 1

    get_eligible_wallet_org_settings(enterprise_user.id)

    tracks_service.TrackSelectionService.assert_called()
    e9y_service.EnterpriseVerificationService.assert_called()


@mock.patch("wallet.utils.eligible_wallets.tracks_service")
def test_get_eligible_wallet_org_settings_with_org_id_arg(
    tracks_service, enterprise_user
):
    get_eligible_wallet_org_settings(
        user_id=enterprise_user.id, organization_id=enterprise_user.organization_v2.id
    )

    tracks_service.TrackSelectionService.assert_not_called()


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_me_response_disqualified_wallet(enterprise_user, client, api_helpers):
    reimbursement_wallet = ReimbursementWalletFactory.create(
        state=WalletState.DISQUALIFIED
    )
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=reimbursement_wallet.id,
    )
    res = client.get("/api/v1/me", headers=api_helpers.json_headers(enterprise_user))
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert len(content["wallet"]["eligible"]) == 1
    assert len(content["wallet"]["enrolled"]) == 0
    wallet = content["wallet"]["eligible"].pop()
    assert wallet["organization_setting_id"] == str(
        reimbursement_wallet.reimbursement_organization_settings_id
    )
    assert wallet["state"] == WalletState.DISQUALIFIED
    assert wallet["benefit_faq_resource"] is not None
    assert wallet["survey_url"].endswith("/app/wallet/apply")


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_me_response_pending_wallet(enterprise_user, client, api_helpers):
    reimbursement_wallet = ReimbursementWalletFactory.create()
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=reimbursement_wallet.id,
    )
    res = client.get("/api/v1/me", headers=api_helpers.json_headers(enterprise_user))
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert len(content["wallet"]["eligible"]) == 0
    assert len(content["wallet"]["enrolled"]) == 1
    wallet = content["wallet"]["enrolled"].pop()
    assert wallet["state"] == WalletState.PENDING
    assert wallet["benefit_faq_resource"] is not None
    assert hasattr(wallet, "organization_setting_id") is False
    assert hasattr(wallet, "survey_url") is False


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_me_response_qualified_wallet(enterprise_user, client, api_helpers):
    reimbursement_wallet = ReimbursementWalletFactory.create(
        state=WalletState.QUALIFIED
    )
    channel = ChannelFactory.create(id=45894032)
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=reimbursement_wallet.id,
        channel_id=channel.id,
    )
    res = client.get("/api/v1/me", headers=api_helpers.json_headers(enterprise_user))
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert len(content["wallet"]["eligible"]) == 0
    assert len(content["wallet"]["enrolled"]) == 1
    wallet = content["wallet"]["enrolled"].pop()
    assert wallet["state"] == WalletState.QUALIFIED
    assert wallet["benefit_faq_resource"] is not None
    assert wallet["benefit_faq_resource"]["url"] is not None
    assert wallet["benefit_overview_resource"] is not None
    assert hasattr(wallet, "organization_setting_id") is False
    assert hasattr(wallet, "survey_url") is False
    assert wallet["channel_id"] == channel.id


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_me_response_expired_wallet(enterprise_user, client, api_helpers):
    reimbursement_wallet = ReimbursementWalletFactory.create(state=WalletState.EXPIRED)
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=reimbursement_wallet.id,
    )
    res = client.get("/api/v1/me", headers=api_helpers.json_headers(enterprise_user))
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert len(content["wallet"]["eligible"]) == 0
    assert len(content["wallet"]["enrolled"]) == 0


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_benefit_resource_overview(enterprise_user, client, api_helpers, factories):
    past_start_date = datetime.datetime.now() - datetime.timedelta(days=7)  # noqa
    resource_title = "Maven Wallet Benefit Overview"
    benefit_overview_resource = factories.ResourceFactory(
        resource_type=ResourceTypes.ENTERPRISE,
        content_type=ResourceContentTypes.article.name,
        title=resource_title,
        body="Read information on benefits here.",
    )
    organization_settings = ReimbursementOrganizationSettingsFactory.create(
        started_at=past_start_date,
        organization_id=enterprise_user.organization_v2.id,
        benefit_overview_resource=benefit_overview_resource,
    )
    reimbursement_wallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings=organization_settings,
    )
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=reimbursement_wallet.id,
    )

    res = client.get("/api/v1/me", headers=api_helpers.json_headers(enterprise_user))
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["wallet"]["enrolled"].pop()
    assert wallet["benefit_overview_resource"]["title"] == resource_title
    assert wallet["benefit_overview_resource"]["url"] is not None


@pytest.mark.parametrize(
    argnames="wallet_state,multiple_wallets_found,wallet_exists",
    argvalues=[
        (WalletState.QUALIFIED, False, True),
        (WalletState.DISQUALIFIED, False, False),
        (WalletState.EXPIRED, False, False),
        (WalletState.PENDING, False, False),
        (WalletState.QUALIFIED, True, False),
        (WalletState.PENDING, True, True),
    ],
)
def test_qualified_reimbursement_wallet(
    wallet_state,
    multiple_wallets_found,
    wallet_exists,
    factories,
):
    active_user = factories.DefaultUserFactory.create(id=1)
    wallet = ReimbursementWalletFactory.create(
        state=wallet_state, user_id=active_user.id
    )
    pending_user = factories.DefaultUserFactory.create(id=5)
    denied_user = factories.DefaultUserFactory.create(id=7)
    for user, user_status in (
        (active_user, WalletUserStatus.ACTIVE),
        (pending_user, WalletUserStatus.PENDING),
        (denied_user, WalletUserStatus.DENIED),
    ):
        ReimbursementWalletUsersFactory.create(
            user_id=user.id,
            reimbursement_wallet_id=wallet.id,
            type=WalletUserType.DEPENDENT,
            status=user_status,
        )

    expected_result = wallet if wallet_exists else None
    if multiple_wallets_found:
        # Create a qualified wallet for the active user
        wallet_2 = ReimbursementWalletFactory.create(
            state=WalletState.QUALIFIED, user_id=active_user.id
        )
        ReimbursementWalletUsersFactory.create(
            user_id=active_user.id,
            reimbursement_wallet_id=wallet_2.id,
            type=WalletUserType.DEPENDENT,
            status=WalletUserStatus.ACTIVE,
        )
        expected_result = wallet_2 if wallet_exists else None

    assert qualified_reimbursement_wallet(active_user.id) == expected_result


@pytest.mark.parametrize(
    argnames="wallet_state,wallet_found",
    argvalues=[
        (WalletState.DISQUALIFIED, False),
        (WalletState.EXPIRED, False),
        (WalletState.PENDING, False),
        (WalletState.QUALIFIED, True),
        (WalletState.PENDING, False),
        (WalletState.RUNOUT, True),
    ],
)
def test_active_reimbursement_wallet(
    wallet_state: WalletState,
    wallet_found: bool,
    enterprise_user,
):
    # Given
    wallet = ReimbursementWalletFactory.create(
        state=wallet_state, user_id=enterprise_user.id
    )
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )

    # When
    found_wallet = active_reimbursement_wallet(enterprise_user.id)

    assert (found_wallet is not None) is wallet_found


def test_active_reimbursement_wallet_multiple_found(
    enterprise_user,
):
    # Given
    wallet_one = ReimbursementWalletFactory.create(
        state=WalletState.QUALIFIED, user_id=enterprise_user.id
    )
    wallet_two = ReimbursementWalletFactory.create(
        state=WalletState.QUALIFIED, user_id=enterprise_user.id
    )
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet_one.id,
    )

    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet_two.id,
    )

    # When
    found_wallet = active_reimbursement_wallet(enterprise_user.id)

    assert found_wallet is None


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_eligible_wallet_check_eligible(enterprise_user):
    """
    Tests that if the wallet ID is returned by the e9y utility function, the wallet will be
    considered eligible.
    """
    # Given
    past_start_date = datetime.datetime.now() - datetime.timedelta(days=7)  # noqa
    wallet = ReimbursementOrganizationSettingsFactory.create(
        started_at=past_start_date, organization_id=enterprise_user.organization_v2.id
    )
    assert len(enterprise_user.active_tracks) > 0
    enterprise_user.active_tracks[0].sub_population_id = 1

    # When
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_eligible_features_by_sub_population_id"
    ) as mock_get_eligible_features_by_sub_population_id:
        mock_get_eligible_features_by_sub_population_id.return_value = [wallet.id]
        eligible_data = get_eligible_wallet_org_settings(enterprise_user.id)

    # Then
    assert len(eligible_data) == 1


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_eligible_wallet_check_none_eligible(enterprise_user):
    """
    Tests that if no wallet ID is returned by the e9y utility function, the wallet will not be
    considered eligible.
    """
    # Given
    past_start_date = datetime.datetime.now() - datetime.timedelta(days=7)  # noqa
    ReimbursementOrganizationSettingsFactory.create(
        started_at=past_start_date, organization_id=enterprise_user.organization_v2.id
    )
    assert len(enterprise_user.active_tracks) > 0
    enterprise_user.active_tracks[0].sub_population_id = 1

    # When
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_eligible_features_by_sub_population_id"
    ) as mock_get_eligible_features_by_sub_population_id:
        mock_get_eligible_features_by_sub_population_id.return_value = []
        eligible_data = get_eligible_wallet_org_settings(enterprise_user.id)

    # Then
    assert len(eligible_data) == 0


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_eligible_wallet_check_no_population(enterprise_user):
    """
    Tests that if no population is configured, the wallet will be considered eligible
    by default.
    """
    # Given
    past_start_date = datetime.datetime.now() - datetime.timedelta(days=7)  # noqa
    ReimbursementOrganizationSettingsFactory.create(
        started_at=past_start_date, organization_id=enterprise_user.organization_v2.id
    )

    # When
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_eligible_features_by_sub_population_id"
    ) as mock_get_eligible_features_by_sub_population_id:
        mock_get_eligible_features_by_sub_population_id.return_value = None
        eligible_data = get_eligible_wallet_org_settings(enterprise_user.id)

    # Then
    assert len(eligible_data) == 1


def test_me_response_denied_user_qualified_wallet(enterprise_user, client, api_helpers):
    reimbursement_wallet = ReimbursementWalletFactory.create(
        state=WalletState.QUALIFIED
    )
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=reimbursement_wallet.id,
        type=WalletUserType.EMPLOYEE,
        status=WalletUserStatus.DENIED,
    )
    res = client.get("/api/v1/me", headers=api_helpers.json_headers(enterprise_user))
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert len(content["wallet"]["eligible"]) == 1
    assert len(content["wallet"]["enrolled"]) == 0
    wallet = content["wallet"]["eligible"].pop()
    assert wallet["organization_setting_id"] == str(
        reimbursement_wallet.reimbursement_organization_settings_id
    )
    assert wallet["state"] == WalletState.DISQUALIFIED
    assert wallet["benefit_faq_resource"] is not None
    assert wallet["survey_url"].endswith("/app/wallet/apply")


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_me_response_pending_user_qualified_wallet(
    enterprise_user, client, api_helpers
):
    reimbursement_wallet = ReimbursementWalletFactory.create(
        state=WalletState.QUALIFIED
    )
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=reimbursement_wallet.id,
        type=WalletUserType.EMPLOYEE,
        status=WalletUserStatus.PENDING,
    )
    res = client.get("/api/v1/me", headers=api_helpers.json_headers(enterprise_user))
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert len(content["wallet"]["eligible"]) == 0
    assert len(content["wallet"]["enrolled"]) == 1
    wallet = content["wallet"]["enrolled"].pop()
    assert wallet["state"] == WalletState.PENDING
    assert wallet["benefit_faq_resource"] is not None
    assert hasattr(wallet, "organization_setting_id") is False
    assert hasattr(wallet, "survey_url") is False


@pytest.mark.parametrize(
    "start_date, required_tenure_days, expected_eligible_data",
    [
        # Cases based on current date of 2024-10-24
        ("2024-10-01", 0, 1),  # no tenure rules
        ("2024-10-01", 90, 0),  # 90 days tenure rules not eligible
        ("2024-07-26", 90, 1),  # 90 days tenure rules eligible
    ],
)
@freeze_time("2024-10-24")
@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_eligible_wallet_check_tenure_requirements(
    enterprise_user,
    start_date,
    required_tenure_days,
    expected_eligible_data,
    qualified_wallet_eligibility_verification_record,
):
    """
    test that only the correct org is returned for eligibility data based off of required
    tenure days and e9y start date
    """
    past_start_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=7
    )
    ReimbursementOrganizationSettingsFactory.create(
        started_at=past_start_date,
        organization_id=enterprise_user.organization.id,
        required_tenure_days=required_tenure_days,
    )
    qualified_wallet_eligibility_verification_record.record[
        "employee_start_date"
    ] = str(start_date)
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as mock_e9y_verification:
        mock_e9y_verification.return_value = (
            qualified_wallet_eligibility_verification_record
        )
        eligible_data = get_eligible_wallet_org_settings(enterprise_user.id)

    assert len(eligible_data) == expected_eligible_data


@freeze_time("2024-10-24")
@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_eligible_wallet_check_tenure_requirements_exception(
    enterprise_user,
    qualified_wallet_eligibility_verification_record,
):
    """
    test that only the correct org is returned for eligibility data based off of required
    tenure days and e9y start date
    """
    past_start_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=7
    )
    ReimbursementOrganizationSettingsFactory.create(
        started_at=past_start_date,
        organization_id=enterprise_user.organization.id,
        required_tenure_days=90,
    )

    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as mock_e9y_verification:
        mock_e9y_verification.side_effect = Exception()
        with pytest.raises(EnterpriseVerificationError):
            get_eligible_wallet_org_settings(enterprise_user.id)


@pytest.mark.parametrize(
    "verification_data,expected",
    [
        (
            mock.MagicMock(record={"employee_start_date": "2025-01-25"}),
            datetime.date(year=2025, month=1, day=25),
        ),
        (
            mock.MagicMock(
                record={"employee_start_date": None, "created_at": "2025-01-26"}
            ),
            datetime.date(year=2025, month=1, day=26),
        ),
        (
            mock.MagicMock(record={"employee_start_date": None, "created_at": None}),
            None,
        ),
        (mock.MagicMock(record={}), None),
        (None, None),
    ],
)
def test_get_user_eligibility_start_date(verification_data, expected):
    with mock.patch(
        "wallet.utils.eligible_wallets.e9y_service.get_verification_service"
    ), mock.patch(
        "wallet.utils.eligible_wallets.get_verification_record_data",
        return_value=verification_data,
    ):
        start_date = get_user_eligibility_start_date(user_id=-1, org_id=-1)
    assert start_date == expected
