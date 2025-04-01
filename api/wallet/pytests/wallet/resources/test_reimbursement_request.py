from __future__ import annotations

import datetime
import json
from typing import List
from unittest.mock import ANY, MagicMock, PropertyMock, patch

import factory
import pytest
import requests
from maven import feature_flags

from cost_breakdown.pytests.factories import CostBreakdownFactory
from models.enterprise import UserAsset
from pytests import freezegun
from wallet.constants import NUM_CREDITS_PER_CYCLE
from wallet.models.constants import (
    BenefitTypes,
    CardStatus,
    CategoryRuleAccessLevel,
    CategoryRuleAccessSource,
    InfertilityDX,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestSourceUploadSource,
    ReimbursementRequestState,
    ReimbursementRequestType,
    TaxationState,
    TaxationStateConfig,
    WalletState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.reimbursement import (
    ReimbursementOrgSettingCategoryAssociation,
    ReimbursementRequest,
)
from wallet.models.reimbursement_request_source import (
    ReimbursementRequestSource,
    ReimbursementRequestSourceRequests,
)
from wallet.models.reimbursement_wallet import (
    ReimbursementWallet,
    ReimbursementWalletAllowedCategorySettings,
)
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.pytests.factories import (
    ReimbursementClaimFactory,
    ReimbursementCycleCreditsFactory,
    ReimbursementOrgSettingCategoryAssociationFactory,
    ReimbursementOrgSettingsExpenseTypeFactory,
    ReimbursementPlanFactory,
    ReimbursementRequestCategoryExpenseTypesFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestFactory,
    ReimbursementRequestSourceFactory,
    ReimbursementRequestSourceRequestsFactory,
    ReimbursementTransactionFactory,
    ReimbursementWalletAllowedCategorySettingsFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
)
from wallet.resources.reimbursement_request import (
    get_expense_types_for_wallet,
    get_summary_currency_code,
)
from wallet.schemas.reimbursement import ReimbursementRequestDataSchema
from wallet.services.reimbursement_request import ReimbursementRequestService


@pytest.fixture
def ff_test_data():
    with feature_flags.test_data() as td:
        yield td


@pytest.fixture()
def category_maximum():
    return 7000


@pytest.fixture()
def two_category_labels():
    return ["fertility", "other"]


@pytest.fixture()
def two_category_wallet(enterprise_user, two_category_labels, category_maximum):
    enterprise_user.organization.alegeus_employer_id = 123
    currency_code = None
    wallet = ReimbursementWalletFactory.create(
        member=enterprise_user,
        reimbursement_organization_settings__allowed_reimbursement_categories=[
            (label, category_maximum, currency_code) for label in two_category_labels
        ],
        state=WalletState.QUALIFIED,
    )
    wallet.alegeus_id = 456
    for (
        allowed_category
    ) in wallet.reimbursement_organization_settings.allowed_reimbursement_categories:
        ReimbursementWalletAllowedCategorySettingsFactory.create(
            reimbursement_organization_settings_allowed_category_id=allowed_category.id,
            reimbursement_wallet_id=wallet.id,
            access_level=CategoryRuleAccessLevel.FULL_ACCESS,
            access_level_source=CategoryRuleAccessSource.NO_RULES,
        )

    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=enterprise_user.id,
    )
    ReimbursementOrgSettingsExpenseTypeFactory.create(
        reimbursement_organization_settings_id=wallet.reimbursement_organization_settings_id,
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
        taxation_status=TaxationStateConfig.SPLIT_DX_INFERTILITY,
    )
    ReimbursementOrgSettingsExpenseTypeFactory.create(
        reimbursement_organization_settings_id=wallet.reimbursement_organization_settings_id,
        expense_type=ReimbursementRequestExpenseTypes.PRESERVATION,
        taxation_status=TaxationStateConfig.NON_TAXABLE,
    )
    ReimbursementOrgSettingsExpenseTypeFactory.create(
        reimbursement_organization_settings_id=wallet.reimbursement_organization_settings_id,
        expense_type=ReimbursementRequestExpenseTypes.ADOPTION,
        taxation_status=TaxationStateConfig.ADOPTION_QUALIFIED,
    )
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category_id=wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category_id,
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
    )
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category_id=wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            1
        ].reimbursement_request_category_id,
        expense_type=ReimbursementRequestExpenseTypes.PRESERVATION,
    )
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category_id=wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            1
        ].reimbursement_request_category_id,
        expense_type=ReimbursementRequestExpenseTypes.ADOPTION,
    )
    return wallet


@pytest.fixture()
def approved_benefit_currency_reimbursement(single_category_wallet):
    category: ReimbursementOrgSettingCategoryAssociation = single_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ]

    request: ReimbursementRequest = ReimbursementRequestFactory.create(
        amount=199999,
        benefit_currency_code=category.currency_code,
        reimbursement_wallet_id=single_category_wallet.id,
        reimbursement_request_category_id=category.reimbursement_request_category_id,
        state=ReimbursementRequestState.APPROVED,
        reimbursement_type=None,
    )

    return request


@pytest.fixture()
def unapproved_benefit_currency_reimbursement(single_category_wallet):
    category: ReimbursementOrgSettingCategoryAssociation = single_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ]

    request: ReimbursementRequest = ReimbursementRequestFactory.create(
        amount=199999,
        benefit_currency_code=category.currency_code,
        reimbursement_wallet_id=single_category_wallet.id,
        reimbursement_request_category_id=category.reimbursement_request_category_id,
        state=ReimbursementRequestState.NEEDS_RECEIPT,
        reimbursement_type=None,
    )

    return request


@pytest.fixture(autouse=False)
def reimbursements(two_category_wallet):
    today = datetime.date.today()

    setup = [
        (
            0,
            [
                (100, ReimbursementRequestState.REIMBURSED, None),
                (50, ReimbursementRequestState.NEW, None),
                (75, ReimbursementRequestState.REIMBURSED, None),
                (101, ReimbursementRequestState.PENDING, None),
                (10, ReimbursementRequestState.APPROVED, None),
                (
                    10,
                    ReimbursementRequestState.DENIED,
                    ReimbursementRequestType.DEBIT_CARD,
                ),
                (10, ReimbursementRequestState.DENIED, ReimbursementRequestType.MANUAL),
                (10, ReimbursementRequestState.FAILED, None),
                (10, ReimbursementRequestState.NEEDS_RECEIPT, None),
                (10, ReimbursementRequestState.RECEIPT_SUBMITTED, None),
                (100, ReimbursementRequestState.INELIGIBLE_EXPENSE, None),
                (-50, ReimbursementRequestState.REFUNDED, None),
                (100, ReimbursementRequestState.RESOLVED, None),
                (150, ReimbursementRequestState.INSUFFICIENT_RECEIPT, None),
            ],
        ),
        (
            1,
            [
                (100, ReimbursementRequestState.NEW, None),
                (100, ReimbursementRequestState.REIMBURSED, None),
                (50, ReimbursementRequestState.NEW, None),
            ],
        ),
    ]
    requests = []
    for category_counter, amounts in setup:
        category = two_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            category_counter
        ].reimbursement_request_category
        for amount, state, reimbursement_type in amounts:
            request = ReimbursementRequestFactory.create(
                amount=amount,
                reimbursement_wallet_id=two_category_wallet.id,
                reimbursement_request_category_id=category.id,
                state=state,
                reimbursement_type=reimbursement_type,
                description="Fixture Reimbursement #" + str(len(requests)),
            )
            requests.append(request)

            ReimbursementPlanFactory.create(
                category=category,
                start_date=today - datetime.timedelta(days=2),
                end_date=today + datetime.timedelta(days=2),
            )
    return requests


def test_get_wallet_prevents_unaffiliated_user(
    client, enterprise_user, api_helpers, factories, reimbursements
):
    wallet = ReimbursementWalletFactory.create()
    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=enterprise_user.id,
        status=WalletUserStatus.ACTIVE,
        type=WalletUserType.DEPENDENT,
    )

    unaffiliated_user = factories.EnterpriseUserFactory.create()
    res = client.get(
        f"/api/v1/reimbursement_request?reimbursement_wallet_id={wallet.id}",
        headers=api_helpers.json_headers(unaffiliated_user),
    )
    assert res.status_code == 400
    content = api_helpers.load_json(res)
    assert content["errors"][0]["detail"] == "Invalid User"


def test_get_reimbursement_requests(
    client,
    enterprise_user,
    two_category_wallet,
    category_maximum,
    two_category_labels,
    api_helpers,
    reimbursements,
):
    # Given
    res = client.get(
        f"/api/v1/reimbursement_request?reimbursement_wallet_id={two_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    data = content["data"]
    meta = content["meta"]

    assert data["summary"]["reimbursement_request_maximum"] == category_maximum * len(
        two_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
    )
    assert meta["reimbursement_wallet_id"] == str(two_category_wallet.id)
    assert data["summary"]["reimbursement_spent"] == 605
    assert len(data["summary"]["category_breakdown"]) == 2
    for category in data["summary"]["category_breakdown"]:
        assert (
            category["category"]["reimbursement_request_category_maximum"]
            == category_maximum
        )
        assert category["category"]["label"] in two_category_labels
        assert category["category"]["benefit_type"] == BenefitTypes.CURRENCY.value
        assert category["category"]["is_fertility_category"] is True
        assert category["category"]["direct_payment_eligible"] is False
        assert category["category"]["is_unlimited"] is False
        assert (
            category["spent"]
            == two_category_wallet.approved_amount_by_category[
                int(category["category"]["id"])
            ]
        )
    assert len(data["summary"]["expense_types"]) == 3

    assert len(data["reimbursement_requests"]) == 16
    # check if the free text description comes through. doesn't matter which RR it is
    assert data["reimbursement_requests"][0]["description"].startswith(
        "Fixture Reimbursement #"
    )


def test_get_reimbursement_requests_label(
    client,
    enterprise_user,
    enterprise_user_asset,
    api_helpers,
    two_category_wallet,
    expense_subtypes,
):
    category: ReimbursementOrgSettingCategoryAssociation = two_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ]
    ReimbursementRequestFactory.create(
        amount=100000,
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=category.reimbursement_request_category_id,
        state=ReimbursementRequestState.PENDING,
        created_at=datetime.date.today(),
        label=ReimbursementRequest.AUTO_LABEL_FLAG,
        description="",
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
        wallet_expense_subtype=expense_subtypes["FIVF"],
    )

    res = client.get(
        f"/api/v1/reimbursement_request?reimbursement_wallet_id={two_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    data = content["data"]

    assert (
        data["reimbursement_requests"][0]["label"]
        == "Fertility - IVF (with fresh transfer)"
    )


def test_get_reimbursement_requests_with_cost_share_details(
    client,
    enterprise_user,
    two_category_wallet,
    api_helpers,
    ff_test_data,
    reimbursements,
):
    enterprise_user.profile.country_code = "US"
    enterprise_user.profile.subdivision_code = "US-NY"
    two_category_wallet.primary_expense_type = (
        ReimbursementRequestExpenseTypes.FERTILITY
    )
    two_category_wallet.reimbursement_organization_settings.direct_payment_enabled = (
        True
    )
    two_category_wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
        True
    )

    reimbursements_with_cost_breakdown = reimbursements[0:8]
    for rr in reimbursements_with_cost_breakdown:
        rr.amount = 30000
        CostBreakdownFactory.create(
            wallet_id=two_category_wallet.id,
            reimbursement_request_id=rr.id,
            total_member_responsibility=25000,
            total_employer_responsibility=5000,
            created_at=datetime.date.today(),
        )

    reimbursement_request_service = ReimbursementRequestService()
    reimbursement_requests_with_cost_share_details = (
        reimbursement_request_service.add_cost_share_details(reimbursements)
    )

    expected_cost_share_details_for_reimbursements = {
        str(rr.id): rr.cost_share_details
        for rr in reimbursement_requests_with_cost_share_details
    }

    res = client.get(
        f"/api/v1/reimbursement_request?reimbursement_wallet_id={two_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    data = content["data"]
    for resp_rr in data["reimbursement_requests"]:
        assert (
            resp_rr["cost_share_details"]
            == expected_cost_share_details_for_reimbursements[resp_rr["id"]]
        )


def test_get_reimbursement_requests_with_cost_share_details_none(
    client,
    enterprise_user,
    two_category_wallet,
    api_helpers,
    ff_test_data,
    reimbursements,
):
    enterprise_user.profile.country_code = "FR"
    enterprise_user.profile.subdivision_code = ""
    two_category_wallet.primary_expense_type = (
        ReimbursementRequestExpenseTypes.FERTILITY
    )
    two_category_wallet.reimbursement_organization_settings.deductible_accumulation_enabled = (
        False
    )

    CostBreakdownFactory.create(
        wallet_id=two_category_wallet.id,
        reimbursement_request_id=reimbursements[0].id,
        total_member_responsibility=25000,
        total_employer_responsibility=5000,
        created_at=datetime.date.today(),
    )

    res = client.get(
        f"/api/v1/reimbursement_request?reimbursement_wallet_id={two_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    data = content["data"]
    for resp_rr in data["reimbursement_requests"]:
        assert resp_rr["cost_share_details"] == None


def test_get_reimbursement_request_details(
    client,
    enterprise_user,
    enterprise_user_asset,
    api_helpers,
    two_category_wallet,
    expense_subtypes,
):
    category: ReimbursementOrgSettingCategoryAssociation = two_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ]
    rr: ReimbursementRequest = ReimbursementRequestFactory.create(
        amount=100000,
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=category.reimbursement_request_category_id,
        state=ReimbursementRequestState.PENDING,
        created_at=datetime.date.today(),
    )
    source = ReimbursementRequestSourceFactory.create(
        user_asset_id=enterprise_user_asset.id,
        reimbursement_wallet_id=two_category_wallet.id,
    )

    CostBreakdownFactory.create(
        wallet_id=two_category_wallet.id,
        reimbursement_request_id=rr.id,
        total_member_responsibility=25000,
        copay=10000,
        deductible=15000,
        total_employer_responsibility=75000,
        created_at=datetime.date.today(),
    )

    ReimbursementRequestSourceRequestsFactory.create(request=rr, source=source)
    with patch("models.enterprise.signed_cdn_url") as mock_signed_url:
        mock_signed_url.return_value = "https://maven_test_domain/test_path"

        res = client.get(
            f"/api/v1/reimbursement_request/{rr.id}",
            headers=api_helpers.json_headers(enterprise_user),
        )

    expected_member_responsibility_items = [
        {"cost": "$150.00", "label": "Deductible"},
        {"cost": "$0.00", "label": "Coinsurance"},
        {"cost": "$100.00", "label": "Copay"},
        {"cost": "$0.00", "label": "Not covered"},
    ]
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    data = content["data"]

    assert data["id"] == str(rr.id)
    assert data["label"] == rr.label
    assert data["amount"] == rr.amount
    assert data["state"] == ReimbursementRequestState.PENDING.value
    assert data["original_claim_amount"] == "$1,000.00"
    assert data["cost_breakdown_details"]["reimbursement_breakdown"]["items"][0] == {
        "cost": "$750.00",
        "label": "Maven benefit",
    }
    assert (
        data["cost_breakdown_details"]["member_responsibility_breakdown"]["items"]
        == expected_member_responsibility_items
    )
    assert (
        data["cost_breakdown_details"]["refund_explanation"]["label"]
        == "Why do I only receive a partial refund?"
    )
    assert len(data["sources"]) == 1
    assert data["sources"][0]["source_id"] == str(rr.sources[0].user_asset_id)
    assert data["sources"][0]["source_url"] == "https://maven_test_domain/test_path"


def test_get_reimbursement_request_details_no_cost_breakdown(
    client,
    enterprise_user,
    enterprise_user_asset,
    api_helpers,
    two_category_wallet,
):
    category: ReimbursementOrgSettingCategoryAssociation = two_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ]
    rr: ReimbursementRequest = ReimbursementRequestFactory.create(
        amount=100,
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=category.reimbursement_request_category_id,
        state=ReimbursementRequestState.NEW,
        created_at=datetime.date.today(),
    )
    source = ReimbursementRequestSourceFactory.create(
        user_asset_id=enterprise_user_asset.id,
        reimbursement_wallet_id=two_category_wallet.id,
    )

    ReimbursementRequestSourceRequestsFactory.create(request=rr, source=source)
    with patch("models.enterprise.signed_cdn_url") as mock_signed_url:
        mock_signed_url.return_value = "https://maven_test_domain/test_path"

        res = client.get(
            f"/api/v1/reimbursement_request/{rr.id}",
            headers=api_helpers.json_headers(enterprise_user),
        )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    data = content["data"]
    assert data["id"] == str(rr.id)
    assert data["label"] == rr.label
    assert data["amount"] == rr.amount
    assert data["state"] == ReimbursementRequestState.NEW.value
    assert "cost_breakdown_details" in data
    assert data["cost_breakdown_details"]["reimbursement_breakdown"] is None
    assert len(data["sources"]) == 1
    assert data["sources"][0]["source_id"] == str(rr.sources[0].user_asset_id)
    assert data["sources"][0]["source_url"] == "https://maven_test_domain/test_path"


