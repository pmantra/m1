import datetime

import pytest

from wallet.models.constants import (
    ReimbursementRequestAutoProcessing,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    ReimbursementRequestType,
    WalletState,
)
from wallet.models.reimbursement import (
    ReimbursementRequest,
    ReimbursementRequestCategory,
    ReimbursementWallet,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.pytests.factories import (
    ReimbursementOrgSettingCategoryAssociationFactory,
    ReimbursementRequestCategoryExpenseTypesFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestFactory,
)


def create_unsaved_manual_reimbursement_request(wallet):
    return _create_unsaved_reimbursement_request(
        wallet, ReimbursementRequestType.MANUAL
    )


def create_unsaved_direct_payment_reimbursement_request(wallet):
    return _create_unsaved_reimbursement_request(
        wallet, ReimbursementRequestType.DIRECT_BILLING
    )


def _create_unsaved_reimbursement_request(wallet, reimbursement_type):
    category = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category
    )

    reimbursement_request = ReimbursementRequestFactory.build(
        wallet=wallet,
        category=category,
        service_start_date=datetime.datetime.utcnow(),
        amount=100_000,
        state=ReimbursementRequestState.NEW,
        reimbursement_type=reimbursement_type,
    )

    return reimbursement_request


def test_set_erisa_workflow__not_direct_payment_enabled__is_false(
    db, qualified_alegeus_wallet_hra
):
    reimbursement_request = create_unsaved_manual_reimbursement_request(
        qualified_alegeus_wallet_hra
    )

    assert reimbursement_request.erisa_workflow is None
    db.session.add(reimbursement_request)
    db.session.commit()

    assert reimbursement_request.erisa_workflow is False


def test_set_erisa_workflow__direct_payment__is_true(
    db, qualified_direct_payment_enabled_wallet
):
    reimbursement_request = create_unsaved_direct_payment_reimbursement_request(
        qualified_direct_payment_enabled_wallet
    )

    assert reimbursement_request.erisa_workflow is None
    db.session.add(reimbursement_request)
    db.session.commit()

    assert reimbursement_request.erisa_workflow is True


# this is a subset of the inputs used to test reimbursement_category.direct_payment_eligible
@pytest.mark.parametrize(
    argnames="country_code,primary_expense_type,category_expense_types,expected",
    argvalues=[
        # true if country is US and category expense type is within eligible fertility type
        ("US", None, ["FERTILITY"], True),
        # false if country is not US
        ("CA", None, ["FERTILITY"], False),
        # true with non-fertility primary and only eligible fertility expense types
        ("US", None, ["FERTILITY", "PRESERVATION"], True),
        ("US", "ADOPTION", ["FERTILITY", "PRESERVATION"], True),
        # false if no expense types are mapped to the category
        ("US", "FERTILITY", [], False),
        # false if expense type is not one of the defined fertility types
        ("US", "FERTILITY", ["ADOPTION"], False),
        # true with fertility primary and any expense type is within eligible types
        ("US", "FERTILITY", ["FERTILITY", "SURROGACY", "ADOPTION"], True),
    ],
)
def test_set_erisa_workflow__direct_payment_eligible(
    db,
    qualified_direct_payment_enabled_wallet,
    country_code,
    primary_expense_type,
    category_expense_types,
    expected,
):
    reimbursement_wallet = qualified_direct_payment_enabled_wallet

    if primary_expense_type:
        reimbursement_wallet.primary_expense_type = ReimbursementRequestExpenseTypes[
            primary_expense_type
        ]
    reimbursement_wallet.member.member_profile.country_code = country_code

    category = reimbursement_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ].reimbursement_request_category
    if len(category_expense_types) > 0:
        for type in category_expense_types:
            ReimbursementRequestCategoryExpenseTypesFactory.create(
                reimbursement_request_category_id=category.id,
                reimbursement_request_category=category,
                expense_type=ReimbursementRequestExpenseTypes[type],
            )

    reimbursement_request = create_unsaved_manual_reimbursement_request(
        reimbursement_wallet
    )

    assert reimbursement_request.erisa_workflow is None
    db.session.add(reimbursement_request)
    db.session.commit()

    assert reimbursement_request.erisa_workflow == expected


