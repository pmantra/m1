from __future__ import annotations

from decimal import Decimal
from unittest import mock
from unittest.mock import MagicMock

import pytest

from admin.views.models.wallet_category import (
    CategoryMaximumAmountForm,
    ReimbursementOrgSettingCategoryAssociationForm,
    category_maximum_amount_formatter,
    validate_reimbursement_org_setting_category_association,
)
from wallet.models.constants import BenefitTypes
from wallet.models.currency import Money
from wallet.models.reimbursement import ReimbursementRequestCategory
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
    ReimbursementOrgSettingCategoryAssociation,
)


@pytest.fixture(scope="function")
def reimbursement_organization_settings():
    return MagicMock(spec=ReimbursementOrganizationSettings)


@pytest.fixture(scope="function")
def reimbursement_request_category():
    return MagicMock(spec=ReimbursementRequestCategory)


@pytest.fixture
def category_association():
    return MagicMock(spec=ReimbursementOrgSettingCategoryAssociation)


@pytest.fixture
def category_association_form():
    form = ReimbursementOrgSettingCategoryAssociationForm()
    return form


class TestFormatters:
    @staticmethod
    def test_category_maximum_amount_formatter_calls_format_display_amount():
        # Given
        expected_currency_code = "USD"
        expected_maximum = 100
        category = ReimbursementOrgSettingCategoryAssociation(
            benefit_type=BenefitTypes.CURRENCY,
            currency_code=expected_currency_code,
            reimbursement_request_category_maximum=expected_maximum,
            is_unlimited=False,
        )
        money_amount = Money(
            amount=Decimal(expected_maximum), currency_code=expected_currency_code
        )
        view, context, name = MagicMock(), MagicMock(), MagicMock()

        # When
        with mock.patch(
            "wallet.services.currency.CurrencyService.to_money"
        ) as mock_to_money, mock.patch(
            "admin.views.models.wallet_category.format_display_amount_with_currency_code"
        ) as mock_format:
            mock_to_money.return_value = money_amount

            category_maximum_amount_formatter(
                view=view, context=context, model=category, name=name
            )

        # Then
        mock_format.assert_called_with(money=money_amount)

    @staticmethod
    def test_category_maximum_amount_formatter_unlimited_benefits():
        # Given
        category = ReimbursementOrgSettingCategoryAssociation(
            benefit_type=BenefitTypes.CURRENCY,
            currency_code="USD",
            reimbursement_request_category_maximum=None,
            is_unlimited=True,
        )
        view, context, name = MagicMock(), MagicMock(), MagicMock()

        # When
        formatted: str = category_maximum_amount_formatter(
            view=view, context=context, model=category, name=name
        )

        # Then
        assert formatted == "UNLIMITED"

    @staticmethod
    @pytest.mark.parametrize(
        argnames=("amount", "currency_code"),
        argvalues=[(None, None), (1000, None), (None, "USD")],
    )
    def test_transaction_amount_formatter_returns_empty_string_when_input_is_missing(
        amount: str | None, currency_code: int | None
    ):
        # Given
        category = ReimbursementOrgSettingCategoryAssociation(
            currency_code=currency_code, reimbursement_request_category_maximum=amount
        )
        view, context, name = MagicMock(), MagicMock(), MagicMock()

        # When
        formatted: str = category_maximum_amount_formatter(
            view=view, context=context, model=category, name=name
        )

        # Then
        assert formatted == ""


class TestCategoryMaximumAmountForm:
    @staticmethod
    def test_on_form_prefill_limited_benefit(currency_service):
        # Given
        expected_currency_code = "USD"
        expected_minor_unit = 2
        expected_maximum = 100
        form = CategoryMaximumAmountForm()
        category = ReimbursementOrgSettingCategoryAssociation(
            currency_code=expected_currency_code,
            reimbursement_request_category_maximum=expected_maximum,
            is_unlimited=False,
        )
        money = Money(
            amount=Decimal(expected_maximum), currency_code=expected_currency_code
        )
        currency_service.currency_code_repo.get_minor_unit.return_value = (
            expected_minor_unit
        )

        # When
        with mock.patch(
            "wallet.services.currency.CurrencyService.to_money"
        ) as mock_to_money:
            mock_to_money.return_value = money
            form.on_form_prefill(currency_service=currency_service, category=category)

        # Then
        assert form.amount.data == expected_maximum
        assert form.currency_code.data == expected_currency_code
        assert form.amount.places == expected_minor_unit
        assert form.is_unlimited.data is False

    @staticmethod
    def test_on_form_prefill_unlimited_benefit(currency_service):
        # Given
        expected_currency_code = "USD"
        form = CategoryMaximumAmountForm()
        category = ReimbursementOrgSettingCategoryAssociation(
            currency_code=expected_currency_code,
            reimbursement_request_category_maximum=None,
            is_unlimited=True,
        )

        # When
        form.on_form_prefill(currency_service=currency_service, category=category)

        # Then
        assert form.amount.data is None
        assert form.currency_code.data == expected_currency_code
        assert form.is_unlimited.data is True


