import datetime
from unittest import mock

import factory
import pytest

from admin.views.models.wallet import (
    ReimbursementWalletView,
    total_reimbursed_formatter,
)
from wallet.models.constants import BenefitTypes
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.pytests import factories
from wallet.pytests.factories import (
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementWalletFactory,
)


class TestWalletView:
    def test_create_model_handle_state_change(self, admin_app, session):
        wallet = ReimbursementWalletFactory.create()

        with mock.patch("flask_admin.model.base.flash") as flash, mock.patch(
            "flask_admin.actions.ActionsMixin.init_actions", return_value=False
        ):
            view = ReimbursementWalletView(ReimbursementWallet, session=session)

            # NOTE: here we are only testing handle_wallet_state_change -- everything else is mocked
            with admin_app.app.test_request_context(
                "/admin/reimbursementwallet/new"
            ), mock.patch(
                "flask_admin.model.base.get_redirect_target", return_value="/test"
            ), mock.patch.multiple(
                "admin.views.models.wallet.ReimbursementWalletView",
                validate_new_data=mock.MagicMock(return_value=True),
                get_or_create_reimbursement_wallet_user=mock.MagicMock(),
                validate_form=mock.MagicMock(return_value=True),
                create_form=mock.MagicMock(
                    return_value=mock.MagicMock(name="Fake Form Data")
                ),
            ), mock.patch.multiple(
                "admin.views.models.wallet",
                super=mock.MagicMock(
                    name="Super Mock",
                    return_value=mock.MagicMock(
                        name="Returned From Super Mock",
                        create_model=mock.MagicMock(return_value=wallet),
                    ),
                ),
                get_or_create_rwu_channel=mock.MagicMock(),
                open_zendesk_ticket=mock.MagicMock(),
                eligibility=mock.MagicMock(get_verification_service=mock.MagicMock()),
            ):
                response = view.create_view()

        assert flash.call_args == mock.call(
            "Record was successfully created.", "success"
        )
        assert response.status_code == 302

    @pytest.mark.parametrize(
        "size,start_dates,end_dates,calls_expected",
        [
            (0, None, None, 0),
            (
                1,
                [datetime.datetime(2024, 1, 1, 0, 0, 0)],
                [datetime.datetime(2025, 12, 31, 23, 59, 59)],
                0,
            ),
            (
                1,
                [datetime.datetime(2024, 1, 1, 23, 1, 1)],
                [datetime.datetime(2025, 12, 31, 6, 0, 0)],
                1,
            ),
            (
                2,
                [
                    datetime.datetime(2023, 1, 1, 0, 0, 0),
                    datetime.datetime(2024, 1, 1, 23, 1, 1),
                ],
                [
                    datetime.datetime(2023, 12, 31, 23, 59, 59),
                    datetime.datetime(2025, 12, 31, 6, 0, 0),
                ],
                1,
            ),
            (
                2,
                [
                    datetime.datetime(2023, 1, 1, 0, 10, 0),
                    datetime.datetime(2024, 1, 1, 23, 1, 1),
                ],
                [
                    datetime.datetime(2023, 12, 31, 23, 0, 59),
                    datetime.datetime(2025, 12, 31, 6, 0, 0),
                ],
                2,
            ),
        ],
    )
    def test_force_health_plan_dates(
        self, admin_app, session, size, start_dates, end_dates, calls_expected
    ):
        wallet = ReimbursementWalletFactory.create()
        employer_health_plans = EmployerHealthPlanFactory.create_batch(
            size=size,
            start_date=datetime.date(2020, 1, 1),
            end_date=datetime.date(2026, 12, 31),
        )
        health_plans = MemberHealthPlanFactory.create_batch(
            size=size,
            reimbursement_wallet=wallet,
            employer_health_plan=factory.Iterator(employer_health_plans),
            plan_start_at=factory.Iterator(start_dates),
            plan_end_at=factory.Iterator(end_dates),
        )

        with mock.patch("admin.views.models.wallet.flash") as flash, mock.patch(
            "flask_admin.actions.ActionsMixin.init_actions", return_value=False
        ):
            view = ReimbursementWalletView(ReimbursementWallet, session=session)
            view.force_health_plan_dates(health_plans)
        assert flash.call_count == calls_expected


