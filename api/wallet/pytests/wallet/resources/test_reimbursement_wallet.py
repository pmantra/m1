from __future__ import annotations

import datetime
from random import randint
from typing import List, Tuple
from unittest.mock import ANY, Mock, patch

import pytest

from cost_breakdown.pytests.factories import CostBreakdownFactory
from direct_payment.clinic.pytests.factories import (
    FertilityClinicFactory,
    FertilityClinicLocationFactory,
)
from direct_payment.payments.models import (
    EstimateSummaryForReimbursementWallet,
    PaymentRecordForReimbursementWallet,
    UpcomingPaymentsAndSummaryForReimbursementWallet,
    UpcomingPaymentsResultForReimbursementWallet,
    UpcomingPaymentSummaryForReimbursementWallet,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.pytests.factories import (
    TreatmentProcedureFactory,
)
from eligibility.pytests import factories as e9y_factories
from pytests.factories import ChannelFactory, DefaultUserFactory, EnterpriseUserFactory
from storage.connection import db
from wallet.models.constants import (
    AlegeusCoverageTier,
    BenefitTypes,
    CardStatus,
    CategoryRuleAccessLevel,
    CategoryRuleAccessSource,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    WalletState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.pytests.factories import (
    ReimbursementAccountTypeFactory,
    ReimbursementOrganizationSettingsFactory,
    ReimbursementPlanFactory,
    ReimbursementRequestCategoryExpenseTypesFactory,
    ReimbursementRequestFactory,
    ReimbursementWalletAllowedCategorySettingsFactory,
    ReimbursementWalletBenefitFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletNonMemberDependentFactory,
    ReimbursementWalletUsersFactory,
)
from wallet.schemas.constants import ClientLayout


@pytest.fixture(scope="function")
def e9y_verification(eligibility_factories, enterprise_user):
    verification = eligibility_factories.VerificationFactory.create(
        user_id=1, organization_id=enterprise_user.organization_employee.organization_id
    )
    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as mock_get_verification_for_user, patch(
        "eligibility.EnterpriseVerificationService.get_eligible_organization_ids_for_user",
        return_value=set([enterprise_user.organization.id]),
    ):
        mock_get_verification_for_user.return_value = verification
        yield verification


@pytest.fixture(scope="function")
def e9y_member(eligibility_factories, enterprise_user):
    e9y_member = eligibility_factories.EligibilityMemberFactory.create(
        id=1, organization_id=enterprise_user.organization_employee.organization_id
    )
    with patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as mock_member_id_search:
        mock_member_id_search.return_value = e9y_member
        yield e9y_member


# TODO: configure assertions to meet pytest RFC "Pytest File and Directory Naming" requirements
def _assert_is_wallet_valid(
    wallet: ReimbursementWallet, expected_state: WalletState = WalletState.PENDING
) -> None:
    assert wallet["reimbursement_organization_settings"] is not None
    assert wallet["state"] == expected_state
    assert (
        len(
            wallet["reimbursement_organization_settings"][
                "allowed_reimbursement_categories"
            ]
        )
        == 1
    )
    assert wallet["reimbursement_organization_settings"]["survey_url"] == "fake-url"
    assert wallet["reimbursement_organization_settings"]["benefit_overview_resource"][
        "url"
    ].startswith("https://www.mavenclinic.com/resources/content/")
    assert wallet["reimbursement_organization_settings"]["benefit_faq_resource"][
        "url"
    ].startswith("https://www.mavenclinic.com/resources/content/")
    assert (
        wallet["reimbursement_organization_settings"]["reimbursement_request_maximum"]
        == 5000
    )
    assert wallet["reimbursement_organization_settings"]["debit_card_enabled"] is False
    assert wallet["zendesk_ticket_id"] is not None
    assert wallet["debit_card_eligible"] is False
    assert wallet["reimbursement_wallet_debit_card"] is None
    assert wallet


def test_get_user_wallet_empty_wallet_enabled(
    client, enterprise_user, api_helpers, eligibility_factories
):
    """
    Currently a wallet can be created for users missing the wallet_enabled attribute in the organization_employee.json
    """
    reimbursement_wallet = ReimbursementWalletFactory.create()
    channel = ChannelFactory.create()
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=reimbursement_wallet.id,
        zendesk_ticket_id=4,
        channel_id=channel.id,
    )

    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=1,
        organization_id=reimbursement_wallet.reimbursement_organization_settings.organization_id,
    )
    reimbursement_wallet.initial_eligibility_member_id = (
        e9y_member_verification.eligibility_member_id
    )

    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = e9y_member_verification
        res = client.get(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"][0]
    assert wallet["employee"]["first_name"] == e9y_member_verification.first_name
    assert wallet["employee"]["last_name"] == e9y_member_verification.last_name
    allowed_reimbursement_categories = wallet["reimbursement_organization_settings"][
        "allowed_reimbursement_categories"
    ]
    # These are currency-based categories. credit_maximum should default to 0
    assert all(
        category["credit_maximum"] == 0 and category["benefit_type"] == "CURRENCY"
        for category in allowed_reimbursement_categories
    )
    _assert_is_wallet_valid(wallet)
    # Use the zendesk_ticket_id and channel_id on the RWU
    assert wallet["zendesk_ticket_id"] == 4
    assert wallet["channel_id"] == channel.id


def test_get_user_wallet_for_wallet_enabled(
    client, enterprise_user, api_helpers, eligibility_factories
):
    enterprise_user.organization_employee.json = {"wallet_enabled": True}
    enterprise_user.profile.country_code = "US"
    enterprise_user.profile.subdivision_code = "US-NY"
    reimbursement_wallet = ReimbursementWalletFactory.create(
        state=WalletState.QUALIFIED
    )
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=reimbursement_wallet.id,
    )

    # add inactive wallet user to ensure users are properly filtered
    other_user = EnterpriseUserFactory.create(
        id=999, first_name="John", last_name="Doe"
    )
    ReimbursementWalletUsersFactory.create(
        user_id=other_user.id,
        reimbursement_wallet_id=reimbursement_wallet.id,
        type=WalletUserType.DEPENDENT,
        status=WalletUserStatus.PENDING,
    )

    reimbursement_wallet.reimbursement_wallet_benefit = (
        ReimbursementWalletBenefitFactory.create()
    )  # normally done when qualifying

    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=1,
        organization_id=reimbursement_wallet.reimbursement_organization_settings.organization_id,
    )
    reimbursement_wallet.initial_eligibility_member_id = (
        e9y_member_verification.eligibility_member_id
    )
    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = e9y_member_verification
        res = client.get(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
        )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"][0]
    assert len(wallet["members"]) == 1
    assert wallet["benefit_id"] is not None
    assert wallet["employee"]["first_name"] == e9y_member_verification.first_name
    assert wallet["employee"]["last_name"] == e9y_member_verification.last_name
    assert wallet["hdhp_status"] == "NONE"
    assert wallet["pharmacy"] is not None
    _assert_is_wallet_valid(wallet, WalletState.QUALIFIED)


def test_get_user_wallet_has_allowed_categories(
    client,
    enterprise_user,
    api_helpers,
    eligibility_factories,
    ff_test_data,
):
    enterprise_user.organization_employee.json = {"wallet_enabled": True}
    enterprise_user.profile.country_code = "US"
    enterprise_user.profile.subdivision_code = "US-NY"

    labels_with_max_and_currency_code = [
        ("label_1", None, None),
        ("label_2", None, None),
    ]
    reimbursement_wallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings__allowed_reimbursement_categories=labels_with_max_and_currency_code,
        state=WalletState.QUALIFIED,
    )

    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=reimbursement_wallet.id,
    )
    reimbursement_wallet.reimbursement_organization_settings.direct_payment_enabled = (
        True
    )
    reimbursement_wallet.reimbursement_wallet_benefit = (
        ReimbursementWalletBenefitFactory.create()
    )
    allowed_categories = (
        reimbursement_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
    )
    ReimbursementWalletAllowedCategorySettingsFactory.create(
        reimbursement_organization_settings_allowed_category_id=allowed_categories[
            0
        ].id,
        reimbursement_wallet_id=reimbursement_wallet.id,
        access_level=CategoryRuleAccessLevel.NO_ACCESS,
        access_level_source=CategoryRuleAccessSource.NO_RULES,
    )

    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=1,
        organization_id=reimbursement_wallet.reimbursement_organization_settings.organization_id,
    )
    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = e9y_member_verification
        res = client.get(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
        )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"][0]
    allowed_reimbursement_categories = wallet["reimbursement_organization_settings"][
        "allowed_reimbursement_categories"
    ]
    assert len(allowed_reimbursement_categories) == 1


