from typing import Optional
from unittest.mock import patch

from maven.feature_flags import test_data

from authn.models.user import User
from eligibility.pytests import factories as e9y_factories
from pytests.factories import DefaultUserFactory
from wallet.models.constants import (
    AlegeusCoverageTier,
    CardStatus,
    CardStatusReason,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.pytests.factories import ReimbursementWalletUsersFactory


def test_get_debit_card__fail_no_wallet(client, enterprise_user, api_helpers):
    res = client.get(
        "/api/v1/reimbursement_wallets/abcdefg/debit_card",
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res.status_code == 404


def test_get_debit_card__fail_wallet_user_mismatch(
    client, qualified_alegeus_wallet_hra, api_helpers
):
    request_user = DefaultUserFactory.create()
    res = client.get(
        "/api/v1/reimbursement_wallets/"
        + str(qualified_alegeus_wallet_hra.id)
        + "/debit_card",
        headers=api_helpers.json_headers(request_user),
    )
    assert res.status_code == 404


def test_get_debit_card__fail_no_debit_card(
    client, enterprise_user, qualified_alegeus_wallet_hra, api_helpers
):
    res = client.get(
        "/api/v1/reimbursement_wallets/"
        + str(qualified_alegeus_wallet_hra.id)
        + "/debit_card",
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res.status_code == 404
    content = api_helpers.load_json(res)
    assert content["message"] == "You do not have a current debit card!"


def test_get_debit_card__success(
    client,
    enterprise_user,
    qualified_alegeus_wallet_hra,
    wallet_debitcardinator,
    api_helpers,
):
    wallet_debitcardinator(qualified_alegeus_wallet_hra, card_status=CardStatus.ACTIVE)

    res = client.get(
        "/api/v1/reimbursement_wallets/"
        + str(qualified_alegeus_wallet_hra.id)
        + "/debit_card",
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    debit_card = content["data"]
    assert debit_card["card_status"] == CardStatus.ACTIVE.value


def test_get_debit_card__translation(
    client,
    enterprise_user,
    qualified_alegeus_wallet_hra,
    wallet_debitcardinator,
    api_helpers,
):
    wallet_debitcardinator(
        qualified_alegeus_wallet_hra,
        card_status=CardStatus.INACTIVE,
        card_status_reason=CardStatusReason.PAST_DUE_RECEIPT,
    )

    with test_data() as td, patch("l10n.config.negotiate_locale", return_value="es"):
        td.update(td.flag("release-mono-api-localization").variation_for_all(True))
        res = client.get(
            "/api/v1/reimbursement_wallets/"
            + str(qualified_alegeus_wallet_hra.id)
            + "/debit_card",
            headers=api_helpers.json_headers(enterprise_user),
        )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    debit_card = content["data"]
    assert (
        debit_card["card_status_reason_text"] is not None
        and debit_card["card_status_reason_text"] != ""
        and debit_card["card_status_reason_text"] != "card_status_reason_text"
        and debit_card["card_status_reason_text"]
        != "Your account has been temporarily deactivated "
        "due to a past-due receipt."
    ), "There must be translated text and it must not be the expected English."


def test_post_debit_card__fail_no_wallet(client, enterprise_user, api_helpers):
    res = client.post(
        "/api/v1/reimbursement_wallets/abcdefg/debit_card",
        headers=api_helpers.json_headers(enterprise_user),
        data=api_helpers.json_data({}),
    )
    assert res.status_code == 404


def test_post_debit_card__fail_wallet_user_mismatch(
    client, qualified_alegeus_wallet_hra, api_helpers
):
    request_user = DefaultUserFactory.create()
    res = client.post(
        "/api/v1/reimbursement_wallets/"
        + str(qualified_alegeus_wallet_hra.id)
        + "/debit_card",
        headers=api_helpers.json_headers(request_user),
        data=api_helpers.json_data({}),
    )
    assert res.status_code == 404


def test_post_debit_card__fail_existing_debit_card(
    client,
    enterprise_user,
    qualified_alegeus_wallet_hra,
    wallet_debitcardinator,
    api_helpers,
):
    wallet_debitcardinator(qualified_alegeus_wallet_hra, card_status=CardStatus.ACTIVE)

    qualified_alegeus_wallet_hra.reimbursement_organization_settings.debit_card_enabled = (
        True
    )

    res = client.post(
        "/api/v1/reimbursement_wallets/"
        + str(qualified_alegeus_wallet_hra.id)
        + "/debit_card",
        headers=api_helpers.json_headers(enterprise_user),
        data=api_helpers.json_data({}),
    )
    assert res.status_code == 409


def test_post_debit_card__fail_unqualified_wallet(
    client, enterprise_user, pending_alegeus_wallet_hra, api_helpers
):
    pending_alegeus_wallet_hra.reimbursement_organization_settings.debit_card_enabled = (
        True
    )

    res = client.post(
        "/api/v1/reimbursement_wallets/"
        + str(pending_alegeus_wallet_hra.id)
        + "/debit_card",
        headers=api_helpers.json_headers(enterprise_user),
        data=api_helpers.json_data({}),
    )
    assert res.status_code == 403


def test_post_debit_card__fail_non_enabled_org(
    client, enterprise_user, qualified_alegeus_wallet_hra, api_helpers
):
    res = client.post(
        "/api/v1/reimbursement_wallets/"
        + str(qualified_alegeus_wallet_hra.id)
        + "/debit_card",
        headers=api_helpers.json_headers(enterprise_user),
        data=api_helpers.json_data({}),
    )
    assert res.status_code == 403


def test_post_debit_card__fail_hdhp_status(
    client,
    enterprise_user,
    qualified_alegeus_wallet_hra,
    current_hdhp_plan,
    api_helpers,
    wallet_factories,
):
    wallet_factories.ReimbursementWalletPlanHDHPFactory.create(
        reimbursement_plan=current_hdhp_plan,
        wallet=qualified_alegeus_wallet_hra,
        alegeus_coverage_tier=AlegeusCoverageTier.SINGLE,
    )
    wallet_factories.ReimbursementAccountFactory.create(
        alegeus_account_type=wallet_factories.ReimbursementAccountTypeFactory.create(
            alegeus_account_type="DTR"
        ),
        alegeus_flex_account_key="42",
        wallet=qualified_alegeus_wallet_hra,
        plan=current_hdhp_plan,
    )

    with patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.get_employee_account"
    ) as mock_get_employee_account:
        mock_get_employee_account.return_value = (
            True,
            {
                "AccountType": "HRA",
                "AvailBalance": 1.99,
            },
        )

        res = client.post(
            "/api/v1/reimbursement_wallets/"
            + str(qualified_alegeus_wallet_hra.id)
            + "/debit_card",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data({}),
        )

        assert res.status_code == 403


def test_post_debit_card__fail_issue(
    client,
    enterprise_user,
    qualified_alegeus_wallet_hra,
    api_helpers,
    eligibility_factories,
):
    e9y_member = eligibility_factories.EligibilityMemberFactory.create(
        id=1,
        organization_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization_id,
        date_of_birth=None,
    )
    enterprise_user.profile.country_code = "US"
    qualified_alegeus_wallet_hra.reimbursement_organization_settings.debit_card_enabled = (
        True
    )
    with patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock, patch(
        "wallet.resources.reimbursement_wallet_debit_card.add_phone_number_to_alegeus"
    ) as add_phone_number_to_alegeus, patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.make_api_request"
    ), patch(
        "wallet.resources.reimbursement_wallet_debit_card.request_debit_card",
        return_value=False,
    ):
        member_id_search_mock.return_value = e9y_member
        res = client.post(
            "/api/v1/reimbursement_wallets/"
            + str(qualified_alegeus_wallet_hra.id)
            + "/debit_card",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data({"sms_opt_in": False}),
        )
        assert res.status_code == 500
        assert res.json["message"] == "Could not issue debit card"
        assert add_phone_number_to_alegeus.called is False


def test_post_debit_card__fail_no_address(
    client,
    enterprise_user,
    qualified_alegeus_wallet_hra,
    wallet_debitcardinator,
    api_helpers,
    eligibility_factories,
):
    e9y_member = eligibility_factories.EligibilityMemberFactory.create(
        id=1,
        organization_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization_id,
    )

    def request_debit_card_side_effect(wallet: ReimbursementWallet):
        wallet_debitcardinator(wallet)
        return True

    with patch(
        "wallet.resources.reimbursement_wallet_debit_card.request_debit_card",
        side_effect=request_debit_card_side_effect,
    ), patch(
        "wallet.resources.reimbursement_wallet_debit_card.add_phone_number_to_alegeus"
    ) as add_phone_number_to_alegeus_mock, patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = e9y_member
        qualified_alegeus_wallet_hra.reimbursement_organization_settings.debit_card_enabled = (
            True
        )
        enterprise_user.profile.country_code = "US"

        res = client.post(
            "/api/v1/reimbursement_wallets/"
            + str(qualified_alegeus_wallet_hra.id)
            + "/debit_card",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data({"sms_opt_in": True}),
        )

        assert add_phone_number_to_alegeus_mock.called
        assert res.status_code == 500
        assert res.json["message"] == "Could not issue debit card"


def test_post_debit_card__success_hdhp_status(
    client,
    enterprise_user,
    qualified_alegeus_wallet_hra,
    current_hdhp_plan,
    wallet_debitcardinator,
    api_helpers,
    factories,
    eligibility_factories,
    wallet_factories,
):
    wallet_factories.ReimbursementWalletPlanHDHPFactory.create(
        reimbursement_plan=current_hdhp_plan,
        wallet=qualified_alegeus_wallet_hra,
        alegeus_coverage_tier=AlegeusCoverageTier.SINGLE,
    )
    factories.AddressFactory(user=qualified_alegeus_wallet_hra.member)
    e9y_member = eligibility_factories.EligibilityMemberFactory.create(
        id=1,
        organization_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization_id,
    )
    # Clear existing RWUs from pytest infrastructure
    ReimbursementWalletUsers.query.delete()

    # Add the e9y_member
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=qualified_alegeus_wallet_hra.id,
        type=WalletUserType.DEPENDENT,
        status=WalletUserStatus.ACTIVE,
    )

    def request_debit_card_side_effect(
        wallet: ReimbursementWallet, user: Optional[User]
    ):
        wallet_debitcardinator(wallet)
        return True

    verification = e9y_factories.build_verification_from_oe(
        enterprise_user.id, enterprise_user.organization_employee
    )
    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user",
        return_value=verification,
    ), patch(
        "wallet.resources.reimbursement_wallet_debit_card.request_debit_card",
        side_effect=request_debit_card_side_effect,
    ), patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.make_api_request"
    ) as put_employee_demographic_api_request_mock, patch(
        "wallet.resources.reimbursement_wallet_debit_card.add_phone_number_to_alegeus"
    ) as add_phone_number_to_alegeus_mock, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.get_employee_accounts"
    ) as mock_get_employee_accounts, patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as get_verification_mock:
        get_verification_mock.return_value = e9y_member
        qualified_alegeus_wallet_hra.reimbursement_organization_settings.debit_card_enabled = (
            True
        )
        put_employee_demographic_api_request_mock.return_value.status_code = 200
        enterprise_user.profile.country_code = "US"

        mock_get_employee_accounts.return_value = (
            True,
            [
                {
                    "AccountType": "HRA",
                    "AnnualElection": 1400.00,
                    "AvailBalance": 0.00,
                    "PlanId": current_hdhp_plan.alegeus_plan_id,
                },
            ],
        )

        res = client.post(
            "/api/v1/reimbursement_wallets/"
            + str(qualified_alegeus_wallet_hra.id)
            + "/debit_card",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data({"sms_opt_in": True}),
        )

        assert res.status_code == 200
        assert add_phone_number_to_alegeus_mock.called