def test_get_reimbursement_request_details_not_found(
    client,
    enterprise_user,
    api_helpers,
):

    res = client.get(
        "/api/v1/reimbursement_request/143",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 404


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
def test_get_reimbursement_requests_category_has_correct_category_maximum_amount(
    client,
    enterprise_user,
    api_helpers,
    single_category_wallet: ReimbursementWallet,
    expected_currency_code: str,
    expected_formatted_amount: str,
    reimbursements,
):
    # Given parameterized input

    # When
    res = client.get(
        f"/api/v1/reimbursement_request?reimbursement_wallet_id={single_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    content = api_helpers.load_json(res)
    data = content["data"]
    category: dict = data["summary"]["category_breakdown"][0]

    # Then
    assert category["category"]["reimbursement_request_category_maximum_amount"] == {
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
        (("fertility", 1000000, None), "USD", "$1,999.99"),
        (("fertility", 1000000, "USD"), "USD", "$1,999.99"),
        (("fertility", 1000000, "AUD"), "AUD", "$1,999.99"),
        (("fertility", 1000000, "NZD"), "NZD", "$1,999.99"),
    ],
    ids=[
        "category-currency-is-none",
        "category-currency-is-USD",
        "category-currency-is-AUD",
        "category-currency-is-NZD",
    ],
    indirect=["single_category_wallet"],
)
def test_get_reimbursement_requests_category_has_correct_spent_amount(
    client,
    enterprise_user,
    api_helpers,
    single_category_wallet: ReimbursementWallet,
    approved_benefit_currency_reimbursement: ReimbursementRequest,
    expected_currency_code: str,
    expected_formatted_amount: str,
    reimbursements,
):
    # Given parameterized input

    # When
    res = client.get(
        f"/api/v1/reimbursement_request?reimbursement_wallet_id={single_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    content = api_helpers.load_json(res)
    data = content["data"]
    category: dict = data["summary"]["category_breakdown"][0]

    # Then
    assert category["spent_amount"] == {
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
        (("fertility", 1000000, None), "USD", "$8,000.01"),
        (("fertility", 1000000, "USD"), "USD", "$8,000.01"),
        (("fertility", 1000000, "AUD"), "AUD", "$8,000.01"),
        (("fertility", 1000000, "NZD"), "NZD", "$8,000.01"),
    ],
    ids=[
        "category-currency-is-none",
        "category-currency-is-USD",
        "category-currency-is-AUD",
        "category-currency-is-NZD",
    ],
    indirect=["single_category_wallet"],
)
def test_get_reimbursement_requests_category_has_correct_remaining_amount(
    client,
    enterprise_user,
    api_helpers,
    single_category_wallet: ReimbursementWallet,
    approved_benefit_currency_reimbursement: ReimbursementRequest,
    expected_currency_code: str,
    expected_formatted_amount: str,
    reimbursements,
):
    # Given parameterized input

    # When
    res = client.get(
        f"/api/v1/reimbursement_request?reimbursement_wallet_id={single_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    content = api_helpers.load_json(res)
    data = content["data"]
    category: dict = data["summary"]["category_breakdown"][0]

    # Then
    assert category["remaining_amount"] == {
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
        (("fertility", 1000000, None), "USD", "$1,999.99"),
        (("fertility", 1000000, "USD"), "USD", "$1,999.99"),
        (("fertility", 1000000, "AUD"), "AUD", "$1,999.99"),
        (("fertility", 1000000, "NZD"), "NZD", "$1,999.99"),
    ],
    ids=[
        "category-currency-is-none",
        "category-currency-is-USD",
        "category-currency-is-AUD",
        "category-currency-is-NZD",
    ],
    indirect=["single_category_wallet"],
)
def test_get_reimbursement_requests_transaction_history_has_correct_benefit_amount(
    client,
    enterprise_user,
    api_helpers,
    single_category_wallet: ReimbursementWallet,
    approved_benefit_currency_reimbursement: ReimbursementRequest,
    expected_currency_code: str,
    expected_formatted_amount: str,
    reimbursements,
):
    # Given parameterized input

    # When
    res = client.get(
        f"/api/v1/reimbursement_request?reimbursement_wallet_id={single_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    content = api_helpers.load_json(res)
    data = content["data"]
    reimbursement_request: dict = data["reimbursement_requests"][0]

    # Then
    assert reimbursement_request["benefit_amount"] == {
        "currency_code": expected_currency_code,
        "amount": ANY,
        "formatted_amount": expected_formatted_amount,
        "formatted_amount_truncated": ANY,
        "raw_amount": ANY,
    }


def test_get_wallet_works_for_multiple_wallets_with_rwu(
    client,
    enterprise_user,
    two_category_wallet,
    category_maximum,
    two_category_labels,
    api_helpers,
    reimbursements,
):
    wallet_2 = ReimbursementWalletFactory.create()

    # Should already have RWU for the first wallet.
    user_already_exists = (
        ReimbursementWalletUsers.query.filter(
            ReimbursementWalletUsers.user_id == enterprise_user.id,
            ReimbursementWalletUsers.reimbursement_wallet_id == two_category_wallet.id,
        ).count()
        == 1
    )
    assert user_already_exists

    # RWU for the second wallet.
    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet_2.id,
        user_id=enterprise_user.id,
    )

    num_wallets_for_user = ReimbursementWalletUsers.query.filter(
        ReimbursementWalletUsers.user_id == enterprise_user.id
    ).count()
    assert num_wallets_for_user == 2

    res = client.get(
        f"/api/v1/reimbursement_request?reimbursement_wallet_id={two_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    data = content["data"]
    meta = content["meta"]

    assert data["summary"]["reimbursement_request_maximum"] == category_maximum * len(
        two_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
    )
    assert meta["reimbursement_wallet_id"] == str(two_category_wallet.id)
    assert data["summary"]["reimbursement_spent"] == 605
    assert len(data["summary"]["category_breakdown"]) == 2
    for category in data["summary"]["category_breakdown"]:
        assert (
            category["category"]["reimbursement_request_category_maximum"]
            == category_maximum
        )
        assert category["category"]["label"] in two_category_labels
        assert category["category"]["benefit_type"] == BenefitTypes.CURRENCY.value
        assert category["category"]["is_fertility_category"] is True
        assert category["category"]["direct_payment_eligible"] is False
        assert (
            category["spent"]
            == two_category_wallet.approved_amount_by_category[
                int(category["category"]["id"])
            ]
        )

    assert len(data["reimbursement_requests"]) == 16


def test_get_reimbursement_requests_with_category(
    api_helpers, client, enterprise_user, two_category_wallet, reimbursements
):
    category = two_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ].reimbursement_request_category
    # direct billing requests should be filtered out
    ReimbursementRequestFactory.create(
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=category.id,
        reimbursement_type=ReimbursementRequestType.DIRECT_BILLING,
        state=ReimbursementRequestState.APPROVED,
    )
    res = client.get(
        f"/api/v1/reimbursement_request?reimbursement_wallet_id={two_category_wallet.id}&category={category.label}",
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content["meta"]["reimbursement_wallet_id"] == str(two_category_wallet.id)
    assert len(content["data"]["summary"]["category_breakdown"]) == 1
    category_breakdown = content["data"]["summary"]["category_breakdown"][0]
    assert category_breakdown["category"]["benefit_type"] == BenefitTypes.CURRENCY.value
    assert category_breakdown["category"]["is_fertility_category"] is True
    assert category_breakdown["category"]["direct_payment_eligible"] is False
    assert category_breakdown["category"]["id"] == str(category.id)


def test_get_reimbursement_requests_cycle_based(
    api_helpers, client, enterprise_user, reimbursements
):
    plans = ReimbursementPlanFactory.create_batch(
        size=2,
        alegeus_plan_id=factory.Iterator(["FAMILYFUND1", "FAMILYFUND2"]),
        start_date=datetime.date(year=2020, month=1, day=3),
        end_date=datetime.date(year=2199, month=12, day=31),
        is_hdhp=False,
    )
    wallet = ReimbursementWalletFactory.create(
        member=enterprise_user, state=WalletState.QUALIFIED
    )
    wallet.reimbursement_organization_settings.organization.alegeus_employer_id = "123"
    wallet.alegeus_id = "456"

    # Configure Reimbursement Plan for wallet
    org_settings = wallet.reimbursement_organization_settings
    org_settings.direct_payment_enabled = True
    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=wallet.id,
        user_id=enterprise_user.id,
        status=WalletUserStatus.ACTIVE,
        type=WalletUserType.DEPENDENT,
    )
    allowed_category1 = ReimbursementOrgSettingCategoryAssociationFactory.create(
        benefit_type=BenefitTypes.CYCLE,
        reimbursement_organization_settings=org_settings,
        reimbursement_request_category=ReimbursementRequestCategoryFactory.create(
            label="happiness", reimbursement_plan=plans[0]
        ),
        reimbursement_request_category_maximum=0,
        num_cycles=2,
    )
    allowed_category2 = ReimbursementOrgSettingCategoryAssociationFactory.create(
        benefit_type=BenefitTypes.CYCLE,
        reimbursement_organization_settings=org_settings,
        reimbursement_request_category=ReimbursementRequestCategoryFactory.create(
            label="happiness", reimbursement_plan=plans[1]
        ),
        reimbursement_request_category_maximum=0,
        num_cycles=3,
    )

    ReimbursementCycleCreditsFactory.create(
        reimbursement_wallet_id=wallet.id,
        reimbursement_organization_settings_allowed_category_id=allowed_category1.id,
        amount=2 * NUM_CREDITS_PER_CYCLE - 2,
    )

    ReimbursementCycleCreditsFactory.create(
        reimbursement_wallet_id=wallet.id,
        reimbursement_organization_settings_allowed_category_id=allowed_category2.id,
        amount=3 * NUM_CREDITS_PER_CYCLE - 1,
    )

    res = client.get(
        f"/api/v1/reimbursement_request?reimbursement_wallet_id={wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    data = content["data"]
    meta = content["meta"]

    assert meta["reimbursement_wallet_id"] == str(wallet.id)
    assert len(data["summary"]["category_breakdown"]) == 3
    categories = data["summary"]["category_breakdown"]
    categories.sort(key=lambda ctg_dict: ctg_dict["category"]["credits_remaining"])

    assert categories[0]["category"]["benefit_type"] == "CURRENCY"
    assert categories[0]["category"]["credit_maximum"] == 0
    assert categories[0]["category"]["credits_remaining"] == 0

    assert categories[1]["category"]["benefit_type"] == "CYCLE"
    assert categories[1]["category"]["credit_maximum"] == 2 * NUM_CREDITS_PER_CYCLE
    assert (
        categories[1]["category"]["credits_remaining"] == 2 * NUM_CREDITS_PER_CYCLE - 2
    )

    assert categories[2]["category"]["benefit_type"] == "CYCLE"
    assert categories[2]["category"]["credit_maximum"] == 3 * NUM_CREDITS_PER_CYCLE
    assert (
        categories[2]["category"]["credits_remaining"] == 3 * NUM_CREDITS_PER_CYCLE - 1
    )


def test_reimbursement_requests_with_category_does_not_go_negative(
    client,
    enterprise_user,
    two_category_wallet,
    category_maximum,
    two_category_labels,
    api_helpers,
    reimbursements,
):
    category = two_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        -1
    ].reimbursement_request_category
    ReimbursementRequestFactory.create(
        amount=-800,
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=category.id,
        state=ReimbursementRequestState.REFUNDED,
        reimbursement_type=None,
    )
    # direct billing requests should be filtered out
    ReimbursementRequestFactory.create(
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=category.id,
        reimbursement_type=ReimbursementRequestType.DIRECT_BILLING,
        state=ReimbursementRequestState.APPROVED,
    )
    res = client.get(
        f"/api/v1/reimbursement_request?reimbursement_wallet_id={two_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    data = content["data"]
    meta = content["meta"]

    assert meta["reimbursement_wallet_id"] == str(two_category_wallet.id)
    assert data["summary"]["reimbursement_spent"] == 0
    assert len(data["summary"]["category_breakdown"]) == 2
    for category in data["summary"]["category_breakdown"]:
        assert (
            category["category"]["reimbursement_request_category_maximum"]
            == category_maximum
        )
        assert (
            category["spent"]
            == two_category_wallet.approved_amount_by_category[
                int(category["category"]["id"])
            ]
        )

    assert len(data["reimbursement_requests"]) == 17


def test_get_reimbursement_request_with_source(
    api_helpers,
    client,
    enterprise_user,
    enterprise_user_asset,
    two_category_wallet,
    reimbursements,
):
    today = datetime.date.today()

    new_category = ReimbursementRequestCategoryFactory.create(
        label="One Request Category"
    )

    ReimbursementPlanFactory.create(
        category=new_category,
        start_date=today - datetime.timedelta(days=4),
        end_date=today - datetime.timedelta(days=2),
    )

    ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_request_category=new_category,
        reimbursement_organization_settings=two_category_wallet.reimbursement_organization_settings,
        reimbursement_request_category_maximum=0,
    )
    source = ReimbursementRequestSourceFactory.create(
        user_asset_id=enterprise_user_asset.id,
        reimbursement_wallet_id=two_category_wallet.id,
    )
    new_request = ReimbursementRequestFactory.create(
        amount=0,
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=new_category.id,
        state=ReimbursementRequestState.APPROVED,
    )
    ReimbursementRequestSourceRequestsFactory.create(request=new_request, source=source)

    # direct billing requests should be filtered out
    ReimbursementRequestFactory.create(
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=new_category.id,
        reimbursement_type=ReimbursementRequestType.DIRECT_BILLING,
        state=ReimbursementRequestState.APPROVED,
    )
    with patch("admin.views.auth.AdminAuth.is_accessible") as mock_permissions:
        mock_permissions.return_value = True
        with patch.object(UserAsset, "direct_download_url") as mock_direct_download_url:
            mock_direct_download_url.return_value = "https://some_url"
            res = client.get(
                f"/api/v1/reimbursement_request?reimbursement_wallet_id={two_category_wallet.id}&category={new_category.label}",
                headers=api_helpers.json_headers(enterprise_user),
            )
            # ensure we make a call to direct_download_url with inline=True
            mock_direct_download_url.assert_any_call(inline=True)

    assert res.status_code == 200
    content = api_helpers.load_json(res)

    assert content["meta"]["category"] == new_category.label
    assert len(content["data"]["reimbursement_requests"]) == 1
    source = content["data"]["reimbursement_requests"][0]["source"]
    assert source["type"] == "user_asset"
    assert source["content_type"] == "image/png"
    assert source["source_url"] == "https://some_url"
    assert source["inline_url"] == "https://some_url"
    assert source["source_id"] == str(new_request.sources[0].user_asset_id)


def test_get_reimbursement_request_with_sources(
    api_helpers, client, enterprise_user, enterprise_user_assets, two_category_wallet
):
    today = datetime.date.today()

    new_category = ReimbursementRequestCategoryFactory.create(
        label="One Request Category"
    )

    ReimbursementPlanFactory.create(
        category=new_category,
        start_date=today - datetime.timedelta(days=4),
        end_date=today - datetime.timedelta(days=2),
    )

    ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_request_category=new_category,
        reimbursement_organization_settings=two_category_wallet.reimbursement_organization_settings,
        reimbursement_request_category_maximum=0,
    )

    source_1 = ReimbursementRequestSourceFactory.create(
        user_asset_id=enterprise_user_assets[0].id,
        reimbursement_wallet_id=two_category_wallet.id,
    )

    source_2 = ReimbursementRequestSourceFactory.create(
        user_asset_id=enterprise_user_assets[1].id,
        reimbursement_wallet_id=two_category_wallet.id,
    )

    new_request = ReimbursementRequestFactory.create(
        amount=0,
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=new_category.id,
        state=ReimbursementRequestState.RECEIPT_SUBMITTED,
    )

    ReimbursementRequestSourceRequestsFactory.create(
        request=new_request, source=source_1
    )

    ReimbursementRequestSourceRequestsFactory.create(
        request=new_request, source=source_2
    )

    with patch("models.enterprise.signed_cdn_url") as mock_signed_cdn_url:
        mock_signed_cdn_url.return_value = "https://asset.mvnctl.net/o/1122207684793237465?Expires=1659716016&KeyName=thumbor-user-files-20190822&Signature=WQCYn06LHMFbu2829NpjBKwoGzk="
        res = client.get(
            f"/api/v1/reimbursement_request?reimbursement_wallet_id={two_category_wallet.id}&category={new_category.label}",
            headers=api_helpers.json_headers(enterprise_user),
        )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content["meta"]["category"] == new_category.label
    assert len(content["data"]["reimbursement_requests"]) == 1
    sources = content["data"]["reimbursement_requests"][0]["sources"]
    assert len(sources) == 2
    assert sources[0]["type"] == "user_asset"
    assert (
        sources[0]["source_url"]
        == "https://asset.mvnctl.net/o/1122207684793237465?Expires=1659716016&KeyName=thumbor-user-files-20190822&Signature=WQCYn06LHMFbu2829NpjBKwoGzk="
    )
    assert sources[0]["source_id"] == str(new_request.sources[0].user_asset_id)
    assert sources[1]["type"] == "user_asset"
    assert (
        sources[1]["source_url"]
        == "https://asset.mvnctl.net/o/1122207684793237465?Expires=1659716016&KeyName=thumbor-user-files-20190822&Signature=WQCYn06LHMFbu2829NpjBKwoGzk="
    )
    assert sources[1]["source_id"] == str(new_request.sources[1].user_asset_id)
    assert content["data"]["reimbursement_requests"][0]["state"] == "RECEIPT_SUBMITTED"