def test_get_user_wallet_displays_num_credits(
    client, enterprise_user, api_helpers, eligibility_factories
):
    enterprise_user.organization_employee.json = {"wallet_enabled": True}
    enterprise_user.profile.country_code = "US"
    enterprise_user.profile.subdivision_code = "US-NY"

    num_cycles = 3
    labels_with_max_and_currency_code = [
        ("label_1", None, None),
        ("label_2", None, None),
    ]
    reimbursement_wallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings__allowed_reimbursement_categories=labels_with_max_and_currency_code,
        state=WalletState.QUALIFIED,
    )

    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=reimbursement_wallet.id,
    )
    reimbursement_wallet.reimbursement_organization_settings.direct_payment_enabled = (
        True
    )
    reimbursement_wallet.reimbursement_wallet_benefit = (
        ReimbursementWalletBenefitFactory.create()
    )  # normally done when qualifying
    for (
        allowed_category
    ) in (
        reimbursement_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
    ):
        allowed_category.benefit_type = BenefitTypes.CYCLE
        allowed_category.num_cycles = num_cycles
        category = allowed_category.reimbursement_request_category
        ReimbursementRequestCategoryExpenseTypesFactory.create(
            reimbursement_request_category=category,
            expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
        )
        year = datetime.datetime.utcnow().year
        category.reimbursement_plan = ReimbursementPlanFactory.create(
            reimbursement_account_type=ReimbursementAccountTypeFactory.create(
                alegeus_account_type="HRA"
            ),
            alegeus_plan_id="X" + category.label,
            start_date=datetime.date(year=year, month=1, day=1),
            end_date=datetime.date(year=year, month=12, day=31),
            is_hdhp=False,
        )
        ReimbursementRequestFactory.create(
            wallet=reimbursement_wallet,
            category=category,
            amount=123,
            state=ReimbursementRequestState.APPROVED,
        )
        ReimbursementRequestFactory.create(
            wallet=reimbursement_wallet,
            category=category,
            amount=123,
            cost_credit=5,
            state=ReimbursementRequestState.PENDING,
        )

    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=1,
        organization_id=reimbursement_wallet.reimbursement_organization_settings.organization_id,
    )

    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = e9y_member_verification
        res = client.get(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
        )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"][0]
    assert wallet["benefit_id"] is not None
    assert wallet["employee"]["first_name"] == e9y_member_verification.first_name
    assert wallet["employee"]["last_name"] == e9y_member_verification.last_name
    allowed_reimbursement_categories = wallet["reimbursement_organization_settings"][
        "allowed_reimbursement_categories"
    ]
    assert len(allowed_reimbursement_categories) == 2
    assert allowed_reimbursement_categories[0]["credit_maximum"] == 36
    assert allowed_reimbursement_categories[0]["credits_remaining"] == 31
    assert allowed_reimbursement_categories[0]["benefit_type"] == "CYCLE"
    assert allowed_reimbursement_categories[1]["credit_maximum"] == 36
    assert allowed_reimbursement_categories[1]["benefit_type"] == "CYCLE"


def test_get_user_wallet_displays_upcoming_procedures_happy_path(
    client,
    enterprise_user,
    api_helpers,
    eligibility_factories,
):
    enterprise_user.organization_employee.json = {"wallet_enabled": True}
    enterprise_user.profile.country_code = "US"
    enterprise_user.profile.subdivision_code = "US-NY"

    reimbursement_wallet = ReimbursementWalletFactory.create(
        state=WalletState.QUALIFIED,
    )
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=reimbursement_wallet.id,
    )

    e9y_member = eligibility_factories.EligibilityMemberFactory.create(
        id=1,
        organization_id=reimbursement_wallet.reimbursement_organization_settings.organization_id,
    )

    dummy_upcoming_payments = UpcomingPaymentsAndSummaryForReimbursementWallet(
        summary=UpcomingPaymentSummaryForReimbursementWallet(
            total_member_amount=6,
            member_method="this one should show",
            total_benefit_amount=3,
            benefit_remaining=0,
            procedure_title="IVF",
        ),
        payments=[
            PaymentRecordForReimbursementWallet(
                bill_uuid=None,
                payment_status="FAILED",
                member_amount=None,
                member_method=None,
                member_date=None,
                benefit_amount=None,
                # Not currently used in the client.
                benefit_date="",
                benefit_remaining=None,
                error_type=None,
                procedure_id=2344,
                procedure_title="Another Operation",
                created_at=datetime.datetime(2025, 11, 25),
                due_at=datetime.datetime(2025, 11, 28),
            ),
            PaymentRecordForReimbursementWallet(
                bill_uuid="d900fd16-383b-4f36-be26-8c601e37af9f",
                payment_status="NEW",
                member_amount=4,
                member_method="3234",
                member_date="2025-11-22",
                benefit_amount=4,
                # Not currently used in the client.
                benefit_date="",
                benefit_remaining=2,
                error_type=None,
                procedure_id=2342,
                procedure_title="Operation",
                created_at=datetime.datetime(2025, 11, 19),
                due_at=datetime.datetime(2025, 11, 22),
            ),
        ],
    )

    result = UpcomingPaymentsResultForReimbursementWallet(
        upcoming_payments_and_summary=dummy_upcoming_payments,
        client_layout=ClientLayout.PENDING_COST,
        show_benefit_amount=False,
        num_errors=0,
    )

    estimate_summary_result = EstimateSummaryForReimbursementWallet(
        estimate_text="Estimated Bill",
        total_estimates=1,
        total_member_estimate="$200.00",
        payment_text="Estimated Total Cost",
        estimate_bill_uuid="31cc19f8-2993-478e-bd9c-13d35cc940cb",
    )

    with patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock, patch(
        "wallet.resources.reimbursement_wallet.PaymentRecordsHelper"
    ) as payment_records_helper_mock, patch(
        "direct_payment.payments.estimates_helper.EstimatesHelper.get_estimates_summary_by_wallet",
        return_value=estimate_summary_result,
    ):
        helper_instance = Mock()
        helper_instance.get_upcoming_payments_for_reimbursement_wallet.return_value = (
            result
        )
        payment_records_helper_mock.return_value = helper_instance

        member_id_search_mock.return_value = e9y_member
        res = client.get(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
        )
        helper_instance.get_upcoming_payments_for_reimbursement_wallet.assert_called()

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"][0]
    expected_upcoming_payments_json = {
        "summary": {
            "total_member_amount": 6,
            "total_benefit_amount": 3,
            "procedure_title": "IVF",
            "member_method": "this one should show",
            "member_method_formatted": "***this one should show",
            "benefit_remaining": 0,
        },
        "payments": [
            {
                "bill_uuid": None,
                "procedure_id": 2344,
                "member_date": None,
                "procedure_title": "Another Operation",
                "member_amount": None,
                "benefit_amount": None,
                "member_method": None,
                "member_method_formatted": None,
                "error_type": None,
                "benefit_remaining": None,
                "benefit_date": "",
            },
            {
                "bill_uuid": "d900fd16-383b-4f36-be26-8c601e37af9f",
                "procedure_id": 2342,
                "member_date": "2025-11-22",
                "procedure_title": "Operation",
                "member_amount": 4,
                "benefit_amount": 4,
                "member_method": "3234",
                "member_method_formatted": "***3234",
                "error_type": None,
                "benefit_remaining": 2,
                "benefit_date": "",
            },
        ],
    }
    estimate_summary_expected_json = {
        "estimate_text": "Estimated Bill",
        "total_estimates": 1,
        "total_member_estimate": "$200.00",
        "payment_text": "Estimated Total Cost",
        "estimate_bill_uuid": "31cc19f8-2993-478e-bd9c-13d35cc940cb",
    }
    upcoming_payments_json = wallet["upcoming_payments"]
    assert upcoming_payments_json == expected_upcoming_payments_json
    # Are we properly deserializing the ClientLayout enum?
    assert wallet["payment_block"]["variant"] == "PENDING_COST"
    # Is the estimates summary block filled out as expected
    assert wallet["estimate_block"] == estimate_summary_expected_json
    # Will replace the following once the default values have been updated
    assert wallet["payment_block"]["show_benefit_amount"] is False
    assert wallet["payment_block"]["num_errors"] == 0


