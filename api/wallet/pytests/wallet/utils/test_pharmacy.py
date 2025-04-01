import pytest

from wallet.models.constants import ReimbursementRequestExpenseTypes
from wallet.pytests.factories import ReimbursementRequestCategoryExpenseTypesFactory
from wallet.utils.pharmacy import (
    ALTO_PHARMACY_REGIONS,
    SMP_PHARMACY_REGIONS,
    Pharmacy,
    get_pharmacy_by_state,
    get_pharmacy_details_for_wallet,
)


def test_get_pharmacy_details_for_wallet__success(
    qualified_alegeus_wallet_hra, enterprise_user
):
    enterprise_user.profile.country_code = "US"
    enterprise_user.profile.subdivision_code = "US-NY"

    details = get_pharmacy_details_for_wallet(
        member=enterprise_user, wallet=qualified_alegeus_wallet_hra
    )
    assert details["name"] == "Alto Pharmacy"
    assert "alto" in details["url"]


def test_get_pharmacy_details_for_direct_payment_wallet__success(
    qualified_direct_payment_enabled_wallet, enterprise_user
):
    """
    DP wallet should always return SMP
    """
    qualified_direct_payment_enabled_wallet.primary_expense_type = (
        ReimbursementRequestExpenseTypes.FERTILITY
    )
    category = qualified_direct_payment_enabled_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        1
    ].reimbursement_request_category
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category_id=category.id,
        reimbursement_request_category=category,
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
    )

    enterprise_user.profile.country_code = "US"
    enterprise_user.profile.subdivision_code = "US-NY"

    details = get_pharmacy_details_for_wallet(
        member=enterprise_user, wallet=qualified_direct_payment_enabled_wallet
    )
    assert details["name"] == "SMP Pharmacy"
    assert "smp" in details["url"]


def test_get_pharmacy_details_for_direct_payment_wallet_with_rx__success(
    qualified_direct_payment_enabled_wallet, enterprise_user
):
    """
    DP wallet *with DP RX* changes the pharmacy
    """
    qualified_direct_payment_enabled_wallet.reimbursement_organization_settings.rx_direct_payment_enabled = (
        True
    )
    qualified_direct_payment_enabled_wallet.primary_expense_type = (
        ReimbursementRequestExpenseTypes.FERTILITY
    )
    category = qualified_direct_payment_enabled_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        1
    ].reimbursement_request_category
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category_id=category.id,
        reimbursement_request_category=category,
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
    )

    enterprise_user.profile.country_code = "US"
    enterprise_user.profile.subdivision_code = "US-NY"

    details = get_pharmacy_details_for_wallet(
        member=enterprise_user, wallet=qualified_direct_payment_enabled_wallet
    )
    assert details["name"] == "SMP Pharmacy"
    assert "smp" in details["url"]


def test_get_pharmacy_details_for_wallet__no_state(
    qualified_alegeus_wallet_hra, enterprise_user
):
    enterprise_user.profile.country_code = "US"
    details = get_pharmacy_details_for_wallet(
        member=enterprise_user, wallet=qualified_alegeus_wallet_hra
    )

    assert details is None


def test_get_pharmacy_details_for_wallet__no_wallet(enterprise_user):
    enterprise_user.profile.country_code = "US"
    enterprise_user.profile.subdivision_code = "US-NY"

    details = get_pharmacy_details_for_wallet(member=enterprise_user, wallet=None)

    assert details["name"] == "Alto Pharmacy"
    assert "alto" in details["url"]


def test_get_pharmacy_details_for_wallet__intl(
    qualified_alegeus_wallet_hra, enterprise_user
):
    enterprise_user.profile.country_code = "CA"
    details = get_pharmacy_details_for_wallet(
        member=enterprise_user, wallet=qualified_alegeus_wallet_hra
    )

    assert details is None


@pytest.mark.parametrize(
    argnames="state,expected",
    argvalues=[("NY", Pharmacy.ALTO), ("DC", Pharmacy.SMP), ("UM", None)],
)
def test_get_pharmacy_by_state(state, expected):
    assert expected == get_pharmacy_by_state(state)


def test_no_overlap_in_different_pharmacy_regions():
    potential_overlap: set[str] = ALTO_PHARMACY_REGIONS & SMP_PHARMACY_REGIONS
    assert len(potential_overlap) == 0


def test_pharmacy_regions_covers_51_areas():
    # At this point it's the 50 states + DC
    all_regions: set[str] = ALTO_PHARMACY_REGIONS | SMP_PHARMACY_REGIONS
    assert all(len(region) == 2 for region in all_regions)
    assert len(all_regions) == 51