def test_set_erisa_workflow__does_not_change(
    db, qualified_direct_payment_enabled_wallet
):
    reimbursement_wallet = qualified_direct_payment_enabled_wallet

    reimbursement_request = create_unsaved_direct_payment_reimbursement_request(
        reimbursement_wallet
    )

    assert reimbursement_request.erisa_workflow is None
    db.session.add(reimbursement_request)
    db.session.commit()

    assert reimbursement_request.erisa_workflow is True

    # What if the org stops Direct Payment?
    reimbursement_wallet.reimbursement_organization_settings.direct_payment_enabled = (
        False
    )

    # Changes should not update existing workflow value.

    reimbursement_request.state = ReimbursementRequestState.PENDING
    db.session.add(reimbursement_request)
    db.session.commit()

    assert reimbursement_request.erisa_workflow is True

    # New request should get new workflow value.

    reimbursement_request2 = create_unsaved_direct_payment_reimbursement_request(
        reimbursement_wallet
    )

    assert reimbursement_request2.erisa_workflow is None
    db.session.add(reimbursement_request2)
    db.session.commit()

    assert reimbursement_request2.erisa_workflow is False


@pytest.mark.parametrize(
    argnames=("category_currency_code", "amount", "usd_amount", "expected_amount"),
    argvalues=[
        (
            "USD",
            100,
            200,
            100,
        ),  # `amount` and `usd_amount` differ for the sake of testing
        (
            None,
            100,
            200,
            100,
        ),  # `amount` and `usd_amount` differ for the sake of testing
        ("AUD", 200, 100, 100),
        ("NZD", 123, 456, 456),
    ],
    ids=[
        "usd-category-returns-amount",
        "none-category-returns-amount",
        "aud-category-returns-usd_amount",
        "nzd-category-returns-usd_amount",
    ],
)
def test_reimbursement_request_reimbursement_usd_amount_property(
    basic_qualified_wallet: ReimbursementWallet,
    category_currency_code: str,
    amount: int,
    usd_amount: int,
    expected_amount: int,
):
    # Given
    category: ReimbursementRequestCategory = ReimbursementRequestCategoryFactory.create(
        label="maternity"
    )
    ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_organization_settings=basic_qualified_wallet.reimbursement_organization_settings,
        reimbursement_request_category=category,
        currency_code=category_currency_code,
    )
    request: ReimbursementRequest = ReimbursementRequestFactory.create(
        wallet=basic_qualified_wallet,
        category=category,
        amount=amount,
        usd_amount=usd_amount,
        benefit_currency_code=category_currency_code,
    )

    # When
    reimbursement_amount_usd = request.usd_reimbursement_amount

    # Then
    assert reimbursement_amount_usd == expected_amount