def test_get_user_wallet_displays_upcoming_procedures_no_display_for_no_upcoming_payments(
    client,
    enterprise_user,
    api_helpers,
    eligibility_factories,
):
    enterprise_user.organization_employee.json = {"wallet_enabled": True}
    enterprise_user.profile.country_code = "US"
    enterprise_user.profile.subdivision_code = "US-NY"

    reimbursement_wallet = ReimbursementWalletFactory.create(
        state=WalletState.QUALIFIED,
    )
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=reimbursement_wallet.id,
    )

    e9y_member = eligibility_factories.EligibilityMemberFactory.create(
        id=1,
        organization_id=reimbursement_wallet.reimbursement_organization_settings.organization_id,
    )

    dummy_upcoming_payments = UpcomingPaymentsAndSummaryForReimbursementWallet(
        summary=UpcomingPaymentSummaryForReimbursementWallet(
            total_member_amount=6,
            member_method="this one should show",
            total_benefit_amount=3,
            benefit_remaining=0,
            procedure_title="IVF",
        ),
        payments=[],
    )

    result = UpcomingPaymentsResultForReimbursementWallet(
        upcoming_payments_and_summary=dummy_upcoming_payments,
        client_layout=ClientLayout.PENDING_COST,
        show_benefit_amount=False,
        num_errors=0,
    )

    estimate_summary_result = EstimateSummaryForReimbursementWallet(
        estimate_text="Estimated Bill",
        total_estimates=1,
        total_member_estimate="$200.00",
        payment_text="Estimated Total Cost",
        estimate_bill_uuid="31cc19f8-2993-478e-bd9c-13d35cc940cb",
    )

    with patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock, patch(
        "wallet.resources.reimbursement_wallet.PaymentRecordsHelper"
    ) as payment_records_helper_mock, patch(
        "direct_payment.payments.estimates_helper.EstimatesHelper.get_estimates_summary_by_wallet",
        return_value=estimate_summary_result,
    ):
        helper_instance = Mock()
        helper_instance.get_upcoming_payments_for_reimbursement_wallet.return_value = (
            result
        )
        payment_records_helper_mock.return_value = helper_instance

        member_id_search_mock.return_value = e9y_member
        res = client.get(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
        )
        helper_instance.get_upcoming_payments_for_reimbursement_wallet.assert_called()

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"][0]

    estimate_summary_expected_json = {
        "estimate_text": "Estimated Bill",
        "total_estimates": 1,
        "total_member_estimate": "$200.00",
        "payment_text": "Estimated Total Cost",
        "estimate_bill_uuid": "31cc19f8-2993-478e-bd9c-13d35cc940cb",
    }
    assert wallet["upcoming_payments"] is None
    assert wallet["payment_block"]["variant"] == "PENDING_COST"
    # Will replace the following once the default values have been updated
    assert wallet["payment_block"]["show_benefit_amount"] is False
    assert wallet["payment_block"]["num_errors"] == 0
    # Is the estimates summary block filled out as expected?
    assert wallet["estimate_block"] == estimate_summary_expected_json


def test_get_user_wallet_displays_upcoming_procedures_null(
    client,
    enterprise_user,
    api_helpers,
    eligibility_factories,
):
    enterprise_user.organization_employee.json = {"wallet_enabled": True}
    enterprise_user.profile.country_code = "US"
    enterprise_user.profile.subdivision_code = "US-NY"

    reimbursement_wallet = ReimbursementWalletFactory.create(
        state=WalletState.QUALIFIED,
    )
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=reimbursement_wallet.id,
    )

    e9y_member = eligibility_factories.EligibilityMemberFactory.create(
        id=1,
        organization_id=reimbursement_wallet.reimbursement_organization_settings.organization_id,
    )

    dummy_upcoming_payments = None

    with patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock:
        with patch(
            "wallet.resources.reimbursement_wallet.PaymentRecordsHelper"
        ) as payment_records_helper_mock, patch(
            "direct_payment.payments.estimates_helper.EstimatesHelper.get_estimates_summary_by_wallet",
            return_value=None,
        ):
            helper_instance = Mock()
            helper_instance.get_upcoming_payments_for_reimbursement_wallet.return_value = (
                dummy_upcoming_payments
            )
            payment_records_helper_mock.return_value = helper_instance

            member_id_search_mock.return_value = e9y_member
            res = client.get(
                "/api/v1/reimbursement_wallet",
                headers=api_helpers.json_headers(enterprise_user),
            )
            helper_instance.get_upcoming_payments_for_reimbursement_wallet.assert_called()

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"][0]
    expected_upcoming_payments_json = None
    upcoming_payments_json = wallet["upcoming_payments"]
    assert upcoming_payments_json == expected_upcoming_payments_json
    assert wallet["estimate_block"] is None
    assert wallet["payment_block"] is None


def test_get_user_wallet_non_us(
    client, enterprise_user, api_helpers, eligibility_factories
):
    enterprise_user.organization_employee.json = {"wallet_enabled": True}
    enterprise_user.profile.country_code = "GB"
    reimbursement_wallet = ReimbursementWalletFactory.create(
        state=WalletState.QUALIFIED
    )
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=reimbursement_wallet.id,
    )
    reimbursement_wallet.reimbursement_wallet_benefit = (
        ReimbursementWalletBenefitFactory.create()
    )  # normally done when qualifying

    e9y_member = eligibility_factories.EligibilityMemberFactory.create(
        id=1,
        organization_id=reimbursement_wallet.reimbursement_organization_settings.organization_id,
    )
    reimbursement_wallet.initial_eligibility_member_id = e9y_member.id

    with patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = e9y_member
        res = client.get(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
        )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"][0]
    assert wallet["benefit_id"] is None
    assert wallet["pharmacy"] is None
    _assert_is_wallet_valid(wallet, WalletState.QUALIFIED)


def test_get_user_wallet_for_wallet_with_debit_card(
    client,
    enterprise_user,
    wallet_debitcardinator,
    api_helpers,
    eligibility_factories,
):
    enterprise_user.organization_employee.json = {"wallet_enabled": True}
    enterprise_user.profile.country_code = "US"
    test_wallet = ReimbursementWalletFactory.create(state=WalletState.QUALIFIED)
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=test_wallet.id,
    )
    test_wallet.reimbursement_organization_settings.debit_card_enabled = True
    wallet_debitcardinator(test_wallet, card_status=CardStatus.ACTIVE)

    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=1,
        organization_id=test_wallet.reimbursement_organization_settings.organization_id,
    )

    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = e9y_member_verification
        res = client.get(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
        )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"][0]
    assert wallet["employee"]["first_name"] == e9y_member_verification.first_name
    assert wallet["employee"]["last_name"] == e9y_member_verification.last_name
    assert wallet["reimbursement_organization_settings"]["debit_card_enabled"] is True
    assert wallet["debit_card_eligible"] is True
    assert (
        wallet["reimbursement_wallet_debit_card"]["reimbursement_wallet_id"]
        == test_wallet.id
    )
    assert (
        wallet["reimbursement_wallet_debit_card"]["card_status"]
        == CardStatus.ACTIVE.value
    )