def test_service_end_date_defaults_to_service_start_date(
    enterprise_user, enterprise_user_asset, two_category_wallet
):
    new_category = ReimbursementRequestCategoryFactory.create(
        label="One Request Category"
    )

    ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_request_category=new_category,
        reimbursement_organization_settings=two_category_wallet.reimbursement_organization_settings,
        reimbursement_request_category_maximum=0,
    )
    request = ReimbursementRequestFactory.create(
        amount=0,
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=new_category.id,
        state=ReimbursementRequestState.APPROVED,
    )

    # Need to use request.service_end_date.date() because the fixture sets the service_start_date
    # to be a date instead of datetime.
    assert request.service_start_date == request.service_end_date.date()


def test_setting_service_end_date_actually_sets_it(
    enterprise_user, enterprise_user_asset, two_category_wallet
):
    new_category = ReimbursementRequestCategoryFactory.create(
        label="One Request Category"
    )

    ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_request_category=new_category,
        reimbursement_organization_settings=two_category_wallet.reimbursement_organization_settings,
        reimbursement_request_category_maximum=0,
    )

    today = datetime.datetime.today()
    start_date = today - datetime.timedelta(days=1)
    request = ReimbursementRequestFactory.create(
        amount=0,
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=new_category.id,
        state=ReimbursementRequestState.APPROVED,
        service_start_date=start_date,
        service_end_date=today,
    )
    assert request.service_start_date == start_date
    assert request.service_end_date == today


def test_get_reimbursement_request_with_reimbursement_type(
    api_helpers, client, enterprise_user, two_category_wallet, reimbursements
):
    new_category = ReimbursementRequestCategoryFactory.create(
        label="One Request Category"
    )

    ReimbursementRequestFactory.create(
        amount=0,
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=new_category.id,
        state=ReimbursementRequestState.APPROVED,
        reimbursement_type=ReimbursementRequestType.DEBIT_CARD,
    )

    res = client.get(
        f"/api/v1/reimbursement_request?reimbursement_wallet_id={two_category_wallet.id}&category={new_category.label}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert (
        content["data"]["reimbursement_requests"][0]["reimbursement_type"]
        == "DEBIT_CARD"
    )


def test_get_reimbursement_request_with_default_reimbursement_type(
    api_helpers, client, enterprise_user, two_category_wallet, reimbursements
):
    new_category = ReimbursementRequestCategoryFactory.create(
        label="One Request Category"
    )

    ReimbursementRequestFactory.create(
        amount=0,
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=new_category.id,
        state=ReimbursementRequestState.APPROVED,
    )

    res = client.get(
        f"/api/v1/reimbursement_request?reimbursement_wallet_id={two_category_wallet.id}&category={new_category.label}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert (
        content["data"]["reimbursement_requests"][0]["reimbursement_type"] == "MANUAL"
    )


def test_assigns_user_assets_to_wallet_reimbursement_request(
    api_helpers, client, enterprise_user, enterprise_user_asset, two_category_wallet
):
    today = datetime.date.today()

    new_category = ReimbursementRequestCategoryFactory.create(
        label="One Request Category"
    )

    ReimbursementPlanFactory.create(
        category=new_category,
        start_date=today - datetime.timedelta(days=4),
        end_date=today - datetime.timedelta(days=2),
    )

    ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_request_category=new_category,
        reimbursement_organization_settings=two_category_wallet.reimbursement_organization_settings,
        reimbursement_request_category_maximum=0,
    )

    new_request = ReimbursementRequestFactory.create(
        amount=0,
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=new_category.id,
        state=ReimbursementRequestState.APPROVED,
        reimbursement_type=ReimbursementRequestType.DEBIT_CARD,
    )

    ReimbursementTransactionFactory.create(reimbursement_request_id=new_request.id)

    mock_blob_instance = MagicMock()
    mock_blob_instance.download_as_bytes = lambda: b"testblob"
    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
    ) as mock_api_request, patch(
        "models.enterprise.UserAsset.blob", new_callable=PropertyMock
    ) as mock_blob, patch(
        "models.enterprise.signed_cdn_url"
    ) as mock_signed_url, patch(
        "wallet.tasks.document_mapping.map_reimbursement_request_documents.delay"
    ) as mock_document_mapper, patch(
        "wallet.resources.reimbursement_request.receipt_validation_ops_view_enabled",
        return_value=True,
    ):
        mock_signed_url.return_value = "https://maven_test_domain/test_path"
        mock_api_request.return_value = requests.Response()
        mock_api_request.return_value.status_code = 200
        mock_blob.return_value = mock_blob_instance

        res = client.post(
            f"/api/v1/reimbursement_request/{new_request.id}/sources",
            headers=api_helpers.json_headers(enterprise_user),
            data=json.dumps({"user_asset_id": enterprise_user_asset.id}),
        )

    reimbursement_request_source = ReimbursementRequestSource.query.filter_by(
        user_asset_id=enterprise_user_asset.id, wallet=two_category_wallet
    ).one_or_none()

    reimbursement_request_source_requests = (
        ReimbursementRequestSourceRequests.query.filter_by(
            reimbursement_request_id=new_request.id
        ).one_or_none()
    )

    assert res.status_code == 201
    content = api_helpers.load_json(res)
    assert content["file_name"] == "img.png"
    assert content["source_url"] == "https://maven_test_domain/test_path"
    assert content["source_id"] == str(reimbursement_request_source.source_id)
    assert content["type"] == "user_asset"
    assert (
        reimbursement_request_source_requests.reimbursement_request_id == new_request.id
    )

    assert (
        reimbursement_request_source.id
        == reimbursement_request_source_requests.reimbursement_request_source_id
    )
    assert (
        reimbursement_request_source.upload_source
        == ReimbursementRequestSourceUploadSource.POST_SUBMISSION
    )
    assert mock_api_request.call_count == 1
    assert mock_document_mapper.call_count == 1