@pytest.mark.parametrize(
    argnames="state, description",
    argvalues=[
        (ReimbursementRequestState.NEW, "Your claim has been successfully created."),
        (
            ReimbursementRequestState.PENDING,
            "Your claim has been received and is pending review.",
        ),
        (
            ReimbursementRequestState.APPROVED,
            "Your transaction has been approved! No further action is needed.",
        ),
        (
            ReimbursementRequestState.REIMBURSED,
            "Your reimbursement is on the way! Look for it in your account "
            "(10 business days for direct deposit, 1-2 pay cycles for payroll).",
        ),
        (
            ReimbursementRequestState.PENDING_MEMBER_INPUT,
            "We are waiting on additional information from you.",
        ),
        (
            ReimbursementRequestState.DENIED,
            "Sorry, your claim is ineligible. Go to Messages to contact the "
            "Maven Wallet Team with any questions or review Coverage Details to see "
            "what services are eligible.",
        ),
        (
            ReimbursementRequestState.FAILED,
            "We're working on your reimbursement! "
            "We may reach out to confirm your bank account information.",
        ),
        (
            ReimbursementRequestState.NEEDS_RECEIPT,
            "Approval pending. Please upload required documents for approval.",
        ),
        (
            ReimbursementRequestState.RECEIPT_SUBMITTED,
            "Your documents have been received and are pending review.",
        ),
        (
            ReimbursementRequestState.INSUFFICIENT_RECEIPT,
            "Sorry, the documents submitted were insufficient. "
            "Please provide additional documentation for approval.",
        ),
        (
            ReimbursementRequestState.INELIGIBLE_EXPENSE,
            "Your recent transaction was deemed ineligible. "
            "Go to Messages to contact the Maven Wallet Team for "
            "assistance.",
        ),
        (
            ReimbursementRequestState.RESOLVED,
            "Your transaction has been resolved. No further action needed.",
        ),
        (ReimbursementRequestState.REFUNDED, "Your transaction has been refunded."),
    ],
)
def test_state_description(state, description, qualified_direct_payment_enabled_wallet):
    reimbursement_request = create_unsaved_direct_payment_reimbursement_request(
        qualified_direct_payment_enabled_wallet
    )

    reimbursement_request.state = state
    reimbursement_request.reimbursement_type = ReimbursementRequestType.DEBIT_CARD
    assert reimbursement_request.state_description == description


def test_create_reimbursement_request_wallet_state_runout(
    db, qualified_alegeus_wallet_hra
):
    # Change the qualified wallet to runout
    qualified_alegeus_wallet_hra.state = WalletState.RUNOUT
    reimbursement_request = create_unsaved_manual_reimbursement_request(
        qualified_alegeus_wallet_hra
    )

    db.session.add(reimbursement_request)
    db.session.commit()

    assert reimbursement_request


@pytest.mark.parametrize(
    "auto_processed,wallet_state,reimbursement_state",
    [
        (
            ReimbursementRequestAutoProcessing.RX,
            WalletState.QUALIFIED,
            ReimbursementRequestState.APPROVED,
        ),
        (
            ReimbursementRequestAutoProcessing.RX,
            WalletState.PENDING,
            ReimbursementRequestState.DENIED,
        ),
        (
            ReimbursementRequestAutoProcessing.RX,
            WalletState.RUNOUT,
            ReimbursementRequestState.NEW,
        ),
        (
            ReimbursementRequestAutoProcessing.RX,
            WalletState.EXPIRED,
            ReimbursementRequestState.DENIED,
        ),
        (
            ReimbursementRequestAutoProcessing.RX,
            WalletState.DISQUALIFIED,
            ReimbursementRequestState.DENIED,
        ),
        (None, WalletState.QUALIFIED, ReimbursementRequestState.NEW),
        (None, WalletState.RUNOUT, ReimbursementRequestState.PENDING),
    ],
)
def test_create_reimbursement_request_wallet_state_and_auto_rx(
    db, qualified_alegeus_wallet_hra, auto_processed, wallet_state, reimbursement_state
):
    qualified_alegeus_wallet_hra.state = wallet_state
    reimbursement_request = create_unsaved_manual_reimbursement_request(
        qualified_alegeus_wallet_hra
    )
    reimbursement_request.state = reimbursement_state
    reimbursement_request.auto_processed = auto_processed
    db.session.add(reimbursement_request)
    db.session.commit()
    assert reimbursement_request