def test_get_user_wallet_shows_rwu_dependents(
    client,
    factories,
    api_helpers,
    eligibility_factories,
):
    enterprise_user = factories.EnterpriseUserFactory.create()
    other_user = factories.EnterpriseUserFactory.create()
    enterprise_user.organization_employee.json = {"wallet_enabled": True}
    enterprise_user.profile.country_code = "US"
    test_wallet = ReimbursementWalletFactory.create(state=WalletState.QUALIFIED)
    ReimbursementWalletUsersFactory.create(
        user_id=other_user.id,
        reimbursement_wallet_id=test_wallet.id,
        type=WalletUserType.DEPENDENT,
        status=WalletUserStatus.ACTIVE,
        channel_id=None,
        zendesk_ticket_id=None,
        alegeus_dependent_id="",
    )
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=test_wallet.id,
        channel_id=None,
        zendesk_ticket_id=None,
        alegeus_dependent_id="",
    )
    test_wallet.reimbursement_organization_settings.debit_card_enabled = True

    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=1,
        organization_id=test_wallet.reimbursement_organization_settings.organization_id,
    )

    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = e9y_member_verification
        res = client.get(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
        )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"][0]
    assert wallet["employee"]["first_name"] == e9y_member_verification.first_name
    assert wallet["employee"]["last_name"] == e9y_member_verification.last_name

    employee_first_name = enterprise_user.first_name
    employee_last_name = enterprise_user.last_name
    employee_full_name = f"{employee_first_name} {employee_last_name}"
    other_user_full_name = f"{other_user.first_name} {other_user.last_name}"

    expected_dependent_names = {
        (other_user.first_name, other_user.last_name, other_user_full_name),
    }
    dependent_names = {
        (d["first_name"], d["last_name"], d["name"]) for d in wallet["dependents"]
    }
    assert expected_dependent_names == dependent_names

    expected_dependent_names.add(
        (employee_first_name, employee_last_name, employee_full_name)
    )

    member_names = {
        (d["first_name"], d["last_name"], d["name"]) for d in wallet["members"]
    }
    assert expected_dependent_names == member_names


@pytest.mark.parametrize(
    argnames="user_types,test_user_type, expected_result_size",
    argvalues=(
        (
            [WalletUserType.EMPLOYEE, WalletUserType.DEPENDENT],
            WalletUserType.EMPLOYEE,
            1,
        ),
        (
            [WalletUserType.EMPLOYEE, WalletUserType.DEPENDENT],
            WalletUserType.DEPENDENT,
            1,
        ),
        ([WalletUserType.EMPLOYEE], WalletUserType.EMPLOYEE, 1),
        ([WalletUserType.DEPENDENT], WalletUserType.DEPENDENT, 1),
    ),
    ids=[
        "Employee and Dependent Users in wallet user table - querying by Employee",
        "Employee and Dependent Users in wallet user table - querying by Dependent",
        "Employee User in wallet user table - querying by Employee",
        "Dependent User in wallet user table - querying by Dependent",
    ],
)
def test_get_multi_user_wallet(
    client,
    create_multi_member_wallet_and_users,
    api_helpers,
    eligibility_factories,
    user_types,
    test_user_type,
    expected_result_size,
):
    test_wallet, users = create_multi_member_wallet_and_users(user_types)
    test_user = users[user_types.index(test_user_type)]
    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=test_user.id,
        organization_id=test_wallet.reimbursement_organization_settings.organization_id,
    )

    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = e9y_member_verification
        res = client.get(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(test_user),
        )
        assert res.status_code == 200
        content = api_helpers.load_json(res)
        assert len(content["data"]) == expected_result_size
        wallet = content["data"][0]
        assert wallet["employee"]["first_name"] == e9y_member_verification.first_name
        assert wallet["employee"]["last_name"] == e9y_member_verification.last_name
        assert int(wallet["id"]) == test_wallet.id


def test_get_user_wallet_for_wallet_without_eligible_debit_card(
    client, enterprise_user, api_helpers, eligibility_factories
):
    enterprise_user.organization_employee.json = {"wallet_enabled": True}
    enterprise_user.profile.country_code = "US"
    wallet = ReimbursementWalletFactory.create(state=WalletState.QUALIFIED)
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )
    wallet.reimbursement_organization_settings.debit_card_enabled = True

    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=1,
        organization_id=wallet.reimbursement_organization_settings.organization_id,
    )

    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = e9y_member_verification
        res = client.get(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
        )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"][0]
    assert wallet["employee"]["first_name"] == e9y_member_verification.first_name
    assert wallet["employee"]["last_name"] == e9y_member_verification.last_name
    assert wallet["reimbursement_organization_settings"]["debit_card_enabled"] is True
    assert wallet["debit_card_eligible"] is True
    assert wallet["reimbursement_wallet_debit_card"] is None


def test_get_user_wallet_for_wallet_debit_enabled_but_ineligible(
    client, enterprise_user, api_helpers, eligibility_factories
):
    enterprise_user.organization_employee.json = {"wallet_enabled": True}
    wallet = ReimbursementWalletFactory.create(state=WalletState.QUALIFIED)
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )
    wallet.reimbursement_organization_settings.debit_card_enabled = True

    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=1,
        organization_id=wallet.reimbursement_organization_settings.organization_id,
    )

    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = e9y_member_verification
        res = client.get(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
        )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"][0]
    assert wallet["employee"]["first_name"] == e9y_member_verification.first_name
    assert wallet["employee"]["last_name"] == e9y_member_verification.last_name
    assert wallet["reimbursement_organization_settings"]["debit_card_enabled"] is True
    assert wallet["debit_card_eligible"] is True
    assert wallet["reimbursement_wallet_debit_card"] is None


def test_get_user_wallet_for_wallet_runout_state(
    client, enterprise_user, api_helpers, eligibility_factories
):
    enterprise_user.organization_employee.json = {"wallet_enabled": True}
    wallet = ReimbursementWalletFactory.create(state=WalletState.RUNOUT)
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )
    wallet.reimbursement_organization_settings.debit_card_enabled = True

    e9y_member = eligibility_factories.EligibilityMemberFactory.create(
        id=1, organization_id=wallet.reimbursement_organization_settings.organization_id
    )

    with patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = e9y_member
        res = client.get(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
        )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"][0]
    assert wallet["reimbursement_organization_settings"]["debit_card_enabled"] is True
    assert wallet["debit_card_eligible"] is False


def test_get_user_wallets_with_expired_and_qualified(
    client, enterprise_user, api_helpers, eligibility_factories
):
    # Qualified wallet must be returned first
    enterprise_user.organization_employee.json = {"wallet_enabled": True}
    expired_wallet = ReimbursementWalletFactory.create(
        state=WalletState.EXPIRED, created_at=datetime.datetime(2022, 1, 1)
    )
    wallet = ReimbursementWalletFactory.create(
        state=WalletState.QUALIFIED, created_at=datetime.datetime(2025, 1, 1)
    )
    expired_wallet_2 = ReimbursementWalletFactory.create(
        state=WalletState.EXPIRED, created_at=datetime.datetime(2020, 1, 1)
    )
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=expired_wallet.id,
    )
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=expired_wallet_2.id,
    )

    e9y_member = eligibility_factories.EligibilityMemberFactory.create(
        id=1, organization_id=wallet.reimbursement_organization_settings.organization_id
    )

    with patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = e9y_member
        res = client.get(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert len(content["data"]) == 3
    assert content["data"][0]["state"] == "QUALIFIED"
    assert content["data"][1]["state"] == "EXPIRED"
    assert content["data"][2]["state"] == "EXPIRED"


def test_get_user_wallet_no_hdhp(client, qualified_alegeus_wallet_hra, api_helpers):
    enterprise_user = qualified_alegeus_wallet_hra.employee_member

    with patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = None
        res = client.get(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
        )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"][0]
    assert wallet["hdhp_status"] == "NONE"


def test_get_user_wallet_hdhp_unmet(
    client,
    qualified_alegeus_wallet_hra,
    current_hdhp_plan,
    api_helpers,
    wallet_factories,
):
    enterprise_user = qualified_alegeus_wallet_hra.employee_member

    wallet_factories.ReimbursementWalletPlanHDHPFactory.create(
        reimbursement_plan=current_hdhp_plan,
        wallet=qualified_alegeus_wallet_hra,
        alegeus_coverage_tier=AlegeusCoverageTier.SINGLE,
    )

    with patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.get_employee_accounts"
    ) as mock_get_employee_accounts:
        member_id_search_mock.return_value = None
        mock_get_employee_accounts.return_value = (
            True,
            [
                {
                    "AccountType": "HRA",
                    "AnnualElection": 1400.00,
                    "AvailBalance": 1.99,
                    "PlanId": current_hdhp_plan.alegeus_plan_id,
                },
            ],
        )
        res = client.get(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
        )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"][0]
    assert wallet["hdhp_status"] == "UNMET"