def test_assigns_user_assets_to_wallet_reimbursement_request__manual_claim(
    api_helpers, client, enterprise_user, enterprise_user_asset, two_category_wallet
):
    today = datetime.date.today()

    new_category = ReimbursementRequestCategoryFactory.create(
        label="One Request Category"
    )

    ReimbursementPlanFactory.create(
        category=new_category,
        start_date=today - datetime.timedelta(days=4),
        end_date=today - datetime.timedelta(days=2),
    )

    ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_request_category=new_category,
        reimbursement_organization_settings=two_category_wallet.reimbursement_organization_settings,
        reimbursement_request_category_maximum=0,
    )

    new_request = ReimbursementRequestFactory.create(
        amount=0,
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=new_category.id,
        state=ReimbursementRequestState.APPROVED,
    )

    ReimbursementClaimFactory.create(
        reimbursement_request_id=new_request.id, alegeus_claim_key="1234test"
    )

    mock_blob_instance = MagicMock()
    mock_blob_instance.download_as_bytes = lambda: b"testblob"
    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
    ) as mock_api_request, patch(
        "models.enterprise.UserAsset.blob", new_callable=PropertyMock
    ) as mock_blob, patch(
        "models.enterprise.signed_cdn_url"
    ) as mock_signed_url, patch(
        "wallet.tasks.document_mapping.map_reimbursement_request_documents.delay"
    ) as mock_document_mapper, patch(
        "wallet.resources.reimbursement_request.receipt_validation_ops_view_enabled",
        return_value=True,
    ):
        mock_signed_url.return_value = "https://maven_test_domain/test_path"
        mock_api_request.return_value = requests.Response()
        mock_api_request.return_value.status_code = 200
        mock_blob.return_value = mock_blob_instance

        res = client.post(
            f"/api/v1/reimbursement_request/{new_request.id}/sources",
            headers=api_helpers.json_headers(enterprise_user),
            data=json.dumps({"user_asset_id": enterprise_user_asset.id}),
        )

    reimbursement_request_source = ReimbursementRequestSource.query.filter_by(
        user_asset_id=enterprise_user_asset.id, wallet=two_category_wallet
    ).one_or_none()

    reimbursement_request_source_requests = (
        ReimbursementRequestSourceRequests.query.filter_by(
            reimbursement_request_id=new_request.id
        ).one_or_none()
    )

    assert res.status_code == 201
    content = api_helpers.load_json(res)
    assert content["file_name"] == "img.png"
    assert content["source_url"] == "https://maven_test_domain/test_path"
    assert content["source_id"] == str(reimbursement_request_source.source_id)
    assert content["type"] == "user_asset"
    assert (
        reimbursement_request_source_requests.reimbursement_request_id == new_request.id
    )

    assert (
        reimbursement_request_source.id
        == reimbursement_request_source_requests.reimbursement_request_source_id
    )
    assert (
        reimbursement_request_source.upload_source
        == ReimbursementRequestSourceUploadSource.POST_SUBMISSION
    )
    assert mock_api_request.call_count == 1
    assert mock_document_mapper.call_count == 1


def test_aborts_when_invalid_reimbursement_request_id(
    api_helpers, client, enterprise_user, enterprise_user_asset, two_category_wallet
):
    today = datetime.date.today()

    new_category = ReimbursementRequestCategoryFactory.create(
        label="One Request Category"
    )

    ReimbursementPlanFactory.create(
        category=new_category,
        start_date=today - datetime.timedelta(days=4),
        end_date=today - datetime.timedelta(days=2),
    )

    ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_request_category=new_category,
        reimbursement_organization_settings=two_category_wallet.reimbursement_organization_settings,
        reimbursement_request_category_maximum=0,
    )

    res = client.post(
        "/api/v1/reimbursement_request/123456789/sources",
        headers=api_helpers.json_headers(enterprise_user),
        data=json.dumps({"user_asset_id": enterprise_user_asset.id}),
    )

    assert res.status_code == 404
    content = api_helpers.load_json(res)
    assert (
        content["message"]
        == "Could not find ReimbursementRequest by reimbursement request id 123456789."
    )


def test_aborts_when_invalid_asset_id(
    api_helpers, client, enterprise_user, two_category_wallet
):
    today = datetime.date.today()

    new_category = ReimbursementRequestCategoryFactory.create(
        label="One Request Category"
    )

    ReimbursementPlanFactory.create(
        category=new_category,
        start_date=today - datetime.timedelta(days=4),
        end_date=today - datetime.timedelta(days=2),
    )

    ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_request_category=new_category,
        reimbursement_organization_settings=two_category_wallet.reimbursement_organization_settings,
        reimbursement_request_category_maximum=0,
    )

    new_request = ReimbursementRequestFactory.create(
        amount=0,
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=new_category.id,
        state=ReimbursementRequestState.APPROVED,
    )

    res = client.post(
        f"/api/v1/reimbursement_request/{new_request.id}/sources",
        headers=api_helpers.json_headers(enterprise_user),
        data=json.dumps({"user_asset_id": 123}),
    )

    assert res.status_code == 404
    content = api_helpers.load_json(res)
    assert content["message"] == "Could not find user asset by id 123."


