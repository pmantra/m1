import pytest

from wallet.models.constants import ReimbursementRequestExpenseTypes
from wallet.pytests.factories import (
    ReimbursementRequestCategoryExpenseTypesFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
)


@pytest.mark.parametrize(
    argnames="country_code,primary_expense_type,category_expense_types,direct_payment_enabled,expected",
    argvalues=[
        # eligible if country is US and category expense type is within eligible fertility type
        # and direct payment is enabled
        ("US", None, ["FERTILITY"], True, True),
        # not eligible if country is not US
        ("CA", None, ["FERTILITY"], True, False),
        # eligible with two eligible fertility expense types and direct payment is enabled
        ("US", None, ["FERTILITY", "PRESERVATION"], True, True),
        # not eligible with non-fertility primary and mixed expense types and direct payment is enabled
        ("US", None, ["FERTILITY", "SURROGACY", "ADOPTION"], True, False),
        ("US", "ADOPTION", ["FERTILITY", "SURROGACY", "ADOPTION"], True, False),
        # eligible with non-fertility primary and only eligible fertility expense types and direct payment is enabled
        ("US", None, ["FERTILITY", "PRESERVATION"], True, True),
        ("US", "ADOPTION", ["FERTILITY", "PRESERVATION"], True, True),
        # eligible if any expense type is within eligible types and direct payment is enabled
        ("US", "FERTILITY", ["FERTILITY", "SURROGACY", "ADOPTION"], True, True),
        # not eligible if expense type is not one of the defined fertility types
        ("US", None, ["ADOPTION"], True, False),
        ("US", "FERTILITY", ["ADOPTION"], True, False),
        ("US", "ADOPTION", ["ADOPTION"], True, False),
        # not eligible if no expense types are mapped to the category and direct payment is enabled
        ("US", None, [], True, False),
        ("US", "FERTILITY", [], True, False),
        ("US", "ADOPTION", [], True, False),
        # not eligible if direct payment is not enabled, regardless of country or expense types
        ("US", "FERTILITY", ["FERTILITY"], False, False),
        ("CA", "FERTILITY", ["FERTILITY"], False, False),
        ("US", "FERTILITY", ["FERTILITY", "PRESERVATION"], False, False),
        ("US", "FERTILITY", ["FERTILITY", "SURROGACY", "ADOPTION"], False, False),
        ("US", "FERTILITY", ["ADOPTION"], False, False),
        ("US", "FERTILITY", [], False, False),
    ],
)
def test_reimbursement_request_category_direct_payment_eligible(
    enterprise_user,
    country_code,
    primary_expense_type,
    category_expense_types,
    direct_payment_enabled,
    expected,
):
    reimbursement_wallet = ReimbursementWalletFactory.create()
    if primary_expense_type:
        reimbursement_wallet.primary_expense_type = ReimbursementRequestExpenseTypes[
            primary_expense_type
        ]
    reimbursement_wallet.reimbursement_organization_settings.direct_payment_enabled = (
        direct_payment_enabled
    )
    wallet_user = ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=reimbursement_wallet.id,
    )
    wallet_user.member.member_profile.country_code = country_code
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
    assert category.is_direct_payment_eligible(reimbursement_wallet) is expected


@pytest.mark.parametrize(
    argnames="category_expense_types,expected",
    argvalues=[
        # meets criteria if only type is fertility-related
        (["FERTILITY"], True),
        # meets criteria if multiple types are all fertility-related
        (["FERTILITY", "PRESERVATION"], True),
        # meets criteria if types are mixed
        (["FERTILITY", "SURROGACY", "ADOPTION"], True),
        # does not meet criteria without any fertility-related type
        (["ADOPTION"], False),
        # does not meet criteria without any types
        ([], False),
    ],
)
def test_has_fertility_expense_type(category_expense_types, expected):
    category = ReimbursementRequestCategoryFactory.create(label="Family Building")
    if len(category_expense_types) > 0:
        for type in category_expense_types:
            ReimbursementRequestCategoryExpenseTypesFactory.create(
                reimbursement_request_category_id=category.id,
                reimbursement_request_category=category,
                expense_type=ReimbursementRequestExpenseTypes[type],
            )
    assert category.has_fertility_expense_type() is expected