def test_post_debit_card__success(
    client,
    enterprise_user,
    qualified_alegeus_wallet_hra,
    wallet_debitcardinator,
    api_helpers,
    factories,
    eligibility_factories,
):
    def request_debit_card_side_effect(
        wallet: ReimbursementWallet, user: Optional[User]
    ):
        wallet_debitcardinator(wallet)
        return True

    factories.AddressFactory(user=qualified_alegeus_wallet_hra.member)
    e9y_member = eligibility_factories.EligibilityMemberFactory.create(
        id=1,
        organization_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization_id,
    )
    # Clear existing RWUs from pytest infrastructure
    ReimbursementWalletUsers.query.delete()

    # Add the e9y_member as an employee for the
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=qualified_alegeus_wallet_hra.id,
    )
    verification = e9y_factories.build_verification_from_oe(
        enterprise_user.id, enterprise_user.organization_employee
    )
    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user",
        return_value=verification,
    ), patch(
        "wallet.resources.reimbursement_wallet_debit_card.request_debit_card",
        side_effect=request_debit_card_side_effect,
    ), patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as get_verification_mock, patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.make_api_request"
    ) as put_employee_demographic_api_request_mock, patch(
        "wallet.resources.reimbursement_wallet_debit_card.add_phone_number_to_alegeus"
    ) as add_phone_number_to_alegeus_mock:
        put_employee_demographic_api_request_mock.return_value.status_code = 200
        get_verification_mock.return_value = e9y_member
        qualified_alegeus_wallet_hra.reimbursement_organization_settings.debit_card_enabled = (
            True
        )
        enterprise_user.profile.country_code = "US"
        res = client.post(
            "/api/v1/reimbursement_wallets/"
            + str(qualified_alegeus_wallet_hra.id)
            + "/debit_card",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data({"sms_opt_in": True}),
        )
        assert res.status_code == 200
        assert add_phone_number_to_alegeus_mock.called