def test_get_reimbursement_requests_with_state(
    client,
    enterprise_user,
    two_category_wallet,
    category_maximum,
    two_category_labels,
    api_helpers,
    ff_test_data,
    reimbursements,
):
    # Given
    res = client.get(
        f"/api/v1/reimbursement_request/state?reimbursement_wallet_id={two_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    data = content["data"]
    meta = content["meta"]
    assert meta["reimbursement_wallet_id"] == str(two_category_wallet.id)
    assert data["summary"]["reimbursement_spent"] == 605
    assert len(data["summary"]["category_breakdown"]) == 2
    for category in data["summary"]["category_breakdown"]:
        assert (
            category["category"]["reimbursement_request_category_maximum"]
            == category_maximum
        )
        assert category["category"]["label"] in two_category_labels
        assert category["category"]["benefit_type"] == BenefitTypes.CURRENCY.value
        assert category["category"]["is_fertility_category"] is True
        assert category["category"]["direct_payment_eligible"] is False
        assert category["category"]["is_unlimited"] is False
        assert (
            category["spent"]
            == two_category_wallet.approved_amount_by_category[
                int(category["category"]["id"])
            ]
        )
    assert len(data["summary"]["expense_types"]) == 3

    reimbursement_requests = data["reimbursement_requests"]

    assert len(reimbursement_requests["needs_attention"]) == 8
    assert len(reimbursement_requests["transaction_history"]) == 8
    assert len(reimbursement_requests["most_recent"]) == 3


@pytest.mark.parametrize(
    argnames=("request_state", "array_key"),
    argvalues=[
        (ReimbursementRequestState.NEW, "needs_attention"),
        (ReimbursementRequestState.PENDING, "needs_attention"),
        (ReimbursementRequestState.APPROVED, "needs_attention"),
        (ReimbursementRequestState.REIMBURSED, "transaction_history"),
        (ReimbursementRequestState.DENIED, "transaction_history"),
        (ReimbursementRequestState.FAILED, None),
        (ReimbursementRequestState.NEEDS_RECEIPT, "needs_attention"),
        (ReimbursementRequestState.RECEIPT_SUBMITTED, "needs_attention"),
        (ReimbursementRequestState.INSUFFICIENT_RECEIPT, "needs_attention"),
        (ReimbursementRequestState.INELIGIBLE_EXPENSE, "transaction_history"),
        (ReimbursementRequestState.PENDING_MEMBER_INPUT, None),
        (ReimbursementRequestState.RESOLVED, "transaction_history"),
        (ReimbursementRequestState.REFUNDED, "transaction_history"),
    ],
)
def test_get_reimbursement_requests_state_query_filter(
    client,
    enterprise_user,
    two_category_wallet,
    category_maximum,
    two_category_labels,
    api_helpers,
    request_state: ReimbursementRequestState,
    array_key: str | None,
):
    # Given
    category: ReimbursementOrgSettingCategoryAssociation = two_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ]
    request: ReimbursementRequest = ReimbursementRequestFactory.create(
        amount=100,
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=category.reimbursement_request_category_id,
        state=request_state,
    )

    # When
    res = client.get(
        f"/api/v1/reimbursement_request/state?reimbursement_wallet_id={two_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )
    content = api_helpers.load_json(res)
    data = content["data"]
    reimbursement_requests = data["reimbursement_requests"]

    # Then
    if array_key is None:
        # The reimbursement requests that should NOT show up in the response
        assert (
            not reimbursement_requests["needs_attention"]
            and not reimbursement_requests["transaction_history"]
        )
    else:
        # The reimbursement requests that should show up in the response
        assert reimbursement_requests.get(array_key)[0]["id"] == str(request.id)


@pytest.mark.parametrize(
    argnames=("num_of_requests", "expected_most_recent_len"),
    argvalues=[
        (0, 0),
        (1, 1),
        (3, 3),
        (4, 3),
    ],
)
def test_get_reimbursement_requests_state_most_recent_is_sorted(
    client,
    enterprise_user,
    two_category_wallet,
    category_maximum,
    two_category_labels,
    api_helpers,
    num_of_requests: int,
    expected_most_recent_len: int,
):
    # Given
    category: ReimbursementOrgSettingCategoryAssociation = two_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ]
    requests: list[ReimbursementRequest] = ReimbursementRequestFactory.create_batch(
        size=num_of_requests,
        amount=100,
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=category.reimbursement_request_category_id,
        state=ReimbursementRequestState.REIMBURSED,
    )
    for i, request in enumerate(requests):
        # Update the list of ascending order by created_at
        date_created_at = datetime.datetime.now(
            datetime.timezone.utc
        ) - datetime.timedelta(days=30)
        request.created_at = date_created_at + datetime.timedelta(days=i)
    # When
    res = client.get(
        f"/api/v1/reimbursement_request/state?reimbursement_wallet_id={two_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )
    content = api_helpers.load_json(res)
    data = content["data"]
    reimbursement_requests = data["reimbursement_requests"]

    # Then
    assert len(reimbursement_requests["most_recent"]) == expected_most_recent_len
    # Confirm the sorting order
    if len(reimbursement_requests["most_recent"]) == 2:
        assert (
            reimbursement_requests["most_recent"][0]["created_at"]
            > reimbursement_requests["most_recent"][1]["created_at"]
        )


def test_get_reimbursement_requests_state_most_recent_is_filtered(
    client,
    enterprise_user,
    two_category_wallet,
    category_maximum,
    two_category_labels,
    api_helpers,
):
    # Given
    category: ReimbursementOrgSettingCategoryAssociation = two_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ]
    requests: list[ReimbursementRequest] = ReimbursementRequestFactory.create_batch(
        size=3,
        amount=100,
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=category.reimbursement_request_category_id,
        state=ReimbursementRequestState.REIMBURSED,
    )
    for i, request in enumerate(requests):
        # Update 2 out of 3 requests to be past 60 days
        if i % 2 == 0:
            request.created_at = datetime.datetime.now(
                datetime.timezone.utc
            ) - datetime.timedelta(days=61)

    # When
    res = client.get(
        f"/api/v1/reimbursement_request/state?reimbursement_wallet_id={two_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )
    content = api_helpers.load_json(res)
    data = content["data"]
    reimbursement_requests = data["reimbursement_requests"]

    # Then
    assert len(reimbursement_requests["most_recent"]) == 1


@pytest.mark.parametrize(
    argnames=("request_state", "returned"),
    argvalues=[
        (ReimbursementRequestState.NEW, False),
        (ReimbursementRequestState.PENDING, True),
        (ReimbursementRequestState.APPROVED, True),
        (ReimbursementRequestState.REIMBURSED, True),
        (ReimbursementRequestState.DENIED, True),
        (ReimbursementRequestState.FAILED, False),
        (ReimbursementRequestState.NEEDS_RECEIPT, True),
        (ReimbursementRequestState.RECEIPT_SUBMITTED, True),
        (ReimbursementRequestState.INSUFFICIENT_RECEIPT, True),
        (ReimbursementRequestState.INELIGIBLE_EXPENSE, True),
        (ReimbursementRequestState.PENDING_MEMBER_INPUT, False),
        (ReimbursementRequestState.RESOLVED, True),
        (ReimbursementRequestState.REFUNDED, True),
    ],
)
def test_get_reimbursement_requests_state_fetch_correct_states_older_than_60_days(
    client,
    enterprise_user,
    two_category_wallet,
    category_maximum,
    two_category_labels,
    api_helpers,
    request_state: ReimbursementRequestState,
    returned: bool,
):
    # Given
    category: ReimbursementOrgSettingCategoryAssociation = two_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ]
    new_request: ReimbursementRequest = ReimbursementRequestFactory.create(
        amount=100,
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=category.reimbursement_request_category_id,
        state=request_state,
    )
    new_request.created_at = datetime.datetime.now(
        datetime.timezone.utc
    ) - datetime.timedelta(61)

    # When
    res = client.get(
        f"/api/v1/reimbursement_request/state?reimbursement_wallet_id={two_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )
    content = api_helpers.load_json(res)
    data = content["data"]

    # Then
    assert (
        len(
            data["reimbursement_requests"]["transaction_history"]
            + data["reimbursement_requests"]["needs_attention"]
        )
        == 1
    ) is returned


@pytest.mark.parametrize(
    argnames=("request_state", "returned"),
    argvalues=[
        (ReimbursementRequestState.NEW, True),
        (ReimbursementRequestState.PENDING, True),
        (ReimbursementRequestState.APPROVED, True),
        (ReimbursementRequestState.REIMBURSED, True),
        (ReimbursementRequestState.DENIED, True),
        (ReimbursementRequestState.FAILED, False),
        (ReimbursementRequestState.NEEDS_RECEIPT, True),
        (ReimbursementRequestState.RECEIPT_SUBMITTED, True),
        (ReimbursementRequestState.INSUFFICIENT_RECEIPT, True),
        (ReimbursementRequestState.INELIGIBLE_EXPENSE, True),
        (ReimbursementRequestState.PENDING_MEMBER_INPUT, False),
        (ReimbursementRequestState.RESOLVED, True),
        (ReimbursementRequestState.REFUNDED, True),
    ],
)
def test_get_reimbursement_requests_query_filter(
    client,
    enterprise_user,
    two_category_wallet,
    category_maximum,
    two_category_labels,
    api_helpers,
    request_state: ReimbursementRequestState,
    returned: bool,
):
    # Given
    category: ReimbursementOrgSettingCategoryAssociation = two_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ]
    ReimbursementRequestFactory.create(
        amount=100,
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=category.reimbursement_request_category_id,
        state=request_state,
    )

    # When
    res = client.get(
        f"/api/v1/reimbursement_request?reimbursement_wallet_id={two_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )
    content = api_helpers.load_json(res)
    data = content["data"]

    # Then
    assert (len(data["reimbursement_requests"]) == 1) is returned


def test_get_reimbursement_requests_fetches_new_less_than_60_days(
    client,
    enterprise_user,
    two_category_wallet,
    category_maximum,
    two_category_labels,
    api_helpers,
):
    # Given
    category: ReimbursementOrgSettingCategoryAssociation = two_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ]
    new_request: ReimbursementRequest = ReimbursementRequestFactory.create(
        amount=100,
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=category.reimbursement_request_category_id,
        state=ReimbursementRequestState.NEW,
    )
    new_request.created_at = datetime.date.today() - datetime.timedelta(days=30)

    # When
    res = client.get(
        f"/api/v1/reimbursement_request?reimbursement_wallet_id={two_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )
    content = api_helpers.load_json(res)
    data = content["data"]

    # Then
    assert data["reimbursement_requests"][0]["id"] == str(new_request.id)


@pytest.mark.parametrize(
    argnames=("request_state", "returned"),
    argvalues=[
        (ReimbursementRequestState.NEW, False),
        (ReimbursementRequestState.PENDING, True),
        (ReimbursementRequestState.APPROVED, True),
        (ReimbursementRequestState.REIMBURSED, True),
        (ReimbursementRequestState.DENIED, True),
        (ReimbursementRequestState.FAILED, False),
        (ReimbursementRequestState.NEEDS_RECEIPT, True),
        (ReimbursementRequestState.RECEIPT_SUBMITTED, True),
        (ReimbursementRequestState.INSUFFICIENT_RECEIPT, True),
        (ReimbursementRequestState.INELIGIBLE_EXPENSE, True),
        (ReimbursementRequestState.PENDING_MEMBER_INPUT, False),
        (ReimbursementRequestState.RESOLVED, True),
        (ReimbursementRequestState.REFUNDED, True),
    ],
)
def test_get_reimbursement_requests_fetch_correct_states_older_than_60_days(
    client,
    enterprise_user,
    two_category_wallet,
    category_maximum,
    two_category_labels,
    api_helpers,
    request_state: ReimbursementRequestState,
    returned: bool,
):
    # Given
    category: ReimbursementOrgSettingCategoryAssociation = two_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ]
    new_request: ReimbursementRequest = ReimbursementRequestFactory.create(
        amount=100,
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=category.reimbursement_request_category_id,
        state=request_state,
    )
    new_request.created_at = datetime.date.today() - datetime.timedelta(days=61)

    # When
    res = client.get(
        f"/api/v1/reimbursement_request?reimbursement_wallet_id={two_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )
    content = api_helpers.load_json(res)
    data = content["data"]

    # Then
    assert (len(data["reimbursement_requests"]) == 1) is returned


def test_get_reimbursement_requests_fetches_pending_older_than_60_days(
    client,
    enterprise_user,
    two_category_wallet,
    category_maximum,
    two_category_labels,
    api_helpers,
):
    # Given
    category: ReimbursementOrgSettingCategoryAssociation = two_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ]
    pending_request: ReimbursementRequest = ReimbursementRequestFactory.create(
        amount=100,
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=category.reimbursement_request_category_id,
        state=ReimbursementRequestState.PENDING,
    )
    pending_request.created_at = datetime.date.today() - datetime.timedelta(days=61)

    # When
    res = client.get(
        f"/api/v1/reimbursement_request?reimbursement_wallet_id={two_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )
    content = api_helpers.load_json(res)
    data = content["data"]

    # Then
    assert data["reimbursement_requests"][0]["id"] == str(pending_request.id)


def test_get_reimbursement_requests_fetches_pending_less_than_60_days(
    client,
    enterprise_user,
    two_category_wallet,
    category_maximum,
    two_category_labels,
    api_helpers,
):
    # Given
    category: ReimbursementOrgSettingCategoryAssociation = two_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ]
    pending_request: ReimbursementRequest = ReimbursementRequestFactory.create(
        amount=100,
        reimbursement_wallet_id=two_category_wallet.id,
        reimbursement_request_category_id=category.reimbursement_request_category_id,
        state=ReimbursementRequestState.PENDING,
    )
    pending_request.created_at = datetime.date.today() - datetime.timedelta(days=30)

    # When
    res = client.get(
        f"/api/v1/reimbursement_request?reimbursement_wallet_id={two_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )
    content = api_helpers.load_json(res)
    data = content["data"]

    # Then
    assert data["reimbursement_requests"][0]["id"] == str(pending_request.id)


@pytest.mark.parametrize(
    argnames="endpoint",
    argvalues=["/api/v1/reimbursement_request", "/api/v1/reimbursement_request/state"],
)
def test_get_reimbursement_requests_expense_types(
    endpoint,
    client,
    enterprise_user,
    two_category_wallet,
    expense_subtypes,
    category_maximum,
    two_category_labels,
    api_helpers,
    reimbursements,
):
    # Given
    expense_type_to_is_fertility_expense_mapping = {
        "Fertility": True,
        "Preservation": True,
        "Adoption": False,
    }
    expense_type_to_subtype_count_mapping = {
        "Fertility": 4,
        "Preservation": 3,
        "Adoption": 3,
    }
    res = client.get(
        f"{endpoint}?reimbursement_wallet_id={two_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    data = content["data"]

    assert len(data["summary"]["expense_types"]) == 3
    for expense_type in data["summary"]["expense_types"]:
        assert expense_type["label"] in [
            "Fertility",
            "Preservation",
            "Adoption",
        ]
        assert (
            expense_type_to_is_fertility_expense_mapping[expense_type["label"]]
            == expense_type["is_fertility_expense"]
        )
        if expense_type["label"] == "Fertility":
            assert expense_type["form_options"][0] == {
                "name": InfertilityDX.name,
                "label": InfertilityDX.label,
            }
        assert (
            len(expense_type["subtypes"])
            == expense_type_to_subtype_count_mapping[expense_type["label"]]
        )


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
def test_get_reimbursement_requests_state_category_has_correct_category_maximum_amount(
    client,
    enterprise_user,
    api_helpers,
    single_category_wallet: ReimbursementWallet,
    expected_currency_code: str,
    expected_formatted_amount: str,
    reimbursements,
):
    # Given parameterized input

    # When
    res = client.get(
        f"/api/v1/reimbursement_request/state?reimbursement_wallet_id={single_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    content = api_helpers.load_json(res)
    data = content["data"]
    category: dict = data["summary"]["category_breakdown"][0]

    # Then
    assert category["category"]["reimbursement_request_category_maximum_amount"] == {
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
        (("fertility", 1000000, None), "USD", "$1,999.99"),
        (("fertility", 1000000, "USD"), "USD", "$1,999.99"),
        (("fertility", 1000000, "AUD"), "AUD", "$1,999.99"),
        (("fertility", 1000000, "NZD"), "NZD", "$1,999.99"),
    ],
    ids=[
        "category-currency-is-none",
        "category-currency-is-USD",
        "category-currency-is-AUD",
        "category-currency-is-NZD",
    ],
    indirect=["single_category_wallet"],
)
def test_get_reimbursement_requests_state_category_has_correct_spent_amount(
    client,
    enterprise_user,
    api_helpers,
    single_category_wallet: ReimbursementWallet,
    approved_benefit_currency_reimbursement: ReimbursementRequest,
    expected_currency_code: str,
    expected_formatted_amount: str,
    reimbursements,
):
    # Given parameterized input

    # When
    res = client.get(
        f"/api/v1/reimbursement_request/state?reimbursement_wallet_id={single_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    content = api_helpers.load_json(res)
    data = content["data"]
    category: dict = data["summary"]["category_breakdown"][0]

    # Then
    assert category["spent_amount"] == {
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
        (("fertility", 1000000, None), "USD", "$8,000.01"),
        (("fertility", 1000000, "USD"), "USD", "$8,000.01"),
        (("fertility", 1000000, "AUD"), "AUD", "$8,000.01"),
        (("fertility", 1000000, "NZD"), "NZD", "$8,000.01"),
    ],
    ids=[
        "category-currency-is-none",
        "category-currency-is-USD",
        "category-currency-is-AUD",
        "category-currency-is-NZD",
    ],
    indirect=["single_category_wallet"],
)
def test_get_reimbursement_requests_state_category_has_correct_remaining_amount(
    client,
    enterprise_user,
    api_helpers,
    single_category_wallet: ReimbursementWallet,
    approved_benefit_currency_reimbursement: ReimbursementRequest,
    expected_currency_code: str,
    expected_formatted_amount: str,
    reimbursements,
):
    # Given parameterized input

    # When
    res = client.get(
        f"/api/v1/reimbursement_request/state?reimbursement_wallet_id={single_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    content = api_helpers.load_json(res)
    data = content["data"]
    category: dict = data["summary"]["category_breakdown"][0]

    # Then
    assert category["remaining_amount"] == {
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
        (("fertility", 1000000, None), "USD", "$1,999.99"),
        (("fertility", 1000000, "USD"), "USD", "$1,999.99"),
        (("fertility", 1000000, "AUD"), "AUD", "$1,999.99"),
        (("fertility", 1000000, "NZD"), "NZD", "$1,999.99"),
    ],
    ids=[
        "category-currency-is-none",
        "category-currency-is-USD",
        "category-currency-is-AUD",
        "category-currency-is-NZD",
    ],
    indirect=["single_category_wallet"],
)
def test_get_reimbursement_requests_state_reimbursement_requests_transaction_history_has_correct_benefit_amount(
    client,
    enterprise_user,
    api_helpers,
    single_category_wallet: ReimbursementWallet,
    approved_benefit_currency_reimbursement: ReimbursementRequest,
    expected_currency_code: str,
    expected_formatted_amount: str,
):
    # Given
    approved_benefit_currency_reimbursement.state = ReimbursementRequestState.REIMBURSED

    # When
    res = client.get(
        f"/api/v1/reimbursement_request/state?reimbursement_wallet_id={single_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    content = api_helpers.load_json(res)
    data = content["data"]
    reimbursement_request: dict = data["reimbursement_requests"]["transaction_history"][
        0
    ]

    # Then
    assert reimbursement_request["benefit_amount"] == {
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
        (("fertility", 1000000, None), "USD", "$1,999.99"),
        (("fertility", 1000000, "USD"), "USD", "$1,999.99"),
        (("fertility", 1000000, "AUD"), "AUD", "$1,999.99"),
        (("fertility", 1000000, "NZD"), "NZD", "$1,999.99"),
    ],
    ids=[
        "category-currency-is-none",
        "category-currency-is-USD",
        "category-currency-is-AUD",
        "category-currency-is-NZD",
    ],
    indirect=["single_category_wallet"],
)
def test_get_reimbursement_requests_state_reimbursement_requests_needs_attention_has_correct_benefit_amount(
    client,
    enterprise_user,
    api_helpers,
    single_category_wallet: ReimbursementWallet,
    unapproved_benefit_currency_reimbursement: ReimbursementRequest,
    expected_currency_code: str,
    expected_formatted_amount: str,
):
    # Given parameterized input

    # When
    res = client.get(
        f"/api/v1/reimbursement_request/state?reimbursement_wallet_id={single_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )

    content = api_helpers.load_json(res)
    data = content["data"]
    reimbursement_request: dict = data["reimbursement_requests"]["needs_attention"][0]

    # Then
    assert reimbursement_request["benefit_amount"] == {
        "currency_code": expected_currency_code,
        "amount": ANY,
        "formatted_amount": expected_formatted_amount,
        "formatted_amount_truncated": ANY,
        "raw_amount": ANY,
    }


def test_reimbursement_sources_uploads_attachment_to_alegeus(
    wallet_with_pending_requests_with_transactions_and_attachments,
    client,
    api_helpers,
    enterprise_user,
    enterprise_user_asset,
):
    mock_blob_instance = MagicMock()
    mock_blob_instance.download_as_bytes = lambda: b"testblob"

    reimbursement_request = wallet_with_pending_requests_with_transactions_and_attachments.reimbursement_requests[
        0
    ]
    # clear out all existing sources + source requests
    ReimbursementRequestSourceRequests.query.filter_by(
        reimbursement_request_id=reimbursement_request.id
    ).delete()
    assert len(reimbursement_request.sources) == 0
    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
    ) as mock_api_request, patch(
        "models.enterprise.UserAsset.blob", new_callable=PropertyMock
    ) as mock_blob, patch(
        "models.enterprise.signed_cdn_url"
    ) as mock_signed_url:
        mock_signed_url.return_value = "https://maven_test_domain/test_path"
        mock_blob.return_value = mock_blob_instance
        mock_api_request.return_value = requests.Response()
        mock_api_request.return_value.status_code = 200

        res = client.post(
            f"/api/v1/reimbursement_request/{reimbursement_request.id}/sources",
            headers=api_helpers.json_headers(enterprise_user),
            data=json.dumps({"user_asset_id": enterprise_user_asset.id}),
        )
    assert res.status_code == 201
    assert mock_api_request.call_count == 1
    assert mock_blob.call_count == 1

    # Check model relationships
    updated_reimbursement_request = ReimbursementRequest.query.get(
        reimbursement_request.id
    )
    assert len(updated_reimbursement_request.sources) == 1
    assert (
        updated_reimbursement_request.sources[0].user_asset.id
        == enterprise_user_asset.id
    )


def test_reimbursement_sources_no_claims(
    wallet_with_pending_requests_no_claims,
    client,
    api_helpers,
    enterprise_user,
    enterprise_user_asset,
):
    mock_blob_instance = MagicMock()
    mock_blob_instance.download_as_bytes = lambda: b"testblob"

    reimbursement_request = (
        wallet_with_pending_requests_no_claims.reimbursement_requests[0]
    )

    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
    ) as mock_api_request, patch(
        "models.enterprise.UserAsset.blob", new_callable=PropertyMock
    ) as mock_blob, patch(
        "models.enterprise.signed_cdn_url"
    ) as mock_signed_url, patch(
        "wallet.resources.reimbursement_request.log.info"
    ) as mock_log_info:
        mock_signed_url.return_value = "https://maven_test_domain/test_path"
        mock_blob.return_value = mock_blob_instance
        mock_api_request.return_value = requests.Response()
        mock_api_request.return_value.status_code = 200

        res_no_claims = client.post(
            f"/api/v1/reimbursement_request/{reimbursement_request.id}/sources",
            headers=api_helpers.json_headers(enterprise_user),
            data=json.dumps({"user_asset_id": enterprise_user_asset.id}),
        )
        assert res_no_claims.status_code == 201
        assert mock_api_request.call_count == 0
        assert mock_blob.call_count == 0

        mock_log_info.assert_called_once_with(
            "No claims associated with reimbursement request. Skipping claim attachments upload.",
            reimbursement_request_id=reimbursement_request.id,
        )


def test_reimbursement_sources_uploads_attachment_to_alegeus_failure(
    wallet_with_pending_requests_with_transactions_and_attachments,
    client,
    api_helpers,
    enterprise_user,
    enterprise_user_asset,
):
    mock_blob_instance = MagicMock()
    mock_blob_instance.download_as_bytes = lambda: b"testblob"

    reimbursement_request = wallet_with_pending_requests_with_transactions_and_attachments.reimbursement_requests[
        0
    ]
    # clear out all existing sources + source requests
    ReimbursementRequestSourceRequests.query.filter_by(
        reimbursement_request_id=reimbursement_request.id
    ).delete()
    assert len(reimbursement_request.sources) == 0
    with patch(
        "wallet.alegeus_api.AlegeusApi.make_api_request",
    ) as mock_api_request, patch(
        "models.enterprise.UserAsset.blob", new_callable=PropertyMock
    ) as mock_blob:
        mock_blob.return_value = mock_blob_instance
        mock_api_request.return_value = requests.Response()
        mock_api_request.return_value.status_code = 500
        mock_api_request.return_value.headers["content-type"] = "image/jpeg"

        res = client.post(
            f"/api/v1/reimbursement_request/{reimbursement_request.id}/sources",
            headers=api_helpers.json_headers(enterprise_user),
            data=json.dumps({"user_asset_id": enterprise_user_asset.id}),
        )
    assert res.status_code == 500
    assert res.json["message"] == "Error uploading attachment"
    assert mock_api_request.call_count == 1
    assert mock_blob.call_count == 1


def test_get_reimbursement_requests_with_debit_card_get_transactions__success(
    client,
    enterprise_user,
    qualified_alegeus_wallet_hra,
    api_helpers,
    wallet_debitcardinator,
    get_employee_activity_response,
):
    test_wallet = qualified_alegeus_wallet_hra
    test_wallet.reimbursement_organization_settings.debit_card_enabled = True
    wallet_debitcardinator(test_wallet, card_status=CardStatus.ACTIVE)

    mock_activity_response = requests.Response()
    mock_activity_response.status_code = 200
    mock_activity_response.json = get_employee_activity_response

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_employee_activity"
    ) as mock_activity_request:
        mock_activity_request.return_value = mock_activity_response

        res = client.get(
            f"/api/v1/reimbursement_request?reimbursement_wallet_id={test_wallet.id}",
            headers=api_helpers.json_headers(enterprise_user),
        )

        assert res.status_code == 200
        content = api_helpers.load_json(res)
        assert content["meta"]["reimbursement_wallet_id"] == str(test_wallet.id)

        reimbursement_requests = content["data"]["reimbursement_requests"]
        assert len(reimbursement_requests) == 1
        assert (
            reimbursement_requests[0]["state"]
            == ReimbursementRequestState.INELIGIBLE_EXPENSE.value
        )