def test_get_user_wallet_hdhp_met(
    client,
    qualified_alegeus_wallet_hra,
    current_hdhp_plan,
    api_helpers,
    wallet_factories,
):
    enterprise_user = qualified_alegeus_wallet_hra.employee_member

    wallet_factories.ReimbursementWalletPlanHDHPFactory.create(
        reimbursement_plan=current_hdhp_plan,
        wallet=qualified_alegeus_wallet_hra,
        alegeus_coverage_tier=AlegeusCoverageTier.SINGLE,
    )

    with patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock, patch(
        "wallet.utils.alegeus.enrollments.enroll_wallet.get_employee_accounts"
    ) as mock_get_employee_accounts:
        member_id_search_mock.return_value = None
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
        res = client.get(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
        )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"][0]
    assert wallet["hdhp_status"] == "MET"


def test_get_user_wallet_with_treatment(
    client, qualified_direct_payment_enabled_wallet, api_helpers
):
    enterprise_user = qualified_direct_payment_enabled_wallet.employee_member
    TreatmentProcedureFactory.create(
        reimbursement_wallet_id=qualified_direct_payment_enabled_wallet.id,
        status=TreatmentProcedureStatus.SCHEDULED,
        fertility_clinic=FertilityClinicFactory.create(name="fc"),
        fertility_clinic_location=FertilityClinicLocationFactory.create(name="fcl"),
    )
    with patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = None
        res = client.get(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"][0]
    assert wallet["treatment_block"] == {
        "clinic": "fc",
        "clinic_location": "fcl",
        "variant": "IN_TREATMENT",
    }


def test_get_user_wallet_with_multiple_treatment(
    client, qualified_direct_payment_enabled_wallet, api_helpers
):
    enterprise_user = qualified_direct_payment_enabled_wallet.employee_member
    TreatmentProcedureFactory.create(
        reimbursement_wallet_id=qualified_direct_payment_enabled_wallet.id,
        status=TreatmentProcedureStatus.SCHEDULED,
        start_date=datetime.date.today() + datetime.timedelta(days=2),
        fertility_clinic=FertilityClinicFactory.create(name="fc_1"),
        fertility_clinic_location=FertilityClinicLocationFactory.create(name="fcl_1"),
    )
    TreatmentProcedureFactory.create(
        reimbursement_wallet_id=qualified_direct_payment_enabled_wallet.id,
        status=TreatmentProcedureStatus.SCHEDULED,
        start_date=datetime.date.today() + datetime.timedelta(days=1),
        fertility_clinic=FertilityClinicFactory.create(name="fc_2"),
        fertility_clinic_location=FertilityClinicLocationFactory.create(name="fcl_2"),
    )
    TreatmentProcedureFactory.create(
        reimbursement_wallet_id=qualified_direct_payment_enabled_wallet.id,
        status=TreatmentProcedureStatus.SCHEDULED,
        start_date=datetime.date.today() + datetime.timedelta(days=1),
        fertility_clinic=FertilityClinicFactory.create(name="fc_3"),
        fertility_clinic_location=FertilityClinicLocationFactory.create(name="fcl_3"),
    )
    with patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = None
        res = client.get(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"][0]
    assert wallet["treatment_block"] == {
        "clinic": "fc_2",
        "clinic_location": "fcl_2",
        "variant": "IN_TREATMENT",
    }


@pytest.mark.parametrize(
    argnames="status",
    argvalues=[
        TreatmentProcedureStatus.COMPLETED,
        TreatmentProcedureStatus.CANCELLED,
        TreatmentProcedureStatus.PARTIALLY_COMPLETED,
    ],
)
def test_get_user_wallet_with_no_treatment(
    status, client, qualified_direct_payment_enabled_wallet, api_helpers
):
    enterprise_user = qualified_direct_payment_enabled_wallet.employee_member
    TreatmentProcedureFactory.create(
        reimbursement_wallet_id=qualified_direct_payment_enabled_wallet.id,
        status=status,
    )
    with patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = None
        res = client.get(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"][0]
    assert wallet["treatment_block"] == {
        "clinic": "",
        "clinic_location": "",
        "variant": "NONE",
    }


def test_get_user_wallet_treatment_direct_payment_not_enabled(
    client, qualified_alegeus_wallet_hra, api_helpers
):
    enterprise_user = qualified_alegeus_wallet_hra.employee_member
    with patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = None
        res = client.get(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"][0]
    assert wallet["treatment_block"] is None


@pytest.mark.parametrize(
    argnames=(
        "rr_state_1",
        "rr_state_2",
        "rr_amount_1",
        "rr_amount_2",
        "total_employer_responsibility",
        "total_member_responsibility",
        "expected_response",
    ),
    argvalues=[
        (
            ReimbursementRequestState.NEW,
            ReimbursementRequestState.PENDING,
            520_00,
            80_00,
            25_45,
            300_00,
            {
                "title": None,
                "total": 2,
                "reimbursement_text": "Estimated total return to you.",
                "expected_reimbursement_amount": "$50.90",
                "original_claim_text": "Original claims total:",
                "original_claim_amount": "$650.90",
                "reimbursement_request_uuid": None,
                "details_text": None,
                "has_cost_breakdown_available": True,
            },
        ),
        (
            ReimbursementRequestState.NEW,
            ReimbursementRequestState.DENIED,
            30_00,
            110_00,
            100_00,
            40_00,
            {
                "title": "reimbursement for service",
                "total": 1,
                "reimbursement_text": "Estimated return to you.",
                "expected_reimbursement_amount": "$100.00",
                "original_claim_text": "Original claim:",
                "original_claim_amount": "$140.00",
                "reimbursement_request_uuid": None,
                "details_text": None,
                "has_cost_breakdown_available": True,
            },
        ),
        (
            ReimbursementRequestState.APPROVED,
            ReimbursementRequestState.NEEDS_RECEIPT,
            10200_00,
            70_50,
            0,
            0,
            {
                "title": "2 claims processing",
                "total": 2,
                "reimbursement_text": None,
                "expected_reimbursement_amount": None,
                "original_claim_text": None,
                "original_claim_amount": None,
                "reimbursement_request_uuid": None,
                "details_text": "Calculating your estimated return. Tap to see claim details.",
                "has_cost_breakdown_available": False,
            },
        ),
        (
            ReimbursementRequestState.INSUFFICIENT_RECEIPT,
            ReimbursementRequestState.REFUNDED,
            10200_00,
            70_50,
            0,
            0,
            {
                "title": "reimbursement for service",
                "total": 1,
                "reimbursement_text": None,
                "expected_reimbursement_amount": None,
                "original_claim_text": "Original claim:",
                "original_claim_amount": "$10,200.00",
                "reimbursement_request_uuid": None,
                "details_text": "If you have financial responsibility, it will be deducted from your claim return.",
                "has_cost_breakdown_available": False,
            },
        ),
    ],
    ids=[
        "multiple reimbursement requests with cost breakdown data",
        "single reimbursement request with cost breakdown data",
        "multiple reimbursement requests with no cost breakdown data",
        "single reimbursement request with no cost breakdown data",
    ],
)
def test_get_user_wallet__reimbursement_request_block_with_cost_breakdowns(
    client,
    qualified_direct_payment_enabled_wallet: ReimbursementWallet,
    api_helpers,
    rr_state_1,
    rr_state_2,
    rr_amount_1,
    rr_amount_2,
    expected_response,
    total_employer_responsibility,
    total_member_responsibility,
):
    enterprise_user = qualified_direct_payment_enabled_wallet.employee_member
    enterprise_user.profile.country_code = "US"
    enterprise_user.profile.subdivision_code = "US-NY"
    qualified_direct_payment_enabled_wallet.primary_expense_type = (
        ReimbursementRequestExpenseTypes.FERTILITY
    )
    qualified_direct_payment_enabled_wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
        True
    )

    for (
        allowed_category
    ) in (
        qualified_direct_payment_enabled_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
    ):
        allowed_category.benefit_type = BenefitTypes.CURRENCY
        category = allowed_category.reimbursement_request_category
        ReimbursementRequestCategoryExpenseTypesFactory.create(
            reimbursement_request_category=category,
            expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
        )

    first_reimbursement_request = ReimbursementRequestFactory.create(
        wallet=qualified_direct_payment_enabled_wallet,
        category=category,
        amount=rr_amount_1,
        state=rr_state_1,
        benefit_currency_code="USD",
        service_provider="Fertility Center",
    )
    expected_response["reimbursement_request_uuid"] = str(
        first_reimbursement_request.id
    )
    ReimbursementRequestFactory.create(
        wallet=qualified_direct_payment_enabled_wallet,
        category=category,
        amount=rr_amount_2,
        state=rr_state_2,
        benefit_currency_code="USD",
        service_provider="Gregory House",
    )

    if expected_response["has_cost_breakdown_available"]:
        for request in qualified_direct_payment_enabled_wallet.reimbursement_requests:
            CostBreakdownFactory.create(
                wallet_id=qualified_direct_payment_enabled_wallet.id,
                reimbursement_request_id=request.id,
                total_member_responsibility=total_member_responsibility,
                total_employer_responsibility=total_employer_responsibility,
                created_at=datetime.date.today(),
            )
            CostBreakdownFactory.create(
                wallet_id=qualified_direct_payment_enabled_wallet.id,
                reimbursement_request_id=request.id,
                total_member_responsibility=777700,
                total_employer_responsibility=0,
                created_at=datetime.date.today() - datetime.timedelta(days=2),
            )

    with patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock, patch(
        "wallet.services.reimbursement_request.ReimbursementRequestService.is_cost_share_breakdown_applicable",
        return_value=True,
    ):
        member_id_search_mock.return_value = None
        res = client.get(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)

    reimbursement_request_block = content["data"][0]["reimbursement_request_block"]
    keys_to_check = [
        "title",
        "total",
        "reimbursement_text",
        "expected_reimbursement_amount",
        "original_claim_text",
        "original_claim_amount",
        "details_text",
        "has_cost_breakdown_available",
    ]
    for key in keys_to_check:
        assert reimbursement_request_block[key] == expected_response[key]


@pytest.mark.parametrize(
    argnames=("country_code", "subdivision_code", "deductible_accumulation_enabled"),
    argvalues=[("FR", "", True), ("US", "US-NY", False), ("US", "US-NY", True)],
)
def test_get_user_wallet__reimbursement_request_block_omitted_from_response(
    client,
    qualified_direct_payment_enabled_wallet: ReimbursementWallet,
    api_helpers,
    country_code,
    subdivision_code,
    deductible_accumulation_enabled,
):
    enterprise_user = qualified_direct_payment_enabled_wallet.employee_member
    enterprise_user.profile.country_code = country_code
    enterprise_user.profile.subdivision_code = subdivision_code
    qualified_direct_payment_enabled_wallet.primary_expense_type = (
        ReimbursementRequestExpenseTypes.FERTILITY
    )
    qualified_direct_payment_enabled_wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
        deductible_accumulation_enabled
    )

    for (
        allowed_category
    ) in (
        qualified_direct_payment_enabled_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
    ):
        allowed_category.benefit_type = BenefitTypes.CURRENCY
        category = allowed_category.reimbursement_request_category
        ReimbursementRequestCategoryExpenseTypesFactory.create(
            reimbursement_request_category=category,
            expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
        )

    with patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock, patch(
        "wallet.resources.reimbursement_wallet.ReimbursementRequestService.is_cost_share_breakdown_applicable",
        return_value=True,
    ):
        member_id_search_mock.return_value = None
        res = client.get(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content["data"][0]["reimbursement_request_block"] is None


# get user wallets with both member and non-member dependents
def test_get_user_wallet_set_get_dependents_true(
    client, api_helpers, enterprise_user, qualified_direct_payment_enabled_wallet
):
    res = client.get(
        "/api/v1/reimbursement_wallet?get_non_member_dependents=true",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"][0]
    assert len(wallet["dependents"]) == 0
    assert len(wallet["members"]) == 1
    assert wallet["members"][0]["id"] == enterprise_user.id
    assert wallet["members"][0]["last_name"] == enterprise_user.last_name
    assert wallet["members"][0]["first_name"] == enterprise_user.first_name


def test_get_user_wallet_set_get_dependents_false_with_non_member_dependent(
    client, api_helpers, enterprise_user, qualified_direct_payment_enabled_wallet
):
    ReimbursementWalletNonMemberDependentFactory.create(
        id=12345,
        first_name="Test",
        last_name="User",
        reimbursement_wallet_id=qualified_direct_payment_enabled_wallet.id,
    )
    res = client.get(
        "/api/v1/reimbursement_wallet?get_non_member_dependents=False",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"][0]
    members = {(u["first_name"], u["id"], u["last_name"]) for u in wallet["members"]}
    household = {
        (u["first_name"], u["id"], u["last_name"]) for u in wallet["household"]
    }

    assert household == {
        (enterprise_user.first_name, enterprise_user.id, enterprise_user.last_name),
    }
    assert members == {
        (enterprise_user.first_name, enterprise_user.id, enterprise_user.last_name),
    }
    assert len(wallet["dependents"]) == 0


# get user wallets with both member and non-member dependents
def test_get_user_wallet_set_get_dependents_true_with_non_member_dependent(
    client, api_helpers, enterprise_user, qualified_direct_payment_enabled_wallet
):
    ReimbursementWalletNonMemberDependentFactory.create(
        id=12345,
        first_name="Test",
        last_name="User",
        reimbursement_wallet_id=qualified_direct_payment_enabled_wallet.id,
    )

    # create a second RWU with both entry in both reimbursement_wallet_user
    # and organization_employee_dependent table, so we can test the dedup logic
    other_user = EnterpriseUserFactory.create(id=99, first_name="John", last_name="Doe")

    ReimbursementWalletUsersFactory.create(
        user_id=other_user.id,
        reimbursement_wallet_id=qualified_direct_payment_enabled_wallet.id,
        type=WalletUserType.DEPENDENT,
        status=WalletUserStatus.ACTIVE,
    )

    ReimbursementWalletNonMemberDependentFactory.create(
        id=23456,
        first_name=other_user.first_name,
        last_name=other_user.last_name,
        reimbursement_wallet_id=qualified_direct_payment_enabled_wallet.id,
    )

    res = client.get(
        "/api/v1/reimbursement_wallet?get_non_member_dependents=true",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"][0]
    members = {(u["first_name"], u["id"], u["last_name"]) for u in wallet["members"]}
    dependents = {
        (u["first_name"], u["id"], u["last_name"]) for u in wallet["dependents"]
    }
    household = {
        (u["first_name"], u["id"], u["last_name"]) for u in wallet["household"]
    }

    assert household == {
        ("John", 99, "Doe"),
        ("Test", 12345, "User"),
        (enterprise_user.first_name, enterprise_user.id, enterprise_user.last_name),
    }

    assert {
        (enterprise_user.first_name, enterprise_user.id, enterprise_user.last_name)
    } == household.difference(dependents)

    assert {("Test", 12345, "User")} == household.difference(members)


@pytest.mark.parametrize(
    argnames=(
        "initial_wallet_state",
        "expected_wallet_state",
    ),
    argvalues=(
        ("pending", WalletState.PENDING),
        ("DISQUALIFIED", WalletState.DISQUALIFIED),
        ("", WalletState.PENDING),  # Should not be set in logic below
        ("expired", WalletState.PENDING),
        ("RUNOUT", WalletState.PENDING),
        ("QUALIFIED", WalletState.PENDING),
    ),
)
def test_post_user_wallet(
    client,
    enterprise_user,
    api_helpers,
    eligibility_factories,
    initial_wallet_state: str,
    expected_wallet_state: WalletState,
):
    organization_settings = ReimbursementOrganizationSettingsFactory.create(
        organization_id=enterprise_user.organization.id
    )
    data = {"reimbursement_organization_settings_id": organization_settings.id}
    if initial_wallet_state != "":
        data["initial_wallet_state"] = initial_wallet_state
    else:
        assert "initial_wallet_state" not in data
    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=1,
        organization_id=enterprise_user.organization.id,
        verification_2_id=1001,
    )
    e9y_member_verification.eligibility_member_id = None

    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = e9y_member_verification
        res = client.post(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(data),
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"]
    reimbursement_wallet_user = (
        db.session.query(ReimbursementWalletUsers)
        .filter(ReimbursementWalletUsers.user_id == enterprise_user.id)
        .one()
    )

    # The "or 0" is due to the default behavior of Marshmallow's deserialization
    assert reimbursement_wallet_user.channel_id == wallet["channel_id"]
    assert (
        reimbursement_wallet_user.channel_id is not None
        and reimbursement_wallet_user.channel_id != 0
    )
    assert (
        reimbursement_wallet_user.zendesk_ticket_id or 0 == wallet["zendesk_ticket_id"]
    )

    assert wallet["employee"]["first_name"] == e9y_member_verification.first_name
    assert wallet["employee"]["last_name"] == e9y_member_verification.last_name
    assert wallet["hdhp_status"] == "NONE"
    _assert_is_wallet_valid(wallet, expected_wallet_state)

    reimbursement_wallet = (
        db.session.query(ReimbursementWallet)
        .filter(
            ReimbursementWallet.id == reimbursement_wallet_user.reimbursement_wallet_id
        )
        .one()
    )
    assert (
        reimbursement_wallet.initial_eligibility_verification_2_id
        == e9y_member_verification.verification_2_id
    )


@pytest.mark.parametrize(
    argnames=("initial_wallet_state"),
    argvalues=(
        ("pending"),
        ("DISQUALIFIED"),
        (""),
        ("expired"),
        ("RUNOUT"),
        ("QUALIFIED"),
    ),
)
def test_post_user_wallet_returns_existing_pending(
    client,
    enterprise_user,
    api_helpers,
    eligibility_factories,
    initial_wallet_state: str,
):
    reimbursement_organization_settings = (
        ReimbursementOrganizationSettingsFactory.create(
            organization_id=enterprise_user.organization.id
        )
    )
    data = {
        "initial_wallet_state": initial_wallet_state,
        "reimbursement_organization_settings_id": reimbursement_organization_settings.id,
    }
    e9y_member = eligibility_factories.EligibilityMemberFactory.create(
        id=enterprise_user.id,
        organization_id=enterprise_user.organization.id,
    )
    channel = ChannelFactory.create()
    existing_wallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings=reimbursement_organization_settings,
        initial_eligibility_member_id=e9y_member.id,
        state=WalletState.PENDING,
    )
    reimbursement_wallet_user = ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=existing_wallet.id,
        channel_id=channel.id,
        zendesk_ticket_id=randint(1, 2_000_000_000),
    )
    verification = e9y_factories.build_verification_from_member(
        enterprise_user.id, e9y_member
    )

    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        res = client.post(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(data),
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"]

    assert reimbursement_wallet_user.channel_id == wallet["channel_id"]
    assert (
        reimbursement_wallet_user.channel_id is not None
        and reimbursement_wallet_user.channel_id != 0
    )
    assert (
        reimbursement_wallet_user.zendesk_ticket_id or 0 == wallet["zendesk_ticket_id"]
    )

    assert wallet["employee"]["first_name"] == verification.first_name
    assert wallet["employee"]["last_name"] == verification.last_name
    assert wallet["hdhp_status"] == "NONE"
    assert wallet["id"] == str(existing_wallet.id)
    _assert_is_wallet_valid(wallet)


def test_post_user_wallet_creates_reimbursement_wallet_user(
    client, enterprise_user, api_helpers, eligibility_factories
):
    organization_settings = ReimbursementOrganizationSettingsFactory.create(
        organization_id=enterprise_user.organization.id
    )
    data = {"reimbursement_organization_settings_id": organization_settings.id}

    previous_reimbursement_wallet_user = db.session.query(
        ReimbursementWalletUsers
    ).one_or_none()
    assert previous_reimbursement_wallet_user is None

    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=1, organization_id=enterprise_user.organization.id
    )

    with patch(
        "eligibility.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=e9y_member_verification,
    ), patch(
        "eligibility.EnterpriseVerificationService.get_verification_for_user",
        return_value=e9y_member_verification,
    ), patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock:
        with patch(
            "wallet.services.reimbursement_wallet_messaging.send_general_ticket_to_zendesk"
        ) as zendesk_ticket_mock:
            member_id_search_mock.return_value = e9y_member_verification
            zendesk_ticket_mock.return_value = 2923
            res = client.post(
                "/api/v1/reimbursement_wallet",
                headers=api_helpers.json_headers(enterprise_user),
                data=api_helpers.json_data(data),
            )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"]
    wallet_id = int(wallet["id"])
    reimbursement_wallet_user = (
        db.session.query(ReimbursementWalletUsers)
        .filter(
            ReimbursementWalletUsers.reimbursement_wallet_id == wallet_id,
            ReimbursementWalletUsers.user_id == enterprise_user.id,
        )
        .one_or_none()
    )

    assert wallet["employee"]["first_name"] == e9y_member_verification.first_name
    assert wallet["employee"]["last_name"] == e9y_member_verification.last_name
    assert reimbursement_wallet_user is not None
    assert reimbursement_wallet_user.user_id == enterprise_user.id
    assert reimbursement_wallet_user.reimbursement_wallet_id == wallet_id

    _assert_is_wallet_valid(wallet, WalletState.PENDING)

    # Check that the zendesk ticket id and the channel id are set
    assert reimbursement_wallet_user.zendesk_ticket_id is not None
    assert (
        reimbursement_wallet_user.zendesk_ticket_id
        == wallet["zendesk_ticket_id"]
        == 2923
    )
    assert reimbursement_wallet_user.channel_id == wallet["channel_id"]
    assert reimbursement_wallet_user.channel_id is not None


def test_post_user_wallet_predenied(
    client, enterprise_user, api_helpers, eligibility_factories
):
    # pre-denial was disabled with ch4680
    organization_settings = ReimbursementOrganizationSettingsFactory.create(
        organization_id=enterprise_user.organization.id
    )
    enterprise_user.organization_employee.json = {"wallet_enabled": False}
    data = {"reimbursement_organization_settings_id": organization_settings.id}

    e9y_member = eligibility_factories.EligibilityMemberFactory.create(
        id=1, organization_id=enterprise_user.organization.id
    )

    verification = eligibility_factories.VerificationFactory.create(
        eligibility_member_id=e9y_member.id,
        organization_id=e9y_member.organization_id,
    )

    with patch(
        "eligibility.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ), patch(
        "eligibility.EnterpriseVerificationService.get_verification_for_user",
        return_value=verification,
    ), patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = e9y_member
        res = client.post(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(data),
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"]
    _assert_is_wallet_valid(wallet, WalletState.PENDING)


def test_post_user_wallet_403(
    client, enterprise_user, api_helpers, eligibility_factories
):
    enterprise_user.organization_employee.json = {"wallet_enabled": False}
    bad_org_settings_id = 12345
    data = {"reimbursement_organization_settings_id": bad_org_settings_id}

    e9y_member = eligibility_factories.EligibilityMemberFactory.create(
        id=1, organization_id=enterprise_user.organization.id
    )

    verification = eligibility_factories.VerificationFactory.create(
        eligibility_member_id=e9y_member.id,
        organization_id=e9y_member.organization_id,
    )

    with patch(
        "eligibility.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ), patch(
        "eligibility.EnterpriseVerificationService.get_verification_for_user",
        return_value=verification,
    ), patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = e9y_member
        res = client.post(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(data),
        )
    assert res.status_code == 403
    content = api_helpers.load_json(res)
    assert content["message"] == "Not Authorized for that Wallet Organization"


def test_put_user_wallet__fail_no_wallet(client, enterprise_user, api_helpers):
    data = {"state": WalletState.QUALIFIED.value}
    res = client.put(
        "/api/v1/reimbursement_wallet/abcdefg",
        headers=api_helpers.json_headers(enterprise_user),
        data=api_helpers.json_data(data),
    )
    assert res.status_code == 404


def test_put_user_wallet__fail_wallet_user_mismatch(
    client, pending_alegeus_wallet_hra, api_helpers
):
    request_user = DefaultUserFactory.create()
    data = {"state": WalletState.QUALIFIED.value}
    res = client.put(
        f"/api/v1/reimbursement_wallet/{pending_alegeus_wallet_hra.id}",
        headers=api_helpers.json_headers(request_user),
        data=api_helpers.json_data(data),
    )
    assert res.status_code == 404


def test_put_user_wallet__success_without_wallet_state_change(
    client, pending_alegeus_wallet_hra, api_helpers, eligibility_factories
):
    organization_settings = (
        pending_alegeus_wallet_hra.reimbursement_organization_settings
    )
    enterprise_user = pending_alegeus_wallet_hra.employee_member

    data = {
        "reimbursement_organization_settings_id": organization_settings.id,
        "state": WalletState.QUALIFIED.value,
    }
    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=1,
        organization_id=pending_alegeus_wallet_hra.reimbursement_organization_settings.organization_id,
    )

    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = e9y_member_verification
        res = client.put(
            f"/api/v1/reimbursement_wallet/{pending_alegeus_wallet_hra.id}",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(data),
        )
    assert res.status_code == 200
    reimbursement_wallet_user = (
        db.session.query(ReimbursementWalletUsers)
        .filter(ReimbursementWalletUsers.user_id == enterprise_user.id)
        .one()
    )

    content = api_helpers.load_json(res)
    wallet = content["data"]
    assert wallet["employee"]["first_name"] == e9y_member_verification.first_name
    assert wallet["employee"]["last_name"] == e9y_member_verification.last_name
    assert wallet["hdhp_status"] == "NONE"
    assert wallet["state"] == WalletState.PENDING
    # The "or 0" is due to the default behavior of Marshmallow's deserialization
    assert reimbursement_wallet_user.channel_id == wallet["channel_id"]
    assert (
        reimbursement_wallet_user.zendesk_ticket_id or 0 == wallet["zendesk_ticket_id"]
    )


def test_put_user_wallet__success_with_wallet_state_change(
    client, pending_alegeus_wallet_hra, api_helpers, eligibility_factories
):
    organization_settings = (
        pending_alegeus_wallet_hra.reimbursement_organization_settings
    )
    pending_alegeus_wallet_hra.state = WalletState.QUALIFIED
    enterprise_user = pending_alegeus_wallet_hra.employee_member

    data = {
        "reimbursement_organization_settings_id": organization_settings.id,
        "state": WalletState.PENDING.value,
    }
    e9y_member = eligibility_factories.EligibilityMemberFactory.create(
        id=1,
        organization_id=pending_alegeus_wallet_hra.reimbursement_organization_settings.organization_id,
    )

    with patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = e9y_member
        res = client.put(
            f"/api/v1/reimbursement_wallet/{pending_alegeus_wallet_hra.id}",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(data),
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    wallet = content["data"]
    assert wallet["state"] == WalletState.PENDING


@pytest.mark.parametrize(
    argnames=(
        "single_category_wallet",
        "expected_currency_code",
        "expected_formatted_amount",
    ),
    argvalues=[
        (("fertility", 1000000, None), "USD", "$10,000.00"),
        (("fertility", 1000000, "USD"), "USD", "$10,000.00"),
        (("fertility", 1000000, "AUD"), "AUD", "$10,000.00"),
        (("fertility", 1000000, "NZD"), "NZD", "$10,000.00"),
    ],
    ids=[
        "category-currency-is-none",
        "category-currency-is-USD",
        "category-currency-is-AUD",
        "category-currency-is-NZD",
    ],
    indirect=["single_category_wallet"],
)
def test_get_reimbursement_wallet_allowed_reimbursement_categories_has_correct_category_maximum_amount(
    client,
    enterprise_user,
    api_helpers,
    single_category_wallet: ReimbursementWallet,
    expected_currency_code: str,
    expected_formatted_amount: str,
):
    # Given

    # When
    res = client.get(
        "/api/v1/reimbursement_wallet",
        headers=api_helpers.json_headers(enterprise_user),
    )

    content = api_helpers.load_json(res)
    categories: List[dict] = content["data"][0]["reimbursement_organization_settings"][
        "allowed_reimbursement_categories"
    ]
    category: dict = categories[0]

    # Then
    assert category["reimbursement_request_category_maximum_amount"] == {
        "currency_code": expected_currency_code,
        "amount": ANY,
        "formatted_amount": expected_formatted_amount,
        "formatted_amount_truncated": ANY,
        "raw_amount": ANY,
    }


@pytest.mark.parametrize(
    argnames=(
        "category_association_config",
        "expected_currency_code",
        "expected_formatted_amount",
    ),
    argvalues=[
        (("fertility", 1000000, None), "USD", "$10,000.00"),
        (("fertility", 1000000, "USD"), "USD", "$10,000.00"),
        (("fertility", 1000000, "AUD"), "AUD", "$10,000.00"),
        (("fertility", 1000000, "NZD"), "NZD", "$10,000.00"),
    ],
    ids=[
        "category-currency-is-none",
        "category-currency-is-USD",
        "category-currency-is-AUD",
        "category-currency-is-NZD",
    ],
)
def test_post_reimbursement_wallet_allowed_reimbursement_categories_has_correct_category_maximum_amount(
    client,
    enterprise_user,
    api_helpers,
    category_association_config: Tuple[str, int, str | None],
    expected_currency_code: str,
    expected_formatted_amount: str,
    e9y_verification,
):
    # Given
    organization_settings: ReimbursementOrganizationSettings = (
        ReimbursementOrganizationSettingsFactory.create(
            organization_id=enterprise_user.organization.id,
            allowed_reimbursement_categories=[category_association_config],
        )
    )
    data: dict = {"reimbursement_organization_settings_id": organization_settings.id}

    # When
    verification = e9y_factories.build_verification_from_oe(
        user_id=enterprise_user.id,
        employee=enterprise_user.organization_employee,
    )

    with patch(
        "eligibility.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ), patch(
        "eligibility.EnterpriseVerificationService.get_verification_for_user",
        return_value=verification,
    ):
        res = client.post(
            "/api/v1/reimbursement_wallet",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(data),
        )

    content = api_helpers.load_json(res)

    categories: List[dict] = content["data"]["reimbursement_organization_settings"][
        "allowed_reimbursement_categories"
    ]
    category: dict = categories[0]

    # Then
    assert category["reimbursement_request_category_maximum_amount"] == {
        "currency_code": expected_currency_code,
        "amount": ANY,
        "formatted_amount": expected_formatted_amount,
        "formatted_amount_truncated": ANY,
        "raw_amount": ANY,
    }


@pytest.mark.parametrize(
    argnames=(
        "single_category_wallet",
        "expected_currency_code",
        "expected_formatted_amount",
    ),
    argvalues=[
        (("fertility", 1000000, None), "USD", "$10,000.00"),
        (("fertility", 1000000, "USD"), "USD", "$10,000.00"),
        (("fertility", 1000000, "AUD"), "AUD", "$10,000.00"),
        (("fertility", 1000000, "NZD"), "NZD", "$10,000.00"),
    ],
    ids=[
        "category-currency-is-none",
        "category-currency-is-USD",
        "category-currency-is-AUD",
        "category-currency-is-NZD",
    ],
    indirect=["single_category_wallet"],
)
def test_put_reimbursement_wallet_allowed_reimbursement_categories_has_correct_category_maximum_amount(
    client,
    enterprise_user,
    api_helpers,
    single_category_wallet: ReimbursementWallet,
    expected_currency_code: str,
    expected_formatted_amount: str,
):
    # Given
    organization_settings: ReimbursementOrganizationSettings = (
        single_category_wallet.reimbursement_organization_settings
    )
    enterprise_user = single_category_wallet.employee_member

    data = {
        "reimbursement_organization_settings_id": organization_settings.id,
        "state": WalletState.QUALIFIED.value,
    }
    # When
    res = client.put(
        f"/api/v1/reimbursement_wallet/{single_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
        data=api_helpers.json_data(data),
    )

    content = api_helpers.load_json(res)
    categories: List[dict] = content["data"]["reimbursement_organization_settings"][
        "allowed_reimbursement_categories"
    ]
    category: dict = categories[0]

    # Then
    assert category["reimbursement_request_category_maximum_amount"] == {
        "currency_code": expected_currency_code,
        "amount": ANY,
        "formatted_amount": expected_formatted_amount,
        "formatted_amount_truncated": ANY,
        "raw_amount": ANY,
    }


def assert_default_reimbursement_organization_configuration_flags(wallet):
    organization_settings = wallet["reimbursement_organization_settings"]
    assert organization_settings is not None
    assert organization_settings["direct_payment_enabled"] is False
    assert organization_settings["deductible_accumulation_enabled"] is False
    assert organization_settings["closed_network"] is False
    assert organization_settings["fertility_program_type"] == "CARVE OUT"
    assert organization_settings["fertility_requires_diagnosis"] is False
    assert organization_settings["fertility_allows_taxable"] is False