def test_post_debit_card_lost_stolen__fail_no_wallet(
    client, enterprise_user, api_helpers
):
    res = client.post(
        "/api/v1/reimbursement_wallets/abcdefg/debit_card/lost_stolen",
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res.status_code == 404


def test_post_debit_card_lost_stolen__fail_wallet_user_mismatch(
    client, qualified_alegeus_wallet_hra, api_helpers
):
    request_user = DefaultUserFactory.create()
    res = client.post(
        f"/api/v1/reimbursement_wallets/{qualified_alegeus_wallet_hra.id}/debit_card/lost_stolen",
        headers=api_helpers.json_headers(request_user),
    )
    assert res.status_code == 404


def test_post_debit_card_lost_stolen__fail_existing_closed_debit_card(
    client,
    enterprise_user,
    qualified_alegeus_wallet_hra,
    wallet_debitcardinator,
    api_helpers,
):
    wallet_debitcardinator(qualified_alegeus_wallet_hra, card_status=CardStatus.CLOSED)

    res = client.post(
        f"/api/v1/reimbursement_wallets/{qualified_alegeus_wallet_hra.id}/debit_card/lost_stolen",
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res.status_code == 409


def test_post_debit_card_lost_stolen__fail_no_debit_card(
    client, enterprise_user, pending_alegeus_wallet_hra, api_helpers
):
    res = client.post(
        f"/api/v1/reimbursement_wallets/{pending_alegeus_wallet_hra.id}/debit_card/lost_stolen",
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res.status_code == 404


def test_post_debit_card_lost_stolen__fail_exception(
    client,
    enterprise_user,
    qualified_alegeus_wallet_hra,
    wallet_debitcardinator,
    api_helpers,
):
    def report_lost_stolen_debit_card_side_effect(wallet: None):
        raise Exception

    with patch(
        "wallet.resources.reimbursement_wallet_debit_card.report_lost_stolen_debit_card",
        side_effect=report_lost_stolen_debit_card_side_effect,
    ):
        wallet_debitcardinator(
            qualified_alegeus_wallet_hra, card_status=CardStatus.ACTIVE
        )
        res = client.post(
            f"/api/v1/reimbursement_wallets/{qualified_alegeus_wallet_hra.id}/debit_card/lost_stolen",
            headers=api_helpers.json_headers(enterprise_user),
        )
        assert res.status_code == 500


def test_post_debit_card_lost_stolen__fail_api(
    client,
    enterprise_user,
    qualified_alegeus_wallet_hra,
    wallet_debitcardinator,
    api_helpers,
):
    def report_lost_stolen_debit_card_side_effect(wallet: qualified_alegeus_wallet_hra):
        wallet.debit_card.card_status = CardStatus.ACTIVE
        return False

    with patch(
        "wallet.resources.reimbursement_wallet_debit_card.report_lost_stolen_debit_card",
        side_effect=report_lost_stolen_debit_card_side_effect,
    ):
        wallet_debitcardinator(
            qualified_alegeus_wallet_hra, card_status=CardStatus.ACTIVE
        )
        res = client.post(
            f"/api/v1/reimbursement_wallets/{qualified_alegeus_wallet_hra.id}/debit_card/lost_stolen",
            headers=api_helpers.json_headers(enterprise_user),
        )
        assert res.status_code == 500


def test_post_debit_card_lost_stolen__success(
    client,
    enterprise_user,
    qualified_alegeus_wallet_hra,
    wallet_debitcardinator,
    api_helpers,
):
    def report_lost_stolen_debit_card_side_effect(wallet: ReimbursementWallet):
        wallet.debit_card.card_status = CardStatus.CLOSED
        return True

    with patch(
        "wallet.resources.reimbursement_wallet_debit_card.report_lost_stolen_debit_card",
        side_effect=report_lost_stolen_debit_card_side_effect,
    ):
        wallet_debitcardinator(
            qualified_alegeus_wallet_hra, card_status=CardStatus.ACTIVE
        )

        res = client.post(
            f"/api/v1/reimbursement_wallets/{qualified_alegeus_wallet_hra.id}/debit_card/lost_stolen",
            headers=api_helpers.json_headers(enterprise_user),
        )
        assert res.status_code == 200