@pytest.mark.parametrize(
    "auto_processed,wallet_state,reimbursement_state,expected_error",
    [
        (
            None,
            WalletState.PENDING,
            ReimbursementRequestState.NEW,
            "You can only add Reimbursement Requests to "
            "active qualified or runout Reimbursement "
            "Wallets.",
        ),
        (
            None,
            WalletState.EXPIRED,
            ReimbursementRequestState.APPROVED,
            "You can only add Reimbursement Requests "
            "to active qualified or runout "
            "Reimbursement Wallets.",
        ),
        (
            None,
            WalletState.DISQUALIFIED,
            ReimbursementRequestState.DENIED,
            "You can only add Reimbursement "
            "Requests to active qualified or "
            "runout Reimbursement Wallets.",
        ),
        (
            ReimbursementRequestAutoProcessing.RX,
            WalletState.PENDING,
            ReimbursementRequestState.NEW,
            "You can only "
            "create "
            "Denied "
            "Reimbursement Requests for non-active Reimbursement Wallets.",
        ),
        (
            ReimbursementRequestAutoProcessing.RX,
            WalletState.EXPIRED,
            ReimbursementRequestState.APPROVED,
            "You can only create Denied Reimbursement Requests for non-active Reimbursement Wallets.",
        ),
        (
            ReimbursementRequestAutoProcessing.RX,
            WalletState.DISQUALIFIED,
            ReimbursementRequestState.PENDING,
            "You "
            "can"
            " only create Denied Reimbursement Requests for non-active Reimbursement Wallets.",
        ),
    ],
)
def test_reimbursement_request_fails(
    db,
    qualified_alegeus_wallet_hra,
    auto_processed,
    wallet_state,
    reimbursement_state,
    expected_error,
):
    qualified_alegeus_wallet_hra.state = wallet_state
    reimbursement_request = create_unsaved_manual_reimbursement_request(
        qualified_alegeus_wallet_hra
    )
    reimbursement_request.state = reimbursement_state
    reimbursement_request.auto_processed = auto_processed
    db.session.add(reimbursement_request)
    with pytest.raises(ValueError) as e:
        db.session.commit()
    assert e.value.args[0] == expected_error


@pytest.mark.parametrize(
    argnames=(
        "label",
        "expense_type",
        "expense_subtype_code",
        "expected_description",
    ),
    argvalues=[
        # legacy-only returns legacy
        ("Legacy Label", None, None, "Legacy Label"),
        # mixed, unflagged returns legacy
        (
            "Legacy Label",
            ReimbursementRequestExpenseTypes.FERTILITY,
            None,
            "Legacy Label",
        ),
        (
            "Legacy Label",
            ReimbursementRequestExpenseTypes.FERTILITY,
            "FIVF",
            "Legacy Label",
        ),
        # flagged returns generated
        (
            ReimbursementRequest.AUTO_LABEL_FLAG,
            ReimbursementRequestExpenseTypes.FERTILITY,
            None,
            "Fertility - Other",
        ),
        (
            ReimbursementRequest.AUTO_LABEL_FLAG,
            ReimbursementRequestExpenseTypes.FERTILITY,
            "FIVF",
            "Fertility - IVF (with fresh transfer)",
        ),
        (
            ReimbursementRequest.AUTO_LABEL_FLAG,
            ReimbursementRequestExpenseTypes.FERTILITY,
            "FRTTRAVEL",
            "Fertility - Fertility Travel",
        ),
        # Bad state
        (
            ReimbursementRequest.AUTO_LABEL_FLAG,
            None,
            None,
            "Unknown - Other",
        ),
    ],
)
def test_reimbursement_request_formatted_label(
    label,
    expense_type,
    expense_subtype_code,
    expected_description,
    qualified_alegeus_wallet_hra,
    expense_subtypes,
):
    category: ReimbursementOrgSettingCategoryAssociation = qualified_alegeus_wallet_hra.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ]
    rr: ReimbursementRequest = ReimbursementRequestFactory.create(
        amount=100,
        reimbursement_wallet_id=qualified_alegeus_wallet_hra.id,
        reimbursement_request_category_id=category.reimbursement_request_category_id,
        state=ReimbursementRequestState.PENDING,
        created_at=datetime.date.today(),
        label=label,
        expense_type=expense_type,
        wallet_expense_subtype=expense_subtypes[expense_subtype_code]
        if expense_subtype_code
        else None,
    )

    assert rr.formatted_label == expected_description