def test_get_reimbursement_requests_with_debit_card_get_transactions__fails(
    client,
    enterprise_user,
    qualified_alegeus_wallet_hra,
    api_helpers,
    wallet_debitcardinator,
):
    test_wallet = qualified_alegeus_wallet_hra
    test_wallet.reimbursement_organization_settings.debit_card_enabled = True
    wallet_debitcardinator(test_wallet, card_status=CardStatus.ACTIVE)

    mock_activity_response = requests.Response()
    mock_activity_response.status_code = 500
    mock_activity_response.json = lambda: {}

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_employee_activity"
    ) as mock_activity_request:
        mock_activity_request.return_value = mock_activity_response

        res = client.get(
            f"/api/v1/reimbursement_request?reimbursement_wallet_id={test_wallet.id}",
            headers=api_helpers.json_headers(enterprise_user),
        )

        assert res.status_code == 200
        content = api_helpers.load_json(res)
        assert content["meta"]["reimbursement_wallet_id"] == str(test_wallet.id)

        reimbursement_requests = content["data"]["reimbursement_requests"]
        assert len(reimbursement_requests) == 0


def test_get_reimbursement_requests_with_debit_card_get_transactions__empty(
    client,
    enterprise_user,
    qualified_alegeus_wallet_hra,
    api_helpers,
    wallet_debitcardinator,
):
    test_wallet = qualified_alegeus_wallet_hra
    test_wallet.reimbursement_organization_settings.debit_card_enabled = True
    wallet_debitcardinator(test_wallet, card_status=CardStatus.ACTIVE)

    mock_activity_response = requests.Response()
    mock_activity_response.status_code = 200
    mock_activity_response.json = lambda: {}

    with patch(
        "wallet.utils.alegeus.debit_cards.manage.alegeus_api.AlegeusApi.get_employee_activity"
    ) as mock_activity_request:
        mock_activity_request.return_value = mock_activity_response

        res = client.get(
            f"/api/v1/reimbursement_request?reimbursement_wallet_id={test_wallet.id}",
            headers=api_helpers.json_headers(enterprise_user),
        )

        assert res.status_code == 200
        content = api_helpers.load_json(res)
        assert content["meta"]["reimbursement_wallet_id"] == str(test_wallet.id)

        reimbursement_requests = content["data"]["reimbursement_requests"]
        assert len(reimbursement_requests) == 0


def test_get_reimbursement_requests_with_expense_types(
    client, api_helpers, two_category_wallet, enterprise_user, reimbursements
):
    # Given
    allowed_categories = two_category_wallet.get_or_create_wallet_allowed_categories
    allowed_categories[0].currency_code = "USD"
    allowed_categories[1].currency_code = "AUD"
    expected_mapping = {"Fertility": "USD", "Preservation": "AUD", "Adoption": "AUD"}

    # When
    res = client.get(
        f"/api/v1/reimbursement_request?reimbursement_wallet_id={two_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )
    content = api_helpers.load_json(res)

    # Then
    for et in content["data"]["summary"]["expense_types"]:
        assert expected_mapping[et["label"]] == et["currency_code"]


def test_get_reimbursement_requests_with_expense_types_mixed_benefit_types(
    client, api_helpers, two_category_wallet, enterprise_user, reimbursements
):
    # Given
    allowed_categories = two_category_wallet.get_or_create_wallet_allowed_categories
    # 1 cycle based category
    allowed_categories[0].benefit_type = BenefitTypes.CYCLE
    allowed_categories[0].num_cycles = 10
    allowed_categories[0].currency_code = None
    # 1 currency based category
    allowed_categories[1].currency_code = "AUD"
    # Cycle based category should default to "USD"
    expected_mapping = {"Fertility": "USD", "Preservation": "AUD", "Adoption": "AUD"}

    # When
    res = client.get(
        f"/api/v1/reimbursement_request?reimbursement_wallet_id={two_category_wallet.id}",
        headers=api_helpers.json_headers(enterprise_user),
    )
    content = api_helpers.load_json(res)

    # Then
    for et in content["data"]["summary"]["expense_types"]:
        assert expected_mapping[et["label"]] == et["currency_code"]


@pytest.mark.parametrize(
    argnames="plan_year, required_plan_year_key_present, wallet_expense_type, mocked_plan_yr_fn_called",
    argvalues=[
        (None, False, ReimbursementRequestExpenseTypes.FERTILITY, True),
        ("2024", True, ReimbursementRequestExpenseTypes.FERTILITY, True),
        (None, False, ReimbursementRequestExpenseTypes.ADOPTION, False),
    ],
    ids=[
        "Survey not needed for plan year. No injection.",
        "Survey needed for plan year. Expense type on wallet needs survey. Injection.",
        "Survey not needed for plan year. Wallet expense type does not need survey. No injection.",
    ],
)
def test_post_reimbursement_request_success(
    client,
    api_helpers,
    enterprise_user,
    qualified_alegeus_wallet_hdhp_family: ReimbursementWallet,
    reimbursement_request_data,
    plan_year,
    required_plan_year_key_present,
    wallet_expense_type,
    mocked_plan_yr_fn_called,
):
    with patch(
        "wallet.services.reimbursement_request.add_reimbursement_request_comment"
    ), patch(
        "wallet.resources.reimbursement_request.get_plan_year_if_survey_needed_for_target_date",
        return_value=plan_year,
    ) as mocked_get_plan_year, patch(
        "wallet.tasks.document_mapping.map_reimbursement_request_documents.delay"
    ) as mock_document_mapper, patch(
        "wallet.resources.reimbursement_request.receipt_validation_ops_view_enabled",
        return_value=True,
    ):
        qualified_alegeus_wallet_hdhp_family.primary_expense_type = wallet_expense_type
        res = client.post(
            "/api/v1/reimbursement_request",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(reimbursement_request_data),
        )

    assert res.status_code == 200
    assert res.json.get("amount") == reimbursement_request_data["amount"]
    assert res.json.get("benefit_amount") == {
        "formatted_amount": ANY,
        "formatted_amount_truncated": ANY,
        "currency_code": reimbursement_request_data["currency_code"],
        "raw_amount": ANY,
        "amount": reimbursement_request_data["amount"],
    }
    assert (
        res.json.get("service_provider")
        == reimbursement_request_data["service_provider"]
    )
    assert (
        res.json.get("person_receiving_service")
        == reimbursement_request_data["person_receiving_service_name"]
    )
    assert len(res.json.get("sources")) == 2
    assert mocked_get_plan_year.called == mocked_plan_yr_fn_called
    assert ("required_plan_year" in res.json) is required_plan_year_key_present
    assert res.json.get("required_plan_year") == plan_year
    reimbursement_request_source = ReimbursementRequestSource.query.filter_by(
        user_asset_id=res.json.get("sources")[0]["source_id"]
    ).one_or_none()
    assert (
        reimbursement_request_source.upload_source
        == ReimbursementRequestSourceUploadSource.INITIAL_SUBMISSION
    )
    assert mock_document_mapper.call_count == 1


@pytest.mark.parametrize(argnames="currency_code", argvalues=["", "    ", None])
def test_post_reimbursement_request_failure_invalid_currency_code(
    client,
    api_helpers,
    enterprise_user,
    qualified_alegeus_wallet_hdhp_family,
    reimbursement_request_data,
    currency_code,
):
    # Given
    reimbursement_request_data["currency_code"] = currency_code
    # When
    with patch(
        "wallet.services.reimbursement_request.add_reimbursement_request_comment"
    ):
        res = client.post(
            "/api/v1/reimbursement_request",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(reimbursement_request_data),
        )

    assert res.status_code == 400


def test_post_reimbursement_request_failure_missing_wallet(
    client,
    api_helpers,
    enterprise_user,
    reimbursement_request_data,
    qualified_alegeus_wallet_hdhp_family,
):
    # Given
    reimbursement_request_data["wallet_id"] = (
        qualified_alegeus_wallet_hdhp_family.id + 1
    )

    # When
    with patch(
        "wallet.services.reimbursement_request.add_reimbursement_request_comment"
    ):
        res = client.post(
            "/api/v1/reimbursement_request",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(reimbursement_request_data),
        )

    # Then
    assert res.status_code == 500


def test_post_reimbursement_request_with_expense_types_success(
    client,
    api_helpers,
    reimbursement_request_data_generator,
    two_category_wallet,
    enterprise_user,
    eligibility_factories,
):
    reimbursement_request_data = reimbursement_request_data_generator(
        two_category_wallet, enterprise_user
    )
    del reimbursement_request_data["category_id"]
    reimbursement_request_data["expense_type"] = "Preservation"
    reimbursement_request_data["expense_subtype_id"] = None

    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=two_category_wallet.employee_member.id,
        organization_id=two_category_wallet.reimbursement_organization_settings.organization_id,
        record={"work_country": "USA"},
    )
    with patch(
        "wallet.services.reimbursement_request.add_reimbursement_request_comment"
    ), patch("wallet.tasks.document_mapping.map_reimbursement_request_documents.delay"):
        with patch(
            "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
        ) as member_id_search_mock:
            member_id_search_mock.return_value = e9y_member_verification

            res = client.post(
                "/api/v1/reimbursement_request",
                headers=api_helpers.json_headers(two_category_wallet.employee_member),
                data=api_helpers.json_data(reimbursement_request_data),
            )

    assert res.status_code == 200
    rr = ReimbursementRequest.query.filter_by(
        expense_type=ReimbursementRequestExpenseTypes.PRESERVATION
    ).first()
    assert rr.category.label == "other"
    assert rr.taxation_status == TaxationState.NON_TAXABLE