class TestTotalReimbursedFormatter:
    @staticmethod
    def test_when_categories_are_not_configured():
        # Given
        wallet: ReimbursementWallet = factories.ReimbursementWalletFactory(
            reimbursement_organization_settings__allowed_reimbursement_categories__no_categories=True,
        )

        # When
        formatted: str = total_reimbursed_formatter(wallet=wallet)

        # Then
        assert formatted == "NO CATEGORIES CONFIGURED"

    @staticmethod
    def test_when_categories_are_cycle_based():
        # Given
        wallet: ReimbursementWallet = factories.ReimbursementWalletFactory(
            reimbursement_organization_settings__allowed_reimbursement_categories=[],
            reimbursement_organization_settings__allowed_reimbursement_categories__cycle_based=True,
        )

        # When
        formatted: str = total_reimbursed_formatter(wallet=wallet)

        # Then
        assert formatted == "CYCLE BASED"

    @staticmethod
    def test_when_categories_are_mixed():
        # Given
        wallet: ReimbursementWallet = factories.ReimbursementWalletFactory(
            reimbursement_organization_settings__allowed_reimbursement_categories=[
                ("adoption", 500000, "USD")
            ],
            reimbursement_organization_settings__allowed_reimbursement_categories__cycle_based=True,
        )
        # Add a cycle based category
        category = factories.ReimbursementRequestCategoryFactory.create(
            label="fertility"
        )
        factories.ReimbursementOrgSettingCategoryAssociationFactory.create(
            reimbursement_organization_settings_id=wallet.reimbursement_organization_settings_id,
            reimbursement_request_category_id=category.id,
            benefit_type=BenefitTypes.CYCLE,
            num_cycles=5,
        )

        # When
        formatted: str = total_reimbursed_formatter(wallet=wallet)

        # Then
        assert formatted == "CYCLE AND CURRENCY CATEGORIES CONFIGURED"

    @staticmethod
    def test_when_categories_have_multiple_currencies():
        # Given
        wallet: ReimbursementWallet = factories.ReimbursementWalletFactory(
            reimbursement_organization_settings__allowed_reimbursement_categories=[
                ("adoption", 500000, "USD"),
                ("surrogacy", 500000, "GBP"),
            ],
        )

        # When
        formatted: str = total_reimbursed_formatter(wallet=wallet)

        # Then
        assert formatted == "MULTIPLE CURRENCIES CONFIGURED"

    @staticmethod
    def test_formatter_when_formatting_amounts_usd():
        # Given
        wallet: ReimbursementWallet = factories.ReimbursementWalletFactory(
            reimbursement_organization_settings__allowed_reimbursement_categories=[
                ("adoption", 500000, "USD"),
                ("surrogacy", 500000, "USD"),
            ],
        )
        reimbursed_amount = 500000
        available_amount = 1000000

        # When
        with mock.patch(
            "wallet.models.reimbursement_wallet.ReimbursementWallet.total_available_amount",
            new_callable=mock.PropertyMock,
            return_value=available_amount,
        ), mock.patch(
            "wallet.models.reimbursement_wallet.ReimbursementWallet.total_reimbursed_amount",
            new_callable=mock.PropertyMock,
            return_value=reimbursed_amount,
        ):
            formatted: str = total_reimbursed_formatter(wallet=wallet)

        # Then
        assert formatted == "$5,000.00 of $10,000.00"

    @staticmethod
    def test_formatter_when_formatting_amounts_usd_pre_backfill():
        # Given
        wallet: ReimbursementWallet = factories.ReimbursementWalletFactory(
            reimbursement_organization_settings__allowed_reimbursement_categories=[
                ("adoption", 500000, None),
                ("surrogacy", 500000, None),
            ],
        )
        reimbursed_amount = 500000
        available_amount = 1000000

        # When
        with mock.patch(
            "wallet.models.reimbursement_wallet.ReimbursementWallet.total_available_amount",
            new_callable=mock.PropertyMock,
            return_value=available_amount,
        ), mock.patch(
            "wallet.models.reimbursement_wallet.ReimbursementWallet.total_reimbursed_amount",
            new_callable=mock.PropertyMock,
            return_value=reimbursed_amount,
        ):
            formatted: str = total_reimbursed_formatter(wallet=wallet)

        # Then
        assert formatted == "$5,000.00 of $10,000.00"

    @staticmethod
    def test_formatter_when_formatting_amounts_non_usd():
        # Given
        wallet: ReimbursementWallet = factories.ReimbursementWalletFactory(
            reimbursement_organization_settings__allowed_reimbursement_categories=[
                ("adoption", 500000, "AUD"),
                ("surrogacy", 500000, "AUD"),
            ],
        )
        reimbursed_amount = 500000
        available_amount = 1000000

        # When
        with mock.patch(
            "wallet.models.reimbursement_wallet.ReimbursementWallet.total_available_amount",
            new_callable=mock.PropertyMock,
            return_value=available_amount,
        ), mock.patch(
            "wallet.models.reimbursement_wallet.ReimbursementWallet.total_reimbursed_amount",
            new_callable=mock.PropertyMock,
            return_value=reimbursed_amount,
        ):
            formatted: str = total_reimbursed_formatter(wallet=wallet)

        # Then
        assert formatted == "A$5,000.00 of A$10,000.00"
