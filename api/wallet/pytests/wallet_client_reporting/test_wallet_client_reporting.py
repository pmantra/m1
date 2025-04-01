import datetime
from io import StringIO
from unittest.mock import ANY, patch

import factory
import pytest

from eligibility.pytests import factories as e9y_factories
from eligibility.service import EnterpriseVerificationService, get_verification_service
from pytests.factories import EnterpriseUserFactory, OrganizationFactory
from pytests.freezegun import freeze_time
from wallet.models.constants import (
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    TaxationState,
    WalletReportConfigCadenceTypes,
    WalletReportConfigColumnTypes,
    WalletState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.reimbursement_wallet_report import WalletClientReports
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.pytests.factories import (
    ReimbursementOrganizationSettingsFactory,
    ReimbursementPlanFactory,
    ReimbursementRequestExchangeRatesFactory,
    ReimbursementRequestFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
    WalletClientReportConfigurationFactory,
    WalletClientReportConfigurationFilterFactory,
    WalletClientReportConfigurationReportColumnsFactory,
    WalletClientReportConfigurationReportTypesFactory,
    WalletClientReportsFactory,
)
from wallet.services import wallet_client_reporting as wcr
from wallet.services.wallet_client_reporting import (
    _collect_reimbursement_requests_for_report,
    _format_audit_rows,
    _format_report_details,
    _format_transaction_reporting_rows,
    _group_reimbursement_requests_into_row_entry,
    _ordered_columns,
    assign_reimbursements_to_report,
    download_client_report,
    download_client_report_audit,
    download_selected_client_reports,
    download_transactional_client_report,
    download_zipped_client_reports,
)
from wallet.services.wallet_client_reporting_constants import (
    DEFAULT_COLUMNS,
    WalletReportConfigFilterType,
)
from wallet.tasks.wallet_client_reports import (
    _get_biweekly_report_configs,
    _get_monthly_report_configs,
    _get_weekly_report_configs,
    generate_wallet_reports,
)


@pytest.fixture(scope="function")
def organization():
    organization = OrganizationFactory.create()
    with freeze_time("2024-01-01"):
        org_setting = ReimbursementOrganizationSettingsFactory.create(
            organization_id=organization.id, started_at=datetime.datetime.utcnow()
        )
    organization.reimbursement_organization_settings = [org_setting]
    return organization


@pytest.fixture(scope="function")
def wallet_client_report_configuration(organization):
    configuration = WalletClientReportConfigurationFactory.create(
        organization=organization
    )
    for t in WalletReportConfigColumnTypes:
        if t.name in DEFAULT_COLUMNS:
            continue

        report_type = WalletClientReportConfigurationReportTypesFactory.create(
            column_type=t
        )
        WalletClientReportConfigurationReportColumnsFactory.create(
            wallet_client_report_configuration_id=configuration.id,
            wallet_client_report_configuration_report_type_id=report_type.id,
        )
    return configuration


@pytest.fixture(scope="function")
def reimbursement_wallets(organization):
    users = [EnterpriseUserFactory.create() for _ in range(4)]
    wallets = [
        ReimbursementWalletFactory.create(
            state=WalletState.QUALIFIED,
            reimbursement_organization_settings=organization.reimbursement_organization_settings[
                0
            ],
        )
        for _ in users
    ]
    for user, wallet in zip(users, wallets):
        ReimbursementWalletUsersFactory.create(
            user_id=user.id,
            reimbursement_wallet_id=wallet.id,
            status=WalletUserStatus.ACTIVE,
            type=WalletUserType.EMPLOYEE,
        )
    return wallets


@pytest.fixture(scope="function")
def reimbursement_requests(reimbursement_wallets):
    wallet_1, wallet_2, wallet_3, wallet_4 = reimbursement_wallets
    today = datetime.date.today()

    ReimbursementPlanFactory.create_batch(
        size=4,
        start_date=today.replace(month=1, day=1),
        end_date=factory.Iterator(
            [
                today.replace(month=12, day=31),
                today.replace(month=12, day=31),
                today.replace(year=2099, month=12, day=31),
                today.replace(year=2099, month=12, day=31),
            ]
        ),
        category=factory.Iterator(
            [
                _get_category(wallet_1),
                _get_category(wallet_2),
                _get_category(wallet_3),
                _get_category(wallet_4),
            ]
        ),
    )
    with freeze_time("2024-01-01"):
        reimbursement_requests = ReimbursementRequestFactory.create_batch(
            size=4,
            wallet=factory.Iterator([wallet_1, wallet_2, wallet_3, wallet_4]),
            category=factory.Iterator(
                [
                    _get_category(wallet_1),
                    _get_category(wallet_2),
                    _get_category(wallet_3),
                    _get_category(wallet_4),
                ]
            ),
            amount=factory.Iterator([123, 456, 789, 1000]),
            state=ReimbursementRequestState.APPROVED,
            service_start_date=datetime.date.today(),
        )
    return reimbursement_requests


@pytest.fixture(scope="function")
def wallet_client_report(
    wallet_client_report_configuration, organization, reimbursement_requests
):
    return WalletClientReportsFactory.create(
        organization=organization,
        configuration_id=wallet_client_report_configuration.id,
        reimbursement_requests=reimbursement_requests,
        start_date=datetime.datetime(year=2024, month=1, day=1),
        end_date=datetime.datetime(year=2024, month=2, day=1),
    )


def _get_category(category_wallet):
    return category_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ].reimbursement_request_category


