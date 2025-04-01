from __future__ import annotations

from decimal import Decimal
from unittest import mock

import pytest

from wallet.constants import UNLIMITED_FUNDING_USD_CENTS
from wallet.models.constants import BenefitTypes
from wallet.models.reimbursement import ReimbursementPlan, ReimbursementRequestCategory
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
    ReimbursementOrgSettingCategoryAssociation,
    WalletOrganizationConfigurationError,
)
from wallet.pytests.factories import (
    ReimbursementOrganizationSettingsFactory,
    ReimbursementOrgSettingCategoryAssociationFactory,
    ReimbursementRequestCategoryFactory,
)


def test_reimburse_org_settings_default(enterprise_user):
    org_setting = ReimbursementOrganizationSettingsFactory(
        organization_id=enterprise_user.organization.id,
        organization=enterprise_user.organization,
    )
    assert org_setting.debit_card_enabled is False
    assert org_setting.survey_url == "fake-url"
    assert org_setting.taxation_status is None
    assert org_setting.benefit_faq_resource is not None

    org_setting = ReimbursementOrganizationSettingsFactory(
        organization_id=enterprise_user.organization.id,
        organization=enterprise_user.organization,
        debit_card_enabled=True,
    )
    assert org_setting.debit_card_enabled is True
    assert org_setting.survey_url == "fake-url"
    assert org_setting.taxation_status is None
    assert org_setting.benefit_faq_resource is not None