def test_post_reimbursement_request_with_expense_types_success_category_activation(
    client,
    api_helpers,
    reimbursement_request_data_generator,
    two_category_wallet,
    enterprise_user,
    eligibility_factories,
):
    reimbursement_request_data = reimbursement_request_data_generator(
        two_category_wallet, enterprise_user
    )

    del reimbursement_request_data["category_id"]
    reimbursement_request_data["expense_type"] = "Preservation"
    reimbursement_request_data["expense_subtype_id"] = None

    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=two_category_wallet.employee_member.id,
        organization_id=two_category_wallet.reimbursement_organization_settings.organization_id,
        record={"work_country": "USA"},
    )
    with patch(
        "wallet.services.reimbursement_request.add_reimbursement_request_comment"
    ), patch("wallet.tasks.document_mapping.map_reimbursement_request_documents.delay"):
        with patch(
            "eligibility.service.EnterpriseVerificationService.get_verification_for_user"
        ) as member_id_search_mock:
            member_id_search_mock.return_value = e9y_member_verification

            res = client.post(
                "/api/v1/reimbursement_request",
                headers=api_helpers.json_headers(two_category_wallet.employee_member),
                data=api_helpers.json_data(reimbursement_request_data),
            )
    assert res.status_code == 200
    rr = ReimbursementRequest.query.filter_by(
        expense_type=ReimbursementRequestExpenseTypes.PRESERVATION
    ).first()
    assert rr.category.label == "other"
    assert rr.taxation_status == TaxationState.NON_TAXABLE


def test_post_reimbursement_request_with_intl_user_expense_types_success(
    client,
    api_helpers,
    reimbursement_request_data_generator,
    two_category_wallet,
    enterprise_user,
    eligibility_factories,
):
    reimbursement_request_data = reimbursement_request_data_generator(
        two_category_wallet, enterprise_user
    )

    del reimbursement_request_data["category_id"]
    reimbursement_request_data["expense_type"] = "Preservation"
    reimbursement_request_data["expense_subtype_id"] = None

    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=two_category_wallet.employee_member.id,
        organization_id=two_category_wallet.reimbursement_organization_settings.organization_id,
        record={"work_country": "UK"},
    )
    with patch(
        "wallet.services.reimbursement_request.add_reimbursement_request_comment"
    ), patch("wallet.tasks.document_mapping.map_reimbursement_request_documents.delay"):
        with patch(
            "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
        ) as member_id_search_mock:
            member_id_search_mock.return_value = e9y_member_verification
            res = client.post(
                "/api/v1/reimbursement_request",
                headers=api_helpers.json_headers(two_category_wallet.employee_member),
                data=api_helpers.json_data(reimbursement_request_data),
            )

    assert res.status_code == 200
    rr = ReimbursementRequest.query.filter_by(
        expense_type=ReimbursementRequestExpenseTypes.PRESERVATION
    ).first()
    assert rr.category.label == "other"
    assert rr.taxation_status == TaxationState.TAXABLE


def test_post_reimbursement_request_with_expense_types_infertility_success(
    client,
    api_helpers,
    reimbursement_request_data_generator,
    enterprise_user,
    two_category_wallet,
):
    reimbursement_request_data = reimbursement_request_data_generator(
        two_category_wallet, enterprise_user
    )

    del reimbursement_request_data["category_id"]
    reimbursement_request_data["expense_type"] = "Fertility"
    reimbursement_request_data["expense_subtype_id"] = None
    reimbursement_request_data["infertility_dx"] = True
    with patch(
        "wallet.services.reimbursement_request.add_reimbursement_request_comment"
    ), patch("wallet.tasks.document_mapping.map_reimbursement_request_documents.delay"):
        res = client.post(
            "/api/v1/reimbursement_request",
            headers=api_helpers.json_headers(two_category_wallet.employee_member),
            data=api_helpers.json_data(reimbursement_request_data),
        )

    assert res.status_code == 200
    rr = ReimbursementRequest.query.filter_by(
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY
    ).first()
    assert rr.category.label == "fertility"
    assert rr.taxation_status == TaxationState.NON_TAXABLE


@freezegun.freeze_time("2024-06-01T00:00:00")
def test_post_reimbursement_request_with_expense_types_old_categories_success(
    client,
    api_helpers,
    reimbursement_request_data_generator,
    two_category_wallet,
    enterprise_user,
):
    ros_id = two_category_wallet.reimbursement_organization_settings_id
    # Set up plan with current categories
    plan = ReimbursementPlanFactory.create(
        plan_type="ANNUAL",
        start_date=datetime.date(2024, 1, 1),
        end_date=datetime.date(2024, 12, 31),
    )
    allowed_categories = (
        two_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
    )
    allowed_categories[0].reimbursement_request_category.reimbursement_plan_id = plan.id
    allowed_categories[1].reimbursement_request_category.reimbursement_plan_id = plan.id

    # Set up extra category with older plan
    old_plan = ReimbursementPlanFactory.create(
        plan_type="ANNUAL",
        start_date=datetime.date(2023, 1, 1),
        end_date=datetime.date(2023, 12, 31),
    )
    old_category = ReimbursementRequestCategoryFactory.create(
        label="old category",
        reimbursement_plan_id=old_plan.id,
    )
    ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_request_category_id=old_category.id,
        reimbursement_organization_settings_id=ros_id,
        benefit_type="CURRENCY",
    )
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category_id=old_category.id,
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
    )

    # Set up request
    reimbursement_request_data = reimbursement_request_data_generator(
        two_category_wallet, enterprise_user
    )

    del reimbursement_request_data["category_id"]
    reimbursement_request_data["expense_type"] = "Fertility"
    reimbursement_request_data["expense_subtype_id"] = None

    with patch(
        "wallet.services.reimbursement_request.add_reimbursement_request_comment"
    ), patch("wallet.tasks.document_mapping.map_reimbursement_request_documents.delay"):
        res = client.post(
            "/api/v1/reimbursement_request",
            headers=api_helpers.json_headers(two_category_wallet.employee_member),
            data=api_helpers.json_data(reimbursement_request_data),
        )

    assert res.status_code == 200
    rr = ReimbursementRequest.query.filter_by(
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY
    ).first()
    assert rr.category.label == "fertility"
    assert rr.taxation_status == TaxationState.TAXABLE


@freezegun.freeze_time("2024-06-01T00:00:00")
def test_post_reimbursement_request_with_expense_types_no_plan_categories_success(
    client,
    api_helpers,
    reimbursement_request_data_generator,
    two_category_wallet,
    enterprise_user,
):
    ros_id = two_category_wallet.reimbursement_organization_settings_id

    # Set up extra category without a plan
    category = ReimbursementRequestCategoryFactory.create(
        label="old category",
    )
    ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_request_category_id=category.id,
        reimbursement_organization_settings_id=ros_id,
        benefit_type="CURRENCY",
    )
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category_id=category.id,
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
    )

    # Set up request
    reimbursement_request_data = reimbursement_request_data_generator(
        two_category_wallet, enterprise_user
    )

    del reimbursement_request_data["category_id"]
    reimbursement_request_data["expense_type"] = "Fertility"
    reimbursement_request_data["expense_subtype_id"] = None

    with patch(
        "wallet.services.reimbursement_request.add_reimbursement_request_comment"
    ), patch("wallet.tasks.document_mapping.map_reimbursement_request_documents.delay"):
        res = client.post(
            "/api/v1/reimbursement_request",
            headers=api_helpers.json_headers(two_category_wallet.employee_member),
            data=api_helpers.json_data(reimbursement_request_data),
        )

    assert res.status_code == 200
    rr = ReimbursementRequest.query.filter_by(
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY
    ).first()
    assert rr.category.label == "fertility"
    assert rr.taxation_status == TaxationState.TAXABLE


@freezegun.freeze_time("2024-06-01T00:00:00")
def test_post_reimbursement_request_with_expense_types_multiple_active_categories_success(
    client,
    api_helpers,
    reimbursement_request_data_generator,
    two_category_wallet,
    enterprise_user,
):
    ros_id = two_category_wallet.reimbursement_organization_settings_id
    # Set up plan with current categories
    plan = ReimbursementPlanFactory.create(
        plan_type="ANNUAL",
        start_date=datetime.date(2024, 1, 1),
        end_date=datetime.date(2024, 12, 31),
    )
    allowed_categories = (
        two_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
    )
    allowed_categories[0].reimbursement_request_category.reimbursement_plan_id = plan.id
    allowed_categories[1].reimbursement_request_category.reimbursement_plan_id = plan.id

    # Set up extra category with older plan
    active_plan = ReimbursementPlanFactory.create(
        plan_type="ANNUAL",
        start_date=datetime.date(2024, 1, 1),
        end_date=datetime.date(2024, 12, 31),
    )
    active_category = ReimbursementRequestCategoryFactory.create(
        label="old category",
        reimbursement_plan_id=active_plan.id,
    )
    ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_request_category_id=active_category.id,
        reimbursement_organization_settings_id=ros_id,
        benefit_type="CURRENCY",
    )
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category_id=active_category.id,
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
    )

    # Set up request
    reimbursement_request_data = reimbursement_request_data_generator(
        two_category_wallet, enterprise_user
    )

    del reimbursement_request_data["category_id"]
    reimbursement_request_data["expense_type"] = "Fertility"
    reimbursement_request_data["expense_subtype_id"] = None

    with patch(
        "wallet.services.reimbursement_request.add_reimbursement_request_comment"
    ), patch("wallet.tasks.document_mapping.map_reimbursement_request_documents.delay"):
        res = client.post(
            "/api/v1/reimbursement_request",
            headers=api_helpers.json_headers(two_category_wallet.employee_member),
            data=api_helpers.json_data(reimbursement_request_data),
        )

    assert res.status_code == 200
    rr = ReimbursementRequest.query.filter_by(
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY
    ).first()
    assert rr.category.label == "fertility"
    assert rr.taxation_status == TaxationState.TAXABLE


def test_post_reimbursement_request_expense_type_subtype_mismatch(
    client, api_helpers, enterprise_user, reimbursement_request_data, expense_subtypes
):
    # remove field to create a bad request
    del reimbursement_request_data["category_id"]
    reimbursement_request_data["expense_type"] = "Fertility"
    reimbursement_request_data["expense_subtype_id"] = str(expense_subtypes["ALF"].id)

    res = client.post(
        "/api/v1/reimbursement_request",
        headers=api_helpers.json_headers(enterprise_user),
        data=api_helpers.json_data(reimbursement_request_data),
    )

    assert res.status_code == 400
    assert (
        res.json.get("message")
        == "Validation failed, due to: Expense Subtype is not valid for this Expense Type"
    )


@pytest.mark.parametrize(
    "missing_field",
    [
        "service_provider",
        "service_start_date",
        "person_receiving_service_id",
        "person_receiving_service_name",
        "amount",
        "wallet_id",
        "sources",
    ],
)
def test_post_reimbursement_request_missing_required_fields(
    client, api_helpers, enterprise_user, missing_field, reimbursement_request_data
):
    # remove field to create a bad request
    del reimbursement_request_data[missing_field]

    res = client.post(
        "/api/v1/reimbursement_request",
        headers=api_helpers.json_headers(enterprise_user),
        data=api_helpers.json_data(reimbursement_request_data),
    )

    assert res.status_code == 400
    assert res.json.get("message") == f"Missing required field: [{missing_field}]"


def test_post_reimbursement_request_missing_expense_type_or_category(
    client, api_helpers, enterprise_user, reimbursement_request_data
):
    # remove field to create a bad request
    del reimbursement_request_data["category_id"]
    del reimbursement_request_data["expense_type"]
    del reimbursement_request_data["expense_subtype_id"]

    res = client.post(
        "/api/v1/reimbursement_request",
        headers=api_helpers.json_headers(enterprise_user),
        data=api_helpers.json_data(reimbursement_request_data),
    )

    assert res.status_code == 400
    assert (
        res.json.get("message")
        == "Validation failed, due to: Expense Type or Category is required."
    )


def test_post_reimbursement_request_invalid_expense_type(
    client, api_helpers, enterprise_user, reimbursement_request_data
):
    # remove field to create a bad request
    del reimbursement_request_data["category_id"]
    reimbursement_request_data["expense_type"] = "something made up"

    res = client.post(
        "/api/v1/reimbursement_request",
        headers=api_helpers.json_headers(enterprise_user),
        data=api_helpers.json_data(reimbursement_request_data),
    )

    assert res.status_code == 400
    assert (
        res.json.get("message")
        == "Validation failed, due to: Missing category for expense type and organization."
    )


def test_post_reimbursement_request_expense_type_has_no_category(
    client,
    api_helpers,
    two_category_wallet,
    enterprise_user,
    reimbursement_request_data_generator,
):
    reimbursement_request_data = reimbursement_request_data_generator(
        two_category_wallet, enterprise_user
    )

    del reimbursement_request_data["category_id"]
    reimbursement_request_data["expense_type"] = "Childcare"
    reimbursement_request_data["expense_subtype_id"] = None

    with patch(
        "wallet.services.reimbursement_request.add_reimbursement_request_comment"
    ):
        res = client.post(
            "/api/v1/reimbursement_request",
            headers=api_helpers.json_headers(two_category_wallet.employee_member),
            data=api_helpers.json_data(reimbursement_request_data),
        )

    assert res.status_code == 400
    assert (
        res.json.get("message")
        == "Validation failed, due to: Missing category for expense type and organization."
    )


