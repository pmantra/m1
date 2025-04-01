from unittest.mock import patch

import pytest

from admin.views.models.wallet import WalletClientReportConfigurationView
from storage.connection import db
from wallet.models.reimbursement_wallet_report import (
    WalletClientReportConfiguration,
    WalletClientReportConfigurationFilter,
)
from wallet.pytests.factories import WalletClientReportConfigurationFactory
from wallet.services.wallet_client_reporting_constants import (
    WalletReportConfigFilterType,
)


@pytest.fixture(scope="function")
def wallet_client_configuration_view():
    return WalletClientReportConfigurationView(
        WalletClientReportConfiguration, session=db.session
    )


class TestWalletClientReportConfigurationView:
    @pytest.mark.parametrize(
        argnames="expense_type_candidates,country_candidates,existing_expense_types,expense_type_equal,existing_countries,country_equal,expected_result",
        argvalues=[
            ({"FERTILITY"}, set(), {"FERTILITY"}, True, {"US"}, True, False),
            ({"FERTILITY"}, {"US"}, set(), True, {"CA"}, True, True),
            ({"FERTILITY"}, set(), set(), True, {"US"}, True, False),
            (set(), set(), {"FERTILITY"}, True, {"US"}, True, False),
            ({"FERTILITY"}, {"US"}, {"EGG_FREEZING"}, True, {"US"}, True, True),
            ({"FERTILITY"}, set(), {"EGG_FREEZING"}, True, set(), True, True),
            ({"FERTILITY"}, {"US"}, {"FERTILITY"}, False, {"US"}, True, True),
            ({"FERTILITY"}, set(), {"FERTILITY"}, False, {}, True, True),
            (set(), {"US"}, set(), True, {"US"}, False, True),
        ],
    )
    def test_check_filters_mutual_exclusive(
        self,
        expense_type_candidates,
        country_candidates,
        existing_expense_types,
        expense_type_equal,
        existing_countries,
        country_equal,
        expected_result,
        wallet_client_configuration_view,
    ):
        filters = []
        for country in existing_countries:
            ft = WalletClientReportConfigurationFilter(
                filter_type=WalletReportConfigFilterType.COUNTRY,
                filter_value=country,
                equal=country_equal,
            )
            filters.append(ft)
        for expense_type in existing_expense_types:
            ft = WalletClientReportConfigurationFilter(
                filter_type=WalletReportConfigFilterType.PRIMARY_EXPENSE_TYPE,
                filter_value=expense_type,
                equal=expense_type_equal,
            )
            filters.append(ft)
        config = WalletClientReportConfigurationFactory.create(filters=filters)
        with patch("admin.views.models.wallet.flash"):
            result = wallet_client_configuration_view._check_filters_mutual_exclusive(
                expense_type_candidates=expense_type_candidates,
                country_candidates=country_candidates,
                organization_id=config.organization_id,
                current_config_id=None,
            )
            assert result == expected_result