class TestReimbursementOrgSettingCategoryAssociationUsdFundingAmount:
    @staticmethod
    @pytest.mark.parametrize(
        argnames=(
            "benefit_type",
            "currency_code",
            "is_unlimited",
            "currency_max",
            "benefit_to_usd_rate",
            "num_cycles",
            "expected_usd_amount",
        ),
        argvalues=[
            # correctly configured - USD
            (
                BenefitTypes.CURRENCY,
                None,
                False,
                25_000_00,
                Decimal("1.0"),
                None,
                25_000_00,
            ),
            (
                BenefitTypes.CURRENCY,
                "USD",
                False,
                25_000_00,
                Decimal("1.0"),
                None,
                25_000_00,
            ),
            # Unlimited benefits
            (
                BenefitTypes.CURRENCY,
                "USD",
                True,
                None,
                None,
                None,
                UNLIMITED_FUNDING_USD_CENTS,
            ),
            (BenefitTypes.CYCLE, None, False, None, None, 1, 40_000_00),
            (BenefitTypes.CYCLE, None, False, None, None, 5, 200_000_00),
            # correctly configured - non-USD
            (
                BenefitTypes.CURRENCY,
                "AUD",
                False,
                25_000_00,
                Decimal("2.0"),
                None,
                50_000_00,
            ),
            (
                BenefitTypes.CURRENCY,
                "NZD",
                False,
                25_000_00,
                Decimal("2.0"),
                None,
                50_000_00,
            ),
            (BenefitTypes.CYCLE, None, False, None, None, 1, 40_000_00),
            (BenefitTypes.CYCLE, None, False, None, None, 5, 200_000_00),
            # incorrectly configured
            (
                BenefitTypes.CURRENCY,
                None,
                False,
                0,
                Decimal("1.0"),
                None,
                0,
            ),  # currency, zero max
            (
                BenefitTypes.CURRENCY,
                None,
                False,
                None,
                Decimal("1.0"),
                None,
                0,
            ),  # currency, null max
            (
                BenefitTypes.CURRENCY,
                None,
                False,
                25_000_00,
                Decimal("1.0"),
                5,
                25_000_00,
            ),  # currency, cycles configured
            (BenefitTypes.CYCLE, None, False, None, None, 0, 0),  # cycle, zero cycles
            (
                BenefitTypes.CYCLE,
                None,
                False,
                None,
                None,
                None,
                0,
            ),  # currency, null cycles
            (
                BenefitTypes.CYCLE,
                None,
                False,
                25_000_00,
                None,
                2,
                80_000_00,
            ),  # cycle, currency configured
        ],
    )
    def test_reimbursement_org_settings_category_association_usd_funding_amount(
        wallet_org_settings: ReimbursementOrganizationSettings,
        valid_alegeus_plan_hra: ReimbursementPlan,
        benefit_type: BenefitTypes,
        currency_code: str | None,
        is_unlimited: bool,
        currency_max: int,
        benefit_to_usd_rate: Decimal | None,
        num_cycles: int | None,
        expected_usd_amount: int,
    ):
        # Given
        category: ReimbursementRequestCategory = (
            ReimbursementRequestCategoryFactory.create(
                label="Family Building", reimbursement_plan=valid_alegeus_plan_hra
            )
        )
        allowed_category: ReimbursementOrgSettingCategoryAssociation = (
            ReimbursementOrgSettingCategoryAssociationFactory.create(
                reimbursement_organization_settings=wallet_org_settings,
                reimbursement_request_category=category,
                benefit_type=benefit_type,
                is_unlimited=is_unlimited,
                currency_code=currency_code,
                reimbursement_request_category_maximum=currency_max,
                num_cycles=num_cycles,
            )
        )

        # When
        with mock.patch(
            "wallet.repository.currency_fx_rate.CurrencyFxRateRepository.get_rate"
        ) as mock_get_rate:
            mock_get_rate.return_value = benefit_to_usd_rate
            usd_amount: int = allowed_category.usd_funding_amount

        # Then
        assert usd_amount == expected_usd_amount

    @staticmethod
    def test_reimbursement_org_settings_category_association_invalid_unlimited_cycle(
        wallet_org_settings: ReimbursementOrganizationSettings,
        valid_alegeus_plan_hra: ReimbursementPlan,
    ):
        # Given
        category: ReimbursementRequestCategory = (
            ReimbursementRequestCategoryFactory.create(
                label="Family Building", reimbursement_plan=valid_alegeus_plan_hra
            )
        )
        allowed_category: ReimbursementOrgSettingCategoryAssociation = (
            ReimbursementOrgSettingCategoryAssociationFactory.create(
                reimbursement_organization_settings=wallet_org_settings,
                reimbursement_request_category=category,
                benefit_type=BenefitTypes.CYCLE,
                is_unlimited=True,
                currency_code=None,
                reimbursement_request_category_maximum=None,
                num_cycles=1,
            )
        )

        # When - Then
        with pytest.raises(
            WalletOrganizationConfigurationError,
            match="Unlimited benefits can only be configured for CURRENCY benefits",
        ):
            _ = allowed_category.usd_funding_amount

    @staticmethod
    def test_reimbursement_org_settings_category_association_usd_funding_amount_mixed(
        wallet_org_settings: ReimbursementOrganizationSettings,
        valid_alegeus_plan_hra: ReimbursementPlan,
    ):
        # Given
        category_1: ReimbursementRequestCategory = (
            ReimbursementRequestCategoryFactory.create(
                label="Fertility", reimbursement_plan=valid_alegeus_plan_hra
            )
        )
        allowed_category_1: ReimbursementOrgSettingCategoryAssociation = (
            ReimbursementOrgSettingCategoryAssociationFactory.create(
                reimbursement_organization_settings=wallet_org_settings,
                reimbursement_request_category=category_1,
                benefit_type=BenefitTypes.CYCLE,
                num_cycles=2,
            )
        )
        category_2: ReimbursementRequestCategory = (
            ReimbursementRequestCategoryFactory.create(
                label="Adoption & Surrogacy", reimbursement_plan=valid_alegeus_plan_hra
            )
        )
        allowed_category_2: ReimbursementOrgSettingCategoryAssociation = (
            ReimbursementOrgSettingCategoryAssociationFactory.create(
                reimbursement_organization_settings=wallet_org_settings,
                reimbursement_request_category=category_2,
                benefit_type=BenefitTypes.CURRENCY,
                currency_code="AUD",
                reimbursement_request_category_maximum=25_000_00,
            )
        )

        # When
        with mock.patch(
            "wallet.repository.currency_fx_rate.CurrencyFxRateRepository.get_rate"
        ) as mock_get_rate:
            mock_get_rate.return_value = Decimal("2.00")
            usd_amount_1: int = allowed_category_1.usd_funding_amount
            usd_amount_2: int = allowed_category_2.usd_funding_amount

        # Then
        assert (usd_amount_1, usd_amount_2) == (80_000_00, 50_000_00)