def test_post_reimbursement_request_with_expense_subtype_success(
    client,
    api_helpers,
    reimbursement_request_data_generator,
    two_category_wallet,
    enterprise_user,
    eligibility_factories,
):
    reimbursement_request_data = reimbursement_request_data_generator(
        two_category_wallet, enterprise_user
    )

    e9y_member_verification = eligibility_factories.VerificationFactory.create(
        user_id=two_category_wallet.employee_member.id,
        organization_id=two_category_wallet.reimbursement_organization_settings.organization_id,
        record={"work_country": "USA"},
    )
    with patch(
        "wallet.services.reimbursement_request.add_reimbursement_request_comment"
    ), patch("wallet.tasks.document_mapping.map_reimbursement_request_documents.delay"):
        with patch(
            "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org"
        ) as member_id_search_mock:
            member_id_search_mock.return_value = e9y_member_verification

            res = client.post(
                "/api/v1/reimbursement_request",
                headers=api_helpers.json_headers(two_category_wallet.employee_member),
                data=api_helpers.json_data(reimbursement_request_data),
            )

    assert res.status_code == 200
    rr = ReimbursementRequest.query.filter_by(
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY
    ).first()
    # reimbursement_request_data includes description, expense type, and expense subtype
    # description should not be saved, returned label should be type + subtype
    assert rr.description == ""
    assert res.json.get("label") == "Fertility - IVF (with fresh transfer)"


def test_post_reimbursement_request_service_returning_validation_error(
    client, api_helpers, enterprise_user, reimbursement_request_data
):
    with patch.object(
        ReimbursementRequestService,
        "create_reimbursement_request",
        side_effect=ValueError("bad data"),
    ):
        res = client.post(
            "/api/v1/reimbursement_request",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(reimbursement_request_data),
        )

        assert res.status_code == 400
        assert res.json.get("message") == "Validation failed, due to: bad data"


def test_post_reimbursement_request_service_returning_500_error(
    client, api_helpers, enterprise_user, reimbursement_request_data
):
    with patch.object(
        ReimbursementRequestService,
        "create_reimbursement_request",
        side_effect=Exception("something failed"),
    ):
        res = client.post(
            "/api/v1/reimbursement_request",
            headers=api_helpers.json_headers(enterprise_user),
            data=api_helpers.json_data(reimbursement_request_data),
        )

        assert res.status_code == 500
        assert (
            res.json.get("message")
            == "Could not complete request, due to: something failed"
        )


def test_marshmallow_deserializes_null_data():
    # ReimbursementRequestDataSchema is the envelope schema
    schema = ReimbursementRequestDataSchema()
    data = {
        "summary": {
            "reimbursement_request_maximum": None,
            "reimbursement_spent": None,
            "currency_code": None,
            "wallet_shareable": None,
            "category_breakdown": [
                {
                    "category": {
                        "id": None,
                        "label": None,
                        "is_unlimited": None,
                        "reimbursement_request_category_maximum": None,
                        "reimbursement_request_category_maximum_amount": {
                            "currency_code": None,
                            "amount": None,
                            "formatted_amount_truncated": None,
                            "truncated_amount": None,
                            "raw_amount": None,
                        },
                        "title": None,
                        "subtitle": None,
                    },
                    "plan_type": None,
                    "plan_start": None,
                    "plan_end": None,
                    "spent": None,
                    "spent_amount": {
                        "currency_code": None,
                        "amount": None,
                        "formatted_amount_truncated": None,
                        "truncated_amount": None,
                        "raw_amount": None,
                    },
                    "remaining_amount": {
                        "currency_code": None,
                        "amount": None,
                        "formatted_amount_truncated": None,
                        "truncated_amount": None,
                        "raw_amount": None,
                    },
                },
            ],
            "expense_types": [
                {
                    "label": None,
                    "currency_code": None,
                    "form_options": [],
                    "is_fertility_expense": None,
                    "subtypes": [],
                }
            ],
        },
        "reimbursement_requests": [
            {
                "id": None,
                "label": None,
                "service_provider": None,
                "person_receiving_service": None,
                "employee_name": None,
                "description": None,
                "amount": None,
                "benefit_amount": {
                    "currency_code": None,
                    "amount": None,
                    "formatted_amount_truncated": None,
                    "truncated_amount": None,
                    "raw_amount": None,
                },
                "state": None,
                "state_description": None,
                "category": {
                    "id": None,
                    "label": None,
                    "reimbursement_request_category_maximum": None,
                    "title": None,
                    "subtitle": None,
                },
                "source": [
                    {
                        "type": None,
                        "source_id": None,
                        "source_url": None,
                        "inline_url": None,
                        "content_type": None,
                        "created_at": None,
                        "file_name": None,
                    }
                ],
                "sources": [
                    {
                        "type": None,
                        "source_id": None,
                        "source_url": None,
                        "inline_url": None,
                        "content_type": None,
                        "created_at": None,
                        "file_name": None,
                    }
                ],
                "service_start_date": None,
                "service_end_date": None,
                "created_at": None,
                "taxation_status": None,
                "reimbursement_type": None,
                "cost_share_details": None,
                "wallet_expense_subtype": None,
            }
        ],
    }

    expected_result = {
        "reimbursement_requests": [
            {
                "amount": 0,
                "benefit_amount": {
                    "currency_code": "",
                    "amount": 0,
                    "formatted_amount": "",
                    "formatted_amount_truncated": "",
                    "raw_amount": "",
                },
                "service_end_date": None,
                "source": {
                    "source_url": None,
                    "type": "",
                    "created_at": None,
                    "file_name": None,
                    "source_id": "",
                    "inline_url": None,
                    "content_type": None,
                },
                "taxation_status": "",
                "reimbursement_type": None,
                "service_provider": "",
                "sources": [
                    {
                        "type": "",
                        "source_url": None,
                        "created_at": None,
                        "file_name": None,
                        "source_id": "",
                        "content_type": None,
                        "inline_url": None,
                    }
                ],
                "service_start_date": None,
                "label": "",
                "id": "",
                "category": {
                    "subtitle": "",
                    "title": "",
                    "label": "",
                    "id": "",
                    "benefit_type": None,
                },
                "created_at": None,
                "person_receiving_service": "",
                "employee_name": "",
                "state": None,
                "description": "",
                "state_description": "",
                "cost_share_details": None,
            },
        ],
        "summary": {
            "currency_code": "",
            "reimbursement_spent": 0,
            "wallet_shareable": False,
            "category_breakdown": [
                {
                    "plan_start": None,
                    "spent": 0,
                    "spent_amount": {
                        "currency_code": "",
                        "amount": 0,
                        "formatted_amount": "",
                        "formatted_amount_truncated": "",
                        "raw_amount": "",
                    },
                    "remaining_amount": {
                        "currency_code": "",
                        "amount": 0,
                        "formatted_amount": "",
                        "formatted_amount_truncated": "",
                        "raw_amount": "",
                    },
                    "category": {
                        "subtitle": "",
                        "title": "",
                        "label": "",
                        "id": "",
                        "is_unlimited": False,
                        "reimbursement_request_category_maximum": 0,
                        "reimbursement_request_category_maximum_amount": {
                            "currency_code": "",
                            "amount": 0,
                            "formatted_amount": "",
                            "formatted_amount_truncated": "",
                            "raw_amount": "",
                        },
                        "benefit_type": None,
                        "credits_remaining": 0,
                        "is_fertility_category": False,
                        "direct_payment_eligible": False,
                        "credit_maximum": 0,
                    },
                    "plan_end": None,
                    "plan_type": "",
                }
            ],
            "expense_types": [
                {
                    "label": "",
                    "currency_code": None,
                    "is_fertility_expense": False,
                    "form_options": [],
                    "subtypes": [],
                }
            ],
            "reimbursement_request_maximum": 0,
        },
    }
    actual_result = schema.dump(data).data
    assert actual_result == expected_result


@pytest.mark.parametrize(
    argnames=(
        "single_category_wallet",
        "expected_currency_code",
    ),
    argvalues=[
        (("fertility", 1000000, None), "USD"),
        (("fertility", 1000000, "USD"), "USD"),
        (("fertility", 1000000, "AUD"), "AUD"),
        (("fertility", 1000000, "NZD"), "NZD"),
    ],
    ids=[
        "category-currency-is-none",
        "category-currency-is-USD",
        "category-currency-is-AUD",
        "category-currency-is-NZD",
    ],
    indirect=["single_category_wallet"],
)
def test_get_summary_currency_code_single_category(
    single_category_wallet: ReimbursementWallet,
    ff_test_data,
    expected_currency_code: str,
):
    # Given
    category_associations: List[
        ReimbursementOrgSettingCategoryAssociation
    ] = (
        single_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
    )

    # When
    currency_code = get_summary_currency_code(
        category_associations=category_associations
    )

    # Then
    assert currency_code == expected_currency_code


@pytest.mark.parametrize(
    argnames=(
        "multi_category_wallet",
        "expected_currency_code",
    ),
    argvalues=[
        ([], "USD"),
        (
            [
                ("fertility", 1000000, None),
                ("wellness", 1000000, "USD"),
                ("family", 1000000, "USD"),
            ],
            "USD",
        ),
        ([("fertility", 1000000, "USD"), ("wellness", 1000000, "USD")], "USD"),
        ([("fertility", 1000000, "AUD"), ("wellness", 1000000, "AUD")], "AUD"),
        ([("fertility", 1000000, "AUD"), ("wellness", 1000000, "USD")], None),
        (
            [
                ("fertility", 1000000, None),
                ("wellness", 1000000, "USD"),
                ("family", 1000000, "AUD"),
            ],
            None,
        ),
    ],
    ids=[
        "no-categories-configured",
        "all-categories-are-USD-or-none",
        "all-categories-are-USD",
        "all-categories-are-AUD",
        "categories-have-different-currency",
        "three-categories-have-different-currency",
    ],
    indirect=["multi_category_wallet"],
)
def test_get_summary_currency_code_multiple_category_multiple_currencies(
    ff_test_data,
    multi_category_wallet: ReimbursementWallet,
    expected_currency_code: str,
):
    # Given
    category_associations: List[
        ReimbursementOrgSettingCategoryAssociation
    ] = (
        multi_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
    )

    # When
    currency_code = get_summary_currency_code(
        category_associations=category_associations
    )

    # Then
    assert currency_code == expected_currency_code


def test_get_expense_types_for_wallet(two_category_wallet, expense_subtypes):
    expected = {
        ReimbursementRequestExpenseTypes.FERTILITY.value: {
            "label": "Fertility",
            "subtypes_labels": [
                "Fertility medication",
                "Fertility testing",
                "IVF (with fresh transfer)",
                "Other",
            ],
        },
        ReimbursementRequestExpenseTypes.PRESERVATION.value: {
            "label": "Preservation",
            "subtypes_labels": [
                "Egg Freezing-IVF-IUI",
                "Fertility and preservation medication",
                "Other",
            ],
        },
        ReimbursementRequestExpenseTypes.ADOPTION.value: {
            "label": "Adoption",
            "subtypes_labels": ["Agency fees", "Legal fees", "Other"],
        },
    }

    allowed_categories = two_category_wallet.get_or_create_wallet_allowed_categories
    expense_types = get_expense_types_for_wallet(
        wallet=two_category_wallet, allowed_categories=allowed_categories
    )
    assert len(expense_types) == 3

    for expense_type in expense_types:
        assert expense_type["label"] == expected[expense_type["type"]]["label"]
        assert [st["label"] for st in expense_type["subtypes"]] == expected[
            expense_type["type"]
        ]["subtypes_labels"]


def test_get_expense_types_for_wallet_no_visibility_category(two_category_wallet):
    all_ros_categories = (
        two_category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories
    )
    missing_label = set(
        all_ros_categories[0].reimbursement_request_category.expense_types
    )
    ReimbursementWalletAllowedCategorySettings.query.filter(
        ReimbursementWalletAllowedCategorySettings.reimbursement_organization_settings_allowed_category_id
        == all_ros_categories[0].id,
        ReimbursementWalletAllowedCategorySettings.reimbursement_wallet_id
        == two_category_wallet.id,
    ).delete()

    ReimbursementWalletAllowedCategorySettingsFactory.create(
        reimbursement_organization_settings_allowed_category_id=all_ros_categories[
            0
        ].id,
        reimbursement_wallet_id=two_category_wallet.id,
        access_level=CategoryRuleAccessLevel.NO_ACCESS,
        access_level_source=CategoryRuleAccessSource.RULES,
    )
    all_ros_labels = {
        expense_type
        for cat in all_ros_categories
        for expense_type in cat.reimbursement_request_category.expense_types
    }
    expected_label_list = list(all_ros_labels - missing_label)
    allowed_categories = two_category_wallet.get_or_create_wallet_allowed_categories
    expense_types = get_expense_types_for_wallet(
        wallet=two_category_wallet, allowed_categories=allowed_categories
    )
    assert len(expense_types) == len(expected_label_list)


def test_get_expense_types_for_wallet_currency_code(two_category_wallet):
    # Given
    allowed_categories = two_category_wallet.get_or_create_wallet_allowed_categories

    # When
    expense_types = get_expense_types_for_wallet(
        wallet=two_category_wallet, allowed_categories=allowed_categories
    )

    # Then
    assert all(expense_type["currency_code"] == "USD" for expense_type in expense_types)


def test_get_expense_types_for_wallet_multi_currencies(two_category_wallet):
    # Given
    allowed_categories = two_category_wallet.get_or_create_wallet_allowed_categories
    allowed_categories[0].currency_code = "USD"
    allowed_categories[1].currency_code = "GBP"
    expected_mapping = {"Fertility": "USD", "Preservation": "GBP", "Adoption": "GBP"}

    # When
    expense_types = get_expense_types_for_wallet(
        wallet=two_category_wallet, allowed_categories=allowed_categories
    )

    # Then
    assert all(
        et["currency_code"] == expected_mapping[et["label"]] for et in expense_types
    )


def test_get_expense_types_for_wallet_is_fertility_expense_check(two_category_wallet):
    # Given
    allowed_categories = two_category_wallet.get_or_create_wallet_allowed_categories
    expected_mapping = {"Fertility": True, "Preservation": True, "Adoption": False}

    # When
    expense_types = get_expense_types_for_wallet(
        wallet=two_category_wallet, allowed_categories=allowed_categories
    )

    # Then
    assert all(
        et["is_fertility_expense"] == expected_mapping[et["label"]]
        for et in expense_types
    )