class TestWalletReporting:
    def test_ordered_columns(self, wallet_client_report):

        assert _ordered_columns(wallet_client_report) == [
            "EMPLOYEE_ID",
            "EMPLOYER_ASSIGNED_ID",
            "DATE_OF_BIRTH",
            "FIRST_NAME",
            "LAST_NAME",
            "PROGRAM",
            "VALUE_TO_APPROVE",
            "FX_RATE",
            "VALUE_TO_APPROVE_USD",
            "DEBIT_CARD_FUND_USAGE_USD",
            "TOTAL_FUNDS_FOR_TAX_HANDLING",
            "REIMBURSEMENT_TYPE",
            "COUNTRY",
            "DEBIT_CARD_FUND_AWAITING_SUBSTANTIATION",
            "PRIOR_PROGRAM_TO_DATE",
            "TOTAL_PROGRAM_TO_DATE",
            "TAXATION",
            "PAYROLL_DEPT",
            "LINE_OF_BUSINESS",
            "DIRECT_PAYMENT_FUND_USAGE",
            "EXPENSE_YEAR",
        ]

    @freeze_time("2024-01-01", tick=False)
    def test_format_report_details(self, wallet_client_report, organization):
        svc: EnterpriseVerificationService = get_verification_service()

        def mock_get_verifidation(user_id, organization_id):
            employee = svc.employees.get_by_user_id(user_id=user_id)[0]
            verification = e9y_factories.build_verification_from_oe(
                user_id=user_id, employee=employee
            )
            return verification

        with patch(
            "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
            side_effect=mock_get_verifidation,
        ):
            assert _format_report_details(wallet_client_report, organization) == [
                ["Maven Wallet - Report for reimbursement approval and payroll"],
                [""],
                [""],
                ["Organization:", organization.name],
                ["Date period start:", "2024-01-01"],
                ["Date period end:", "2024-02-01"],
                ["Date program start:", "2024-01-01"],
                [""],
                [""],
                [
                    "Employee ID",
                    "Employer Assigned ID",
                    "Date of Birth",
                    "First Name",
                    "Last Name",
                    "Program",
                    "Reimbursements to be approved",
                    "Fx Rate",
                    "Reimbursements to be approved (Benefit Currency)",
                    "Debit card fund usage (Benefit Currency)",
                    "Total funds for tax handling",
                    "Reimbursement Type",
                    "Country",
                    "Debit card funds awaiting substantiation",
                    "Prior Program to-date (Benefit Currency)",
                    "Total Program to-date (Benefit Currency)",
                    "Taxation",
                    "Payroll Dept",
                    "Line of Business",
                    "Direct Payment Fund Usage",
                    "Expense Year",
                ],
                [
                    ANY,
                    None,
                    ANY,
                    ANY,
                    ANY,
                    "",
                    "1.23",
                    1.0,
                    "$1.23",
                    "$0.00",
                    "$1.23",
                    "DIRECT_DEPOSIT",
                    None,
                    "$0.00",
                    "$0.00",
                    "$1.23",
                    None,
                    None,
                    "",
                    "$0.00",
                    "2024",
                ],
                [
                    ANY,
                    None,
                    ANY,
                    ANY,
                    ANY,
                    "",
                    "4.56",
                    1.0,
                    "$4.56",
                    "$0.00",
                    "$4.56",
                    "DIRECT_DEPOSIT",
                    None,
                    "$0.00",
                    "$0.00",
                    "$4.56",
                    None,
                    None,
                    "",
                    "$0.00",
                    "2024",
                ],
                [
                    ANY,
                    None,
                    ANY,
                    ANY,
                    ANY,
                    "",
                    "7.89",
                    1.0,
                    "$7.89",
                    "$0.00",
                    "$7.89",
                    "DIRECT_DEPOSIT",
                    None,
                    "$0.00",
                    "$0.00",
                    "$7.89",
                    None,
                    None,
                    "",
                    "$0.00",
                    "2024",
                ],
                [
                    ANY,
                    None,
                    ANY,
                    ANY,
                    ANY,
                    "",
                    "10.00",
                    1.0,
                    "$10.00",
                    "$0.00",
                    "$10.00",
                    "DIRECT_DEPOSIT",
                    None,
                    "$0.00",
                    "$0.00",
                    "$10.00",
                    None,
                    None,
                    "",
                    "$0.00",
                    "2024",
                ],
                [
                    "Totals",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "$23.68",
                    "$0.00",
                    "",
                    "",
                    "",
                    "$0.00",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                ],
                [""],
                ["", "", "Total to be approved:", "$23.68"],
                ["", "", "Total unsubstantiated debit card funds:", "$0.00"],
                [""],
                [""],
                [
                    "Employer approval requested within 3 business days upon receipt of report"
                ],
                [
                    "This is based on Client plan design and is interchangeable with qualified, non-qualified associated with 213(d) and IRS adoption assistance programs."
                ],
                [""],
            ]

    def test__collect_reimbursement_requests_for_report(
        self,
        reimbursement_wallets,
        reimbursement_requests,
        organization,
        wallet_client_report_configuration,
    ):
        id_list = _collect_reimbursement_requests_for_report(
            organization.id, wallet_client_report_configuration.id
        )
        assert len(id_list) == 4

    def test__collect_reimbursement_requests_for_report_with_country_filter(
        self,
        reimbursement_wallets,
        reimbursement_requests,
        organization,
        wallet_client_report_configuration,
    ):
        WalletClientReportConfigurationFilterFactory.create(
            configuration_id=wallet_client_report_configuration.id,
            filter_type=WalletReportConfigFilterType.COUNTRY,
            filter_value="US",
        )
        wallet_user = ReimbursementWalletUsers.query.filter(
            ReimbursementWalletUsers.reimbursement_wallet_id
            == reimbursement_wallets[0].id
        ).one()
        wallet_user.member.member_profile.country_code = "US"
        id_list = _collect_reimbursement_requests_for_report(
            organization.id, wallet_client_report_configuration.id
        )
        assert len(id_list) == 1

    def test__collect_reimbursement_requests_for_report_with_primary_expense_type_filter(
        self,
        reimbursement_wallets,
        reimbursement_requests,
        organization,
        wallet_client_report_configuration,
    ):
        WalletClientReportConfigurationFilterFactory.create(
            configuration_id=wallet_client_report_configuration.id,
            filter_type=WalletReportConfigFilterType.PRIMARY_EXPENSE_TYPE,
            filter_value="FERTILITY",
        )
        reimbursement_requests[
            0
        ].expense_type = ReimbursementRequestExpenseTypes.FERTILITY
        id_list = _collect_reimbursement_requests_for_report(
            organization.id, wallet_client_report_configuration.id
        )
        assert len(id_list) == 1

    def test__collect_reimbursement_requests_for_report_with_primary_expense_type_filter_fallback(
        self,
        reimbursement_wallets,
        reimbursement_requests,
        organization,
        wallet_client_report_configuration,
    ):
        WalletClientReportConfigurationFilterFactory.create(
            configuration_id=wallet_client_report_configuration.id,
            filter_type=WalletReportConfigFilterType.PRIMARY_EXPENSE_TYPE,
            filter_value="FERTILITY",
        )
        reimbursement_requests[0].expense_type = None
        reimbursement_wallets[
            0
        ].primary_expense_type = ReimbursementRequestExpenseTypes.FERTILITY
        id_list = _collect_reimbursement_requests_for_report(
            organization.id, wallet_client_report_configuration.id
        )
        assert len(id_list) == 1

    def test__collect_reimbursement_requests_for_report_with_primary_expense_type_filter_both_rr_and_wallet(
        self,
        reimbursement_wallets,
        reimbursement_requests,
        organization,
        wallet_client_report_configuration,
    ):
        WalletClientReportConfigurationFilterFactory.create(
            configuration_id=wallet_client_report_configuration.id,
            filter_type=WalletReportConfigFilterType.PRIMARY_EXPENSE_TYPE,
            filter_value="FERTILITY",
        )
        reimbursement_requests[
            0
        ].expense_type = ReimbursementRequestExpenseTypes.PRESERVATION
        reimbursement_wallets[
            0
        ].primary_expense_type = ReimbursementRequestExpenseTypes.FERTILITY
        id_list = _collect_reimbursement_requests_for_report(
            organization.id, wallet_client_report_configuration.id
        )
        # Should not filter into the results, only fallback to wallet primary expense type if RR expense type is None
        assert len(id_list) == 0

    def test_exchange_rate_use_submission_year(
        self, reimbursement_wallets, reimbursement_requests
    ):
        # Given
        submission_year = 2025
        for reimbursement in reimbursement_requests:
            reimbursement.created_at = datetime.datetime(
                year=submission_year, month=1, day=1
            )

        wallet = reimbursement_wallets[0]
        target_exchange_rate_2024 = 123.45
        ReimbursementRequestExchangeRatesFactory(
            exchange_rate=target_exchange_rate_2024,
            trading_date=datetime.date(
                reimbursement_requests[0].service_start_date.year, 1, 1
            ),
        )
        target_exchange_rate_2025 = 200.00
        ReimbursementRequestExchangeRatesFactory(
            exchange_rate=target_exchange_rate_2025,
            trading_date=datetime.date(submission_year, 1, 1),
        )
        wallet.member.member_profile.country_code = "JP"
        reimbursements = [wallet.reimbursement_requests[0]]

        exchange_rate = wcr._fx_rate(reimbursements)
        assert exchange_rate == target_exchange_rate_2025

        formatted_exchange_rate = wcr._fx_rate_formatted(reimbursements)
        assert formatted_exchange_rate == 1.0 / target_exchange_rate_2025

        local_value = wcr._local_currency_value_to_approve(reimbursements)
        assert local_value == "246.00"

    def test_exchange_rate_use_submission_year_submitted_pre_2025(
        self, reimbursement_wallets, reimbursement_requests
    ):
        # Given
        wallet = reimbursement_wallets[0]
        target_exchange_rate_2024 = 123.45
        ReimbursementRequestExchangeRatesFactory(
            exchange_rate=target_exchange_rate_2024,
            trading_date=datetime.date(
                reimbursement_requests[0].service_start_date.year, 1, 1
            ),
        )
        target_exchange_rate_2025 = 200.00
        ReimbursementRequestExchangeRatesFactory(
            exchange_rate=target_exchange_rate_2025,
            trading_date=datetime.date(2025, 1, 1),
        )
        wallet.member.member_profile.country_code = "JP"
        reimbursements = [wallet.reimbursement_requests[0]]

        exchange_rate = wcr._fx_rate(reimbursements)
        assert exchange_rate == target_exchange_rate_2024

        formatted_exchange_rate = wcr._fx_rate_formatted(reimbursements)
        assert formatted_exchange_rate == 1.0 / target_exchange_rate_2024

        local_value = wcr._local_currency_value_to_approve(reimbursements)
        assert local_value == "151.84"

    def test_assign_reimbursements_to_report(
        self,
        organization,
        wallet_client_report_configuration,
        reimbursement_requests,
    ):
        report = WalletClientReportsFactory.create(
            organization=organization,
            configuration_id=wallet_client_report_configuration.id,
        )
        assert (
            assign_reimbursements_to_report(
                organization_id=organization.id,
                new_report_id=report.id,
                configuration_id=wallet_client_report_configuration.id,
            )
            == 4
        )

    def test_format_audit_rows_full_report(self, reimbursement_requests, organization):
        assert _format_audit_rows(reimbursement_requests) == [
            {
                "Organization Name": organization.name,
                "Organization ID": organization.id,
                "Amount": 1.23,
                "Reimbursement Method": "DIRECT_DEPOSIT",
                "Alegeus ID": None,
                "Organization Employee First Name": ANY,
                "Organization Employee Last Name": ANY,
                "Service Start Date": ANY,
                "Reimbursement ID": ANY,
                "Transaction Type": "MANUAL",
                "Wallet ID": ANY,
                "Client Employee ID": ANY,
                "Created Date": ANY,
                "Last Census File Before Deleted": "",
                "State": "APPROVED",
                "Taxation Status": None,
                "Program": "",
                "Country": None,
            },
            {
                "Organization Name": organization.name,
                "Organization ID": organization.id,
                "Amount": 4.56,
                "Reimbursement Method": "DIRECT_DEPOSIT",
                "Alegeus ID": None,
                "Organization Employee First Name": ANY,
                "Organization Employee Last Name": ANY,
                "Service Start Date": ANY,
                "Reimbursement ID": ANY,
                "Transaction Type": "MANUAL",
                "Wallet ID": ANY,
                "Client Employee ID": ANY,
                "Created Date": ANY,
                "Last Census File Before Deleted": "",
                "State": "APPROVED",
                "Taxation Status": None,
                "Program": "",
                "Country": None,
            },
            {
                "Organization Name": organization.name,
                "Organization ID": organization.id,
                "Amount": 7.89,
                "Reimbursement Method": "DIRECT_DEPOSIT",
                "Alegeus ID": None,
                "Organization Employee First Name": ANY,
                "Organization Employee Last Name": ANY,
                "Service Start Date": ANY,
                "Reimbursement ID": ANY,
                "Transaction Type": "MANUAL",
                "Wallet ID": ANY,
                "Client Employee ID": ANY,
                "Created Date": ANY,
                "Last Census File Before Deleted": "",
                "State": "APPROVED",
                "Taxation Status": None,
                "Program": "",
                "Country": None,
            },
            {
                "Organization Name": organization.name,
                "Organization ID": organization.id,
                "Amount": 10.0,
                "Reimbursement Method": "DIRECT_DEPOSIT",
                "Alegeus ID": None,
                "Organization Employee First Name": ANY,
                "Organization Employee Last Name": ANY,
                "Service Start Date": ANY,
                "Reimbursement ID": ANY,
                "Transaction Type": "MANUAL",
                "Wallet ID": ANY,
                "Client Employee ID": ANY,
                "Created Date": ANY,
                "Last Census File Before Deleted": "",
                "State": "APPROVED",
                "Taxation Status": None,
                "Program": "",
                "Country": None,
            },
        ]

    def test_format_audit_rows_half_report(self, reimbursement_requests, organization):
        assert _format_audit_rows(reimbursement_requests, full_report=False) == [
            {
                "Organization Name": organization.name,
                "Organization ID": organization.id,
                "Amount": 1.23,
                "Reimbursement Method": "DIRECT_DEPOSIT",
                "Alegeus ID": None,
                "Organization Employee First Name": ANY,
                "Organization Employee Last Name": ANY,
                "Service Start Date": ANY,
            },
            {
                "Organization Name": organization.name,
                "Organization ID": organization.id,
                "Amount": 4.56,
                "Reimbursement Method": "DIRECT_DEPOSIT",
                "Alegeus ID": None,
                "Organization Employee First Name": ANY,
                "Organization Employee Last Name": ANY,
                "Service Start Date": ANY,
            },
            {
                "Organization Name": organization.name,
                "Organization ID": organization.id,
                "Amount": 7.89,
                "Reimbursement Method": "DIRECT_DEPOSIT",
                "Alegeus ID": None,
                "Organization Employee First Name": ANY,
                "Organization Employee Last Name": ANY,
                "Service Start Date": ANY,
            },
            {
                "Organization Name": organization.name,
                "Organization ID": organization.id,
                "Amount": 10.0,
                "Reimbursement Method": "DIRECT_DEPOSIT",
                "Alegeus ID": None,
                "Organization Employee First Name": ANY,
                "Organization Employee Last Name": ANY,
                "Service Start Date": ANY,
            },
        ]

    def test_format_transaction_reporting_rows(self, reimbursement_requests):
        assert _format_transaction_reporting_rows(
            reimbursement_requests, "EMPLOYEE_ID"
        ) == [
            {
                "Employee ID": ANY,
                "First Name": ANY,
                "Last Name": ANY,
                "Date of Transaction": "01/01/2024",
                "Transaction Amount": "123.00",
            },
            {
                "Employee ID": ANY,
                "First Name": ANY,
                "Last Name": ANY,
                "Date of Transaction": "01/01/2024",
                "Transaction Amount": "456.00",
            },
            {
                "Employee ID": ANY,
                "First Name": ANY,
                "Last Name": ANY,
                "Date of Transaction": "01/01/2024",
                "Transaction Amount": "789.00",
            },
            {
                "Employee ID": ANY,
                "First Name": ANY,
                "Last Name": ANY,
                "Date of Transaction": "01/01/2024",
                "Transaction Amount": "1,000.00",
            },
        ]

    def test_download_client_report(self, wallet_client_report):
        with patch(
            "wallet.services.wallet_client_reporting._format_report_details",
        ) as format_report_details:
            download_client_report(wallet_client_report.id)
            format_report_details.assert_called_once_with(
                wallet_client_report=wallet_client_report,
                organization=wallet_client_report.organization,
            )

    def test_download_zipped_client_reports(self, wallet_client_report):
        with patch(
            "wallet.services.wallet_client_reporting.download_client_report",
            return_value=StringIO(""),
        ) as download_client_report:
            download_zipped_client_reports(
                [wallet_client_report.id, wallet_client_report.id]
            )
            download_client_report.assert_called_with(wallet_client_report.id)

    def test_download_client_report_audit(self, wallet_client_report):
        with patch(
            "wallet.services.wallet_client_reporting._format_audit_rows",
        ) as format_audit_rows:
            download_client_report_audit(wallet_client_report.id)
            format_audit_rows.assert_called_once_with(
                reimbursement_requests=wallet_client_report.reimbursement_requests,
                full_report=True,
            )

    def test_download_transactional_client_report(self, wallet_client_report):
        with patch(
            "wallet.services.wallet_client_reporting._format_transaction_reporting_rows",
        ) as format_transaction_reporting_rows:
            download_transactional_client_report(wallet_client_report.id)
            format_transaction_reporting_rows.assert_called_once_with(
                reimbursement_requests=wallet_client_report.reimbursement_requests,
                employee_id_column="EMPLOYEE_ID",
            )

    @freeze_time("2024-01-01", tick=False)
    def test_download_selected_client_reports(
        self, wallet_client_report_configuration, organization, reimbursement_requests
    ):
        report_1 = WalletClientReportsFactory.create(
            organization=organization,
            configuration_id=wallet_client_report_configuration.id,
            reimbursement_requests=reimbursement_requests[:2],
        )
        report_2 = WalletClientReportsFactory.create(
            organization=organization,
            configuration_id=wallet_client_report_configuration.id,
            reimbursement_requests=reimbursement_requests[2:],
        )
        file, org_name = download_selected_client_reports([report_1.id, report_2.id])
        assert file.getvalue().split("\r\n") == [
            "Maven Wallet - Report for reimbursement approval and payroll",
            '""',
            '""',
            ANY,
            "Date period start:,2024-01-01",
            "Date period end:,2024-01-01",
            "Date program start:,2024-01-01",
            '""',
            '""',
            "Employer Assigned ID,Employer Assigned ID,First Name,Last Name,Fx Rate,Total "
            "Program to-date (Benefit Currency),Country,Taxation",
            ANY,
            ANY,
            ANY,
            ANY,
            "Totals,,,,,,,",
            '""',
            ",,Total to be approved:,$23.68",
            '""',
            '""',
            "Employer approval requested within 3 business days upon receipt of report",
            '"This is based on Client plan design and is interchangeable with qualified, '
            'non-qualified associated with 213(d) and IRS adoption assistance programs."',
            '""',
            "",
        ]
        assert org_name == organization.name.lower()

    @freeze_time("2024-01-01", tick=False)
    def test_job_generate_client_reports(self, organization, reimbursement_requests):
        configuration = WalletClientReportConfigurationFactory.create(
            organization=organization,
            cadence=WalletReportConfigCadenceTypes.MONTHLY,
            day_of_week=1,
        )
        # Previous report to get the correct start date for the new report
        WalletClientReportsFactory.create(
            organization=organization,
            configuration_id=configuration.id,
            start_date=datetime.datetime(year=2023, day=1, month=11),
            end_date=datetime.datetime(year=2023, day=30, month=11),
            client_submission_date=datetime.datetime(year=2023, day=1, month=12),
        )

        generate_wallet_reports(dry_run=False)

        new_report = (
            WalletClientReports.query.filter(
                WalletClientReports.organization_id == organization.id
            )
            .order_by(WalletClientReports.end_date.desc())
            .first()
        )
        assert new_report.end_date.strftime("%Y-%m-%d") == "2023-12-31"
        assert new_report.start_date.strftime("%Y-%m-%d") == "2023-12-01"
        assert new_report.client_submission_date.strftime("%Y-%m-%d") == "2024-01-01"
        assert len(new_report.reimbursement_requests) == 4

    @freeze_time("2024-01-01", tick=False)
    def test_job_generate_client_reports_skips_if_empty(self, organization):
        WalletClientReportConfigurationFactory.create(
            organization=organization,
            cadence=WalletReportConfigCadenceTypes.MONTHLY,
            day_of_week=1,
        )

        generate_wallet_reports(dry_run=False)

        new_report = WalletClientReports.query.filter(
            WalletClientReports.organization_id == organization.id
        ).first()
        assert new_report == None

    @freeze_time("2024-01-01", tick=False)
    def test_job_generate_client_reports_weekly(
        self,
        organization,
    ):
        # 2024-01-01 is a monday
        WalletClientReportConfigurationFactory.create(
            organization=organization,
            cadence=WalletReportConfigCadenceTypes.WEEKLY,
            day_of_week=1,
        )

        today = datetime.datetime.today()
        configs = _get_weekly_report_configs(today)

        assert len(configs) == 1
        assert configs[0].day_of_week == 1

    @freeze_time("2024-01-08", tick=False)
    def test_job_generate_client_reports_biweekly(
        self,
        organization,
    ):
        # 2024-01-01 is a monday
        WalletClientReportConfigurationFactory.create(
            organization=organization,
            cadence=WalletReportConfigCadenceTypes.BIWEEKLY,
            day_of_week=8,
        )

        today = datetime.datetime.today()
        configs = _get_biweekly_report_configs(today)

        assert len(configs) == 1
        assert configs[0].day_of_week == 8

    @freeze_time("2024-02-29", tick=False)
    def test_job_generate_client_reports_monthly_last_day(
        self,
        organization,
    ):
        WalletClientReportConfigurationFactory.create(
            organization=organization,
            cadence=WalletReportConfigCadenceTypes.MONTHLY,
            day_of_week=31,
        )

        today = datetime.datetime.today()
        configs = _get_monthly_report_configs(today)

        assert len(configs) == 1
        assert configs[0].day_of_week == 31

    def test_group_reimbursement_requests_into_row_entry_pre_use_submission_year(
        self, reimbursement_requests
    ):
        """Test that if the submission year is >=2025, the key for submission year is included."""
        # Given
        submission_year = 2025
        for reimbursement in reimbursement_requests:
            reimbursement.created_at = datetime.datetime(
                year=submission_year, month=1, day=1
            )

        # one group should have taxation_status None, one group should have taxation_status TAXABLE
        reimbursement_requests[0].taxation_status = TaxationState.TAXABLE
        reimbursement_requests[1].reimbursement_wallet_id = reimbursement_requests[
            0
        ].reimbursement_wallet_id
        grouped_requests = _group_reimbursement_requests_into_row_entry(
            reimbursement_requests
        )
        assert len(grouped_requests) == 4
        wallet_id = reimbursement_requests[0].reimbursement_wallet_id
        service_year = reimbursement_requests[0].service_start_date.year
        assert list(grouped_requests.keys())[0] == (
            wallet_id,
            service_year,
            submission_year,
            TaxationState.TAXABLE.name,
        )
        assert list(grouped_requests.keys())[1] == (
            wallet_id,
            service_year,
            submission_year,
            None,
        )