class TestValidateCategoryAssociation:
    @staticmethod
    def test_validate_currency_valid(
        mock_request_ctx,
        reimbursement_organization_settings,
        reimbursement_request_category,
    ):
        result = validate_reimbursement_org_setting_category_association(
            reimbursement_organization_settings=reimbursement_organization_settings,
            reimbursement_request_category=reimbursement_request_category,
            benefit_type=BenefitTypes.CURRENCY.value,
            is_unlimited=False,
            num_cycles=None,
            currency_code="USD",
            category_maximum_amount=1000,
            is_valid=True,
        )
        assert result is True

    @staticmethod
    def test_validate_currency_invalid_no_currency_code(
        mock_request_ctx,
        reimbursement_organization_settings,
        reimbursement_request_category,
    ):
        result = validate_reimbursement_org_setting_category_association(
            reimbursement_organization_settings=reimbursement_organization_settings,
            reimbursement_request_category=reimbursement_request_category,
            benefit_type=BenefitTypes.CURRENCY.value,
            is_unlimited=False,
            num_cycles=None,
            currency_code=None,
            category_maximum_amount=1000,
            is_valid=True,
        )
        assert result is False

    @staticmethod
    def test_validate_cycle_valid(
        mock_request_ctx,
        reimbursement_organization_settings,
        reimbursement_request_category,
    ):
        reimbursement_organization_settings.debit_card_enabled = False
        reimbursement_organization_settings.direct_payment_enabled = True
        reimbursement_organization_settings.closed_network = True

        result = validate_reimbursement_org_setting_category_association(
            reimbursement_organization_settings=reimbursement_organization_settings,
            reimbursement_request_category=reimbursement_request_category,
            benefit_type=BenefitTypes.CYCLE.value,
            is_unlimited=False,
            num_cycles=2,
            currency_code=None,
            category_maximum_amount=None,
            is_valid=True,
        )
        assert result is True

    @staticmethod
    def test_validate_cycle_invalid_no_num_cycles(
        mock_request_ctx,
        reimbursement_organization_settings,
        reimbursement_request_category,
    ):
        reimbursement_organization_settings.debit_card_enabled = False
        reimbursement_organization_settings.direct_payment_enabled = True
        reimbursement_organization_settings.closed_network = True

        result = validate_reimbursement_org_setting_category_association(
            reimbursement_organization_settings=reimbursement_organization_settings,
            reimbursement_request_category=reimbursement_request_category,
            benefit_type=BenefitTypes.CYCLE.value,
            is_unlimited=False,
            num_cycles=None,
            currency_code=None,
            category_maximum_amount=None,
            is_valid=True,
        )
        assert result is False

    @staticmethod
    def test_validate_currency_invalid_amount_set_for_unlimited(
        mock_request_ctx,
        reimbursement_organization_settings,
        reimbursement_request_category,
    ):
        result = validate_reimbursement_org_setting_category_association(
            reimbursement_organization_settings=reimbursement_organization_settings,
            reimbursement_request_category=reimbursement_request_category,
            benefit_type=BenefitTypes.CURRENCY.value,
            is_unlimited=True,
            num_cycles=None,
            currency_code="USD",
            category_maximum_amount=1000,
            is_valid=True,
        )
        assert result is False

    @staticmethod
    def test_validate_cycle_invalid_unlimited(
        mock_request_ctx,
        reimbursement_organization_settings,
        reimbursement_request_category,
    ):
        reimbursement_organization_settings.debit_card_enabled = False
        reimbursement_organization_settings.direct_payment_enabled = True
        reimbursement_organization_settings.closed_network = True

        result = validate_reimbursement_org_setting_category_association(
            reimbursement_organization_settings=reimbursement_organization_settings,
            reimbursement_request_category=reimbursement_request_category,
            benefit_type=BenefitTypes.CYCLE.value,
            is_unlimited=True,
            num_cycles=2,
            currency_code=None,
            category_maximum_amount=None,
            is_valid=True,
        )
        assert result is False

    @staticmethod
    def test_validate_cycle_invalid_debit_card_enabled(
        mock_request_ctx,
        reimbursement_organization_settings,
        reimbursement_request_category,
    ):
        reimbursement_organization_settings.debit_card_enabled = True
        reimbursement_organization_settings.direct_payment_enabled = True
        reimbursement_organization_settings.closed_network = True

        result = validate_reimbursement_org_setting_category_association(
            reimbursement_organization_settings=reimbursement_organization_settings,
            reimbursement_request_category=reimbursement_request_category,
            benefit_type=BenefitTypes.CYCLE.value,
            is_unlimited=False,
            num_cycles=2,
            currency_code=None,
            category_maximum_amount=None,
            is_valid=True,
        )
        assert result is False

    @staticmethod
    def test_validate_cycle_invalid_direct_payment_disabled(
        mock_request_ctx,
        reimbursement_organization_settings,
        reimbursement_request_category,
    ):
        reimbursement_organization_settings.debit_card_enabled = False
        reimbursement_organization_settings.direct_payment_enabled = False
        reimbursement_organization_settings.closed_network = True

        result = validate_reimbursement_org_setting_category_association(
            reimbursement_organization_settings=reimbursement_organization_settings,
            reimbursement_request_category=reimbursement_request_category,
            benefit_type=BenefitTypes.CYCLE.value,
            is_unlimited=False,
            num_cycles=2,
            currency_code=None,
            category_maximum_amount=None,
            is_valid=True,
        )
        assert result is False

    @staticmethod
    def test_validate_cycle_invalid_closed_network_disabled(
        mock_request_ctx,
        reimbursement_organization_settings,
        reimbursement_request_category,
    ):
        reimbursement_organization_settings.debit_card_enabled = False
        reimbursement_organization_settings.direct_payment_enabled = True
        reimbursement_organization_settings.closed_network = False

        result = validate_reimbursement_org_setting_category_association(
            reimbursement_organization_settings=reimbursement_organization_settings,
            reimbursement_request_category=reimbursement_request_category,
            benefit_type=BenefitTypes.CYCLE.value,
            is_unlimited=False,
            num_cycles=2,
            currency_code=None,
            category_maximum_amount=None,
            is_valid=True,
        )
        assert result is False
