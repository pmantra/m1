import csv
import datetime
from collections import defaultdict
from decimal import Decimal
from io import BytesIO, StringIO
from typing import Dict, List, Optional, Tuple
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import extract, insert

from authn.models.user import User
from eligibility.e9y import EligibilityVerification
from eligibility.service import EnterpriseVerificationService, get_verification_service
from models.base import db
from models.enterprise import Organization
from utils.log import logger
from utils.payments import convert_cents_to_dollars
from wallet.models.constants import (
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    ReimbursementRequestType,
    TaxationState,
    WalletReportConfigColumnTypes,
)
from wallet.models.reimbursement import (
    ReimbursementRequest,
    ReimbursementRequestExchangeRates,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import CountryCurrencyCode, ReimbursementWallet
from wallet.models.reimbursement_wallet_report import (
    WalletClientReportConfiguration,
    WalletClientReportConfigurationFilter,
    WalletClientReportReimbursements,
    WalletClientReports,
)
from wallet.services.wallet_client_reporting_constants import (
    AUDIT_COLUMN_NAMES,
    DEFAULT_COLUMNS,
    ELIGIBILITY_SERVICE_COLS,
    NEW_REPORT_QUERY_REIMBURSEMENT_STATES,
    REIMBURSEMENT_AUDIT_REPORT_COLUMN_NAMES,
    REPORT_REIMBURSEMENT_STATES,
    TRANSACTIONAL_REPORT_COLUMN_NAMES,
    UNSUBSTANTIATED_DEBIT_COLS_OMIT,
    UNSUBSTANTIATED_DEBIT_REIMBURSEMENT_STATES,
    WALLET_REPORT_COLUMN_NAMES,
    YTD_REPORT_REIMBURSEMENT_STATES,
    AuditColumns,
    TransactionalReportColumns,
    WalletReportConfigFilterCountry,
    WalletReportConfigFilterType,
)

log = logger(__name__)

USE_SUBMISSION_DATE_FOR_FX_RATE_ON_AND_AFTER_YEAR = 2025


def download_client_report(wallet_client_report_id: int) -> StringIO:
    """
    This is the main usage of wallet reporting, it will generate a detailed csv report
    for an organization client, which includes all manual approved or refunded manual or debit card
    reimbursement requests for filtered employees.
    """
    wallet_client_report = WalletClientReports.query.get(wallet_client_report_id)
    organization = wallet_client_report.organization

    report_file = StringIO()
    rows = _format_report_details(
        wallet_client_report=wallet_client_report, organization=organization
    )
    # write to file
    report_writer = csv.writer(report_file)
    report_writer.writerows(rows)
    report_file.seek(0)
    return report_file


def download_zipped_client_reports(wallet_client_report_ids: List[int]) -> BytesIO:
    """
    Zipped version of download_client_report
    """
    zipped_reports = BytesIO()
    with ZipFile(zipped_reports, mode="w", compression=ZIP_DEFLATED) as zf:
        for report_id in wallet_client_report_ids:
            report = WalletClientReports.query.get(report_id)
            report_file = download_client_report(report_id)
            if report.client_submission_date:
                report_date = report.client_submission_date
            else:
                report_date = report.end_date
            date = report_date.strftime("%Y%m%d")
            org_name = report.organization.name.capitalize()
            filename = f"{org_name}_Wallet_Report_{date}.csv"
            zf.writestr(filename, report_file.getvalue())
    return zipped_reports


def download_client_report_audit(wallet_client_report_id: int) -> StringIO:
    """
    This will query for all manual reimbursement request within a wallet client report
    and generate a full csv report to download.
    """
    wallet_client_report = WalletClientReports.query.get(wallet_client_report_id)
    reimbursement_requests = wallet_client_report.reimbursement_requests
    audit_file = StringIO()
    report_writer = csv.DictWriter(audit_file, fieldnames=AUDIT_COLUMN_NAMES.values())
    report_writer.writeheader()
    report_writer.writerows(
        _format_audit_rows(
            reimbursement_requests=reimbursement_requests, full_report=True
        )
    )
    audit_file.seek(0)
    return audit_file


def download_transactional_client_report(wallet_client_report_id: int) -> StringIO:
    """
    Download report for transactions for debit/direct payment reconciliation
    """
    wallet_client_report = WalletClientReports.query.get(wallet_client_report_id)
    columns = _ordered_columns(wallet_client_report)
    if WalletReportConfigColumnTypes.EMPLOYER_ASSIGNED_ID in columns:
        employee_id_column = WalletReportConfigColumnTypes.EMPLOYER_ASSIGNED_ID.name
    else:
        employee_id_column = WalletReportConfigColumnTypes.EMPLOYEE_ID.name
    reimbursement_requests = wallet_client_report.reimbursement_requests
    audit_file = StringIO()
    report_writer = csv.DictWriter(
        audit_file, fieldnames=TRANSACTIONAL_REPORT_COLUMN_NAMES.values()
    )
    report_writer.writeheader()
    report_writer.writerows(
        _format_transaction_reporting_rows(
            reimbursement_requests=reimbursement_requests,
            employee_id_column=employee_id_column,
        )
    )
    audit_file.seek(0)
    return audit_file


def download_client_report_reimbursements_by_date(
    peakone_sent_date: datetime,  # type: ignore[valid-type] # Module "datetime" is not valid as a type
) -> StringIO:
    """
    Download client audit report for a specific peakone sent date,
    this will query all manual reimbursement request for a specific peakone sent date
    and generate a csv report to download.
    """
    wallet_client_report_reimbursements = WalletClientReportReimbursements.query.filter(
        WalletClientReportReimbursements.peakone_sent_date == peakone_sent_date
    ).all()
    reimbursement_requests = []
    for wallet_client_rr in wallet_client_report_reimbursements:
        rr = wallet_client_rr.reimbursement_request
        if rr and rr.reimbursement_type == ReimbursementRequestType.MANUAL:
            reimbursement_requests.append(wallet_client_rr.reimbursement_request)
    audit_file = StringIO()
    report_writer = csv.DictWriter(
        audit_file, fieldnames=REIMBURSEMENT_AUDIT_REPORT_COLUMN_NAMES.values()
    )
    report_writer.writeheader()
    report_writer.writerows(
        _format_audit_rows(
            reimbursement_requests=reimbursement_requests, full_report=False
        )
    )
    audit_file.seek(0)
    return audit_file


def create_wallet_report(
    config: WalletClientReportConfiguration,
    start_date: datetime.datetime.date,  # type: ignore[valid-type] # Function "datetime.datetime.date" is not valid as a type
    end_date: datetime.datetime.date,  # type: ignore[valid-type] # Function "datetime.datetime.date" is not valid as a type
    client_submission_date: Optional[datetime.datetime.date] = None,  # type: ignore[valid-type] # Function "datetime.datetime.date" is not valid as a type
    client_approval_date: Optional[datetime.datetime.date] = None,  # type: ignore[valid-type] # Function "datetime.datetime.date" is not valid as a type
    peakone_sent_date: Optional[datetime.datetime.date] = None,  # type: ignore[valid-type] # Function "datetime.datetime.date" is not valid as a type
    payroll_date: Optional[datetime.datetime.date] = None,  # type: ignore[valid-type] # Function "datetime.datetime.date" is not valid as a type
    notes: Optional[str] = None,
    skip_if_empty: bool = False,
) -> WalletClientReports:
    organization_id = config.organization_id
    report = WalletClientReports(
        organization_id=organization_id,
        configuration_id=config.id,
        start_date=start_date,
        end_date=end_date,
        client_submission_date=client_submission_date,
        client_approval_date=client_approval_date,
        peakone_sent_date=peakone_sent_date,
        payroll_date=payroll_date,
        notes=notes,
    )
    db.session.add(report)
    db.session.commit()
    num_requests = assign_reimbursements_to_report(
        organization_id, report.id, config.id
    )
    if skip_if_empty and num_requests == 0:
        db.session.delete(report)
    db.session.commit()
    return report


def assign_reimbursements_to_report(
    organization_id: int, new_report_id: int, configuration_id: int
) -> int:
    """
    This is used when creating a new wallet client report, it collects all qualified reimbursement
    requests and store them into wallet_client_report_reimbursements table.

    Return value is the number of reimbursements identified for adding to the new report.
    """
    reimbursement_ids = _collect_reimbursement_requests_for_report(
        organization_id=organization_id, configuration_id=configuration_id
    )

    if len(reimbursement_ids) == 0:
        log.error(
            "Wallet Client Report contains no reimbursement requests",
            organization_id=organization_id,
            new_report_id=new_report_id,
        )
        return 0

    log.info(
        "Creating associations for Wallet Client Report",
        organization_id=organization_id,
        new_report_id=new_report_id,
        num_assoc=len(reimbursement_ids),
    )
    db.session.execute(
        insert(WalletClientReportReimbursements),  # type: ignore[arg-type] # Argument 1 to "Insert" has incompatible type "Type[WalletClientReportReimbursements]"; expected "Union[str, Selectable]"
        [
            {
                "reimbursement_request_id": reimbursement_id,
                "wallet_client_report_id": new_report_id,
            }
            for reimbursement_id in reimbursement_ids
            if reimbursement_id is not None
        ],
    )

    log.info(
        "Creating associations for Wallet Client Report",
        organization_id=organization_id,
        new_report_id=new_report_id,
        num_assoc=len(reimbursement_ids),
    )
    return len(reimbursement_ids)


# TODO: Refactor to reuse more components with individual wallet reports
def download_selected_client_reports(
    wallet_client_report_ids: List[int],
) -> Tuple[StringIO, str]:
    """
    This will download multiple selected client reports into a single bundled reports,
    only client reports with same configuration settings can be bundled into a single report!
    """
    verification_svc = get_verification_service()
    # All client report show share the same configuration, so it's safe to use the first one's
    first_wallet_client_report = WalletClientReports.query.get(
        wallet_client_report_ids[0]
    )
    organization = first_wallet_client_report.organization
    report_config_columns = _ordered_columns(first_wallet_client_report)

    # Determine what employee id to use based on report config
    if WalletReportConfigColumnTypes.EMPLOYER_ASSIGNED_ID.name in report_config_columns:
        columns = [WalletReportConfigColumnTypes.EMPLOYER_ASSIGNED_ID.name]
    else:
        columns = [WalletReportConfigColumnTypes.EMPLOYEE_ID.name]

    columns.extend(
        [
            WalletReportConfigColumnTypes.EMPLOYER_ASSIGNED_ID.name,
            WalletReportConfigColumnTypes.FIRST_NAME.name,
            WalletReportConfigColumnTypes.LAST_NAME.name,
            WalletReportConfigColumnTypes.FX_RATE.name,
            WalletReportConfigColumnTypes.TOTAL_PROGRAM_TO_DATE.name,
            WalletReportConfigColumnTypes.COUNTRY.name,
            WalletReportConfigColumnTypes.TAXATION.name,
        ]
    )

    # Gather Reimbursements
    reimbursement_ids_query = (
        WalletClientReportReimbursements.query.with_entities(
            WalletClientReportReimbursements.reimbursement_request_id
        )
        .filter(
            WalletClientReportReimbursements.wallet_client_report_id.in_(
                wallet_client_report_ids
            )
        )
        .all()
    )
    reimbursement_ids = {res[0] for res in reimbursement_ids_query}
    reimbursements = [
        r
        for r in ReimbursementRequest.query.filter(
            ReimbursementRequest.id.in_(reimbursement_ids),
        )
        if r.state in YTD_REPORT_REIMBURSEMENT_STATES
    ]

    rows = [["Maven Wallet - Report for reimbursement approval and payroll"]]
    # Add padding
    rows.extend([[""], [""]])

    # Add org name, date start, date end, and program start date
    rows.append(["Organization:", organization.name])
    rows.append(["Date period start:", datetime.datetime.today().strftime("%Y-01-01")])
    rows.append(["Date period end:", datetime.datetime.today().strftime("%Y-%m-%d")])
    rows.append(
        [
            "Date program start:",
            organization.reimbursement_organization_settings[0].started_at.strftime(
                "%Y-%m-%d"
            ),
        ]
    )

    # Add padding
    rows.extend([[""], [""]])

    # Add column headers
    column_names = _column_names(columns)
    rows.append(column_names)

    grouped_requests = defaultdict(list)
    for r in reimbursements:
        key = r.reimbursement_wallet_id
        grouped_requests[key].append(r)

    total_reimbursement_amount = Decimal(0.0)
    # For each grouping of reimbursement requests, run the requests column calculations
    for requests in grouped_requests.values():
        row = []
        eligibility_verification = _get_verification_using_reimbursement_request(
            requests[0], verification_svc
        )
        for col in columns:
            func = WALLET_REPORT_COLUMN_FUNCTIONS[col]
            if col == WalletReportConfigColumnTypes.TOTAL_PROGRAM_TO_DATE.name:
                result = _total_ytd_amount(requests)
            elif col == WalletReportConfigColumnTypes.FX_RATE.name:
                result = _get_ytd_local_currency_rate(requests)
            elif col in ELIGIBILITY_SERVICE_COLS:
                result = func(eligibility_verification)
            else:
                result = func(requests)
            row.append(result)

            if col == WalletReportConfigColumnTypes.TOTAL_PROGRAM_TO_DATE.name:
                result_numeric = Decimal(result.replace("$", "").replace(",", ""))
                total_reimbursement_amount += result_numeric
        rows.append(row)

    total_reimbursement_amount_formatted = f"${total_reimbursement_amount:,.2f}"
    rows.extend(_totals_rows(columns, total_reimbursement_amount_formatted, "0", "0"))

    rows.extend([[""], [""]])

    # Add additional notes
    rows.append(
        ["Employer approval requested within 3 business days upon receipt of report"]
    )
    rows.append(
        [
            "This is based on Client plan design and is interchangeable with qualified, "
            "non-qualified associated with 213(d) and IRS adoption assistance programs."
        ]
    )
    rows.append([""])

    # Create File
    report_file = StringIO()
    report_writer = csv.writer(report_file)
    report_writer.writerows(rows)
    report_file.seek(0)
    # get org name for filename generation
    return report_file, organization.name.lower()


def _apply_filters_to_reimbursement_requests(
    reimbursement_requests: List[ReimbursementRequest],
    filters: List[WalletClientReportConfigurationFilter],
) -> List[ReimbursementRequest]:
    countries = set()
    primary_expense_types = set()

    valid_expense_types = {t for t in ReimbursementRequestExpenseTypes}
    valid_countries = {t.value for t in WalletReportConfigFilterCountry}

    for fts in filters:
        if fts.filter_type == WalletReportConfigFilterType.COUNTRY:
            value = fts.filter_value.upper()
            if fts.equal:
                countries.add(value)
            else:
                countries = countries.union(valid_countries - {value})
        elif fts.filter_type == WalletReportConfigFilterType.PRIMARY_EXPENSE_TYPE:
            value = ReimbursementRequestExpenseTypes(fts.filter_value.upper())
            if fts.equal:
                primary_expense_types.add(value)
            else:
                primary_expense_types = primary_expense_types.union(
                    valid_expense_types - {value}
                )
    qualified_reimbursement_requests = []
    for rr in reimbursement_requests:
        if primary_expense_types:
            if rr.expense_type and rr.expense_type not in primary_expense_types:
                continue
            if (
                rr.expense_type is None
                and rr.wallet.primary_expense_type not in primary_expense_types
            ):
                continue
        if countries:
            user = User.query.get(rr.employee_member_id)
            if "OTHERS" in countries:
                if (
                    not user.member_profile.country_code
                    or user.member_profile.country_code
                    in {country.value for country in WalletReportConfigFilterCountry}
                ):
                    continue
            else:
                if user.member_profile.country_code not in countries:
                    continue
        qualified_reimbursement_requests.append(rr)
    return qualified_reimbursement_requests


def _collect_reimbursement_requests_for_report(
    organization_id: int, configuration_id: int
) -> List[int]:
    """
    Collect all unreported reimbursement requests, this will make sure each reimbursement
    request can be at most included within one wallet client report.
    Each organization has multiple report configurations, and those report configurations
    are mutually exclusive, so that each reimbursement request in that organization can
    ONLY be included in one report.
    """
    filters = WalletClientReportConfiguration.query.get(configuration_id).filters
    query = (
        db.session.query(ReimbursementRequest)
        .join(
            ReimbursementRequest.wallet,
            ReimbursementWallet.reimbursement_organization_settings,
        )
        .join(
            WalletClientReportReimbursements,
            ReimbursementRequest.id
            == WalletClientReportReimbursements.reimbursement_request_id,
            isouter=True,
        )
        .filter(
            ReimbursementRequest.state.in_(NEW_REPORT_QUERY_REIMBURSEMENT_STATES),
            ReimbursementOrganizationSettings.organization_id == organization_id,
            # don't include reimbursement requests reported before
            WalletClientReportReimbursements.reimbursement_request_id.is_(None),
        )
    )
    reimbursement_requests = query.all()
    qualified_reimbursement_requests = _apply_filters_to_reimbursement_requests(
        reimbursement_requests=reimbursement_requests, filters=filters
    )
    return [rr.id for rr in qualified_reimbursement_requests]


def _format_report_details(
    wallet_client_report: WalletClientReports, organization: Organization
) -> List:
    verification_svc: EnterpriseVerificationService = get_verification_service()
    columns: List = _ordered_columns(wallet_client_report)
    rows = [["Maven Wallet - Report for reimbursement approval and payroll"]]
    # Add padding
    rows.extend([[""], [""]])

    # Add org name, date start, date end, and program start date
    rows.append(["Organization:", organization.name])
    rows.append(
        ["Date period start:", wallet_client_report.start_date.strftime("%Y-%m-%d")]
    )
    rows.append(
        ["Date period end:", wallet_client_report.end_date.strftime("%Y-%m-%d")]
    )
    rows.append(
        [
            "Date program start:",
            organization.reimbursement_organization_settings[0].started_at.strftime(
                "%Y-%m-%d"
            ),
        ]
    )

    # Add padding
    rows.extend([[""], [""]])

    # Add column headers
    column_names = _column_names(columns)
    rows.append(column_names)

    # Calculate reporting rows and totals
    (
        employee_rows,
        reimbursement_amount,
        debit_amount,
        unsubstantiated_debit_amount,
    ) = _format_employee_rows(
        wallet_client_report=wallet_client_report,
        columns=columns,
        verification_svc=verification_svc,
    )

    # Add employee rows
    rows.extend(employee_rows)

    # Add totals rows
    totals_rows = _totals_rows(
        columns=columns,
        reimbursement_amount=reimbursement_amount,
        debit_amount=debit_amount,
        unsubstantiated_debit_amount=unsubstantiated_debit_amount,
    )
    rows.extend(totals_rows)

    # Add padding
    rows.extend([[""], [""]])

    # Add additional notes
    rows.append(
        ["Employer approval requested within 3 business days upon receipt of report"]
    )
    rows.append(
        [
            "This is based on Client plan design and is interchangeable with qualified, "
            "non-qualified associated with 213(d) and IRS adoption assistance programs."
        ]
    )
    rows.append([""])
    return rows


def _ordered_columns(wallet_client_report: WalletClientReports) -> List:
    """
    returns wallet report configuration columns in the same order as WALLET_REPORT_COLUMN_NAMES dict
    AND adds the default employee columns
    """
    ordered_columns = []
    report_config = WalletClientReportConfiguration.query.get(
        wallet_client_report.configuration_id
    )
    columns = report_config.column_names()
    for col in WALLET_REPORT_COLUMN_NAMES.keys():
        if col in columns or col in DEFAULT_COLUMNS:
            ordered_columns.append(col)
    return ordered_columns


def _column_names(columns: List[str]) -> List[str]:
    return [WALLET_REPORT_COLUMN_NAMES[col] for col in columns]


def _format_employee_rows(
    wallet_client_report: WalletClientReports,
    columns: List,
    verification_svc: EnterpriseVerificationService,
) -> (List, str, str, str):  # type: ignore[syntax] # Syntax error in type annotation
    employee_rows = []

    # Only collect APPROVED and REFUNDED reimbursements
    reimbursement_requests: List[ReimbursementRequest] = [
        rr
        for rr in wallet_client_report.reimbursement_requests
        if rr.state in REPORT_REIMBURSEMENT_STATES
    ]
    total_reimbursement_amount = Decimal(0.0)
    total_debit_amount = Decimal(0.0)
    total_unsubstantiated_debit_amount = Decimal(0.0)

    # Each row is grouped by wallet_id
    grouped_requests = _group_reimbursement_requests_into_row_entry(
        reimbursement_requests
    )
    # For each grouping of reimbursement requests, run the requests column calculations
    for requests in grouped_requests.values():
        row = []
        # get verification for each row first
        eligibility_verification = _get_verification_using_reimbursement_request(
            requests[0], verification_svc
        )
        for col in columns:
            func = WALLET_REPORT_COLUMN_FUNCTIONS[col]
            if col in ELIGIBILITY_SERVICE_COLS:
                result = func(eligibility_verification)
            else:
                result = func(requests)
            row.append(result)

            # Update running totals
            if col == WalletReportConfigColumnTypes.VALUE_TO_APPROVE_USD.name:
                result_numeric = Decimal(result.replace("$", "").replace(",", ""))
                total_reimbursement_amount += result_numeric
            elif col == WalletReportConfigColumnTypes.DEBIT_CARD_FUND_USAGE_USD.name:
                result_numeric = Decimal(result.replace("$", "").replace(",", ""))
                total_debit_amount += result_numeric
            elif (
                col
                == WalletReportConfigColumnTypes.DEBIT_CARD_FUND_AWAITING_SUBSTANTIATION.name
            ):
                result_numeric = Decimal(result.replace("$", "").replace(",", ""))
                total_unsubstantiated_debit_amount += result_numeric

        employee_rows.append(row)

    # Lookup additional rows for unsubstantiated debit transactions and add rows to report + update unsubstantiated total
    (
        debit_rows,
        additional_unsubstantiated_debit_amount,
    ) = _get_unsubstantiated_debit_transactions_rows(
        wallet_client_report=wallet_client_report,
        existing_row_keys=grouped_requests.keys(),
        columns=columns,
        verification=verification_svc,
    )
    employee_rows.extend(debit_rows)
    total_unsubstantiated_debit_amount += additional_unsubstantiated_debit_amount

    # Add rows for any ineligible_expense reimbursements to report
    ineligible_expense_rows, ineligible_debit_total = _get_ineligible_expense_rows(
        wallet_client_report=wallet_client_report,
        columns=columns,
        verification=verification_svc,
    )
    employee_rows.extend(ineligible_expense_rows)
    total_debit_amount += ineligible_debit_total

    # Format values for totals
    total_reimbursement_amount_formatted = f"${total_reimbursement_amount:,.2f}"
    total_debit_amount_formatted = f"${total_debit_amount:,.2f}"
    total_unsubstantiated_debit_amount_formatted = (
        f"${total_unsubstantiated_debit_amount:,.2f}"
    )

    return (
        employee_rows,
        total_reimbursement_amount_formatted,
        total_debit_amount_formatted,
        total_unsubstantiated_debit_amount_formatted,
    )


def _group_reimbursement_requests_into_row_entry(
    reimbursement_requests: List[ReimbursementRequest],
) -> dict:
    # Group reimbursement requests by wallet_id, service year, and taxation status
    grouped_requests = defaultdict(list)
    for rr in reimbursement_requests:
        reimbursement_wallet_id = rr.reimbursement_wallet_id
        service_start_year = (
            rr.service_start_date.year
        )  # Extract the year from the date

        # If the reimbursement was submitted in 2025 onwards
        # We group these on a different row, as FX rate will be determined by submission year instead of service_start_year
        submission_year = (
            rr.created_at.year
            if rr.created_at.year >= USE_SUBMISSION_DATE_FOR_FX_RATE_ON_AND_AFTER_YEAR
            else None
        )

        taxation_status = None
        if rr.taxation_status:
            taxation_status = rr.taxation_status.name  # type: ignore[attr-defined] # "str" has no attribute "name"
        key = (
            reimbursement_wallet_id,
            service_start_year,
            submission_year,
            taxation_status,
        )
        grouped_requests[key].append(rr)
    return grouped_requests


def _get_unsubstantiated_debit_transactions_rows(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    wallet_client_report: WalletClientReports,
    existing_row_keys,
    columns: List,
    verification: EnterpriseVerificationService,
):
    # Collect the relevant reimbursement_requests for unsubstantiated debit card transactions
    organization_id = wallet_client_report.organization_id
    reimbursement_query = (
        ReimbursementRequest.query.filter(
            ReimbursementRequest.state.in_(UNSUBSTANTIATED_DEBIT_REIMBURSEMENT_STATES)
        )
        .filter(
            ReimbursementRequest.reimbursement_type
            == ReimbursementRequestType.DEBIT_CARD
        )
        .all()
    )
    reimbursement_requests = _apply_filters_to_reimbursement_requests(
        reimbursement_requests=reimbursement_query,
        filters=wallet_client_report.configuration.filters,
    )
    unsubstantiated_debit_reimbursements = []
    for reimbursement in reimbursement_requests:
        # check org match
        if (
            reimbursement.wallet.reimbursement_organization_settings.organization_id
            != organization_id
        ):
            continue

        # check if this wallet/category has already been reported in a previous row
        if reimbursement.reimbursement_wallet_id in existing_row_keys:
            continue

        unsubstantiated_debit_reimbursements.append(reimbursement)

    # Group requests by wallet/category
    grouped_requests = defaultdict(list)
    for r in unsubstantiated_debit_reimbursements:
        key = r.reimbursement_wallet_id
        grouped_requests[key].append(r)

    # format rows for CSV report
    unsubstantiated_debit_reimbursements_rows = []
    additional_unsubstantiated_debit_amount = 0.0

    for debit_reimbursements in grouped_requests.values():
        row = []
        for col in columns:
            # Skip rows not relevant to debit unsubstantiation, these are for approved reimbursements.
            # These columns would have populated in the earlier rows if applicable.
            if col in UNSUBSTANTIATED_DEBIT_COLS_OMIT:
                row.append(0)
            elif (
                col
                == WalletReportConfigColumnTypes.DEBIT_CARD_FUND_AWAITING_SUBSTANTIATION.name
            ):
                # Sum requests, update running total.
                # We don't reuse the existing column logic because it re-queries the reimbursement
                # requests we already have, instead we can just sum the grouped requests here.
                total_for_row = _sum_unsubstantiated_debit_reimbursements(
                    debit_reimbursements
                )
                row.append(f"${total_for_row:,.2f}")  # type: ignore[arg-type] # Argument 1 to "append" of "list" has incompatible type "str"; expected "int"
                additional_unsubstantiated_debit_amount += total_for_row
            else:
                eligibility_verification = (
                    _get_verification_using_reimbursement_request(
                        debit_reimbursements[0], verification
                    )
                )
                func = WALLET_REPORT_COLUMN_FUNCTIONS[col]
                if col in ELIGIBILITY_SERVICE_COLS:
                    result = func(eligibility_verification)
                else:
                    result = func(debit_reimbursements)
                row.append(result)
        unsubstantiated_debit_reimbursements_rows.append(row)
    return (
        unsubstantiated_debit_reimbursements_rows,
        Decimal(additional_unsubstantiated_debit_amount),
    )


def _get_ineligible_expense_rows(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    wallet_client_report: WalletClientReports,
    columns: List,
    verification: EnterpriseVerificationService,
):
    ineligible_expense_rows = []
    ineligible_total = 0.0
    reimbursements = [
        r
        for r in wallet_client_report.reimbursement_requests
        if r.state == ReimbursementRequestState.INELIGIBLE_EXPENSE
    ]
    if not reimbursements:
        return ineligible_expense_rows, Decimal(ineligible_total)

    # Each row is grouped by wallet_id
    grouped_requests = defaultdict(list)
    for r in reimbursements:
        key = r.reimbursement_wallet_id
        grouped_requests[key].append(r)

    # iterate through groupings for each column
    for ineligible_reimbursements in grouped_requests.values():
        row = []
        debit_fund_usage = sum(
            _handle_reimbursement_amount(r)
            for r in ineligible_reimbursements
            if r.reimbursement_type == ReimbursementRequestType.DEBIT_CARD
        )
        ineligible_total += debit_fund_usage
        for col in columns:
            if col == WalletReportConfigColumnTypes.TAXATION.name:
                row.append(TaxationState.TAXABLE.value)
            elif col == WalletReportConfigColumnTypes.DEBIT_CARD_FUND_USAGE_USD.name:
                row.append(f"${debit_fund_usage:,.2f}")
            elif col == WalletReportConfigColumnTypes.TOTAL_FUNDS_FOR_TAX_HANDLING.name:
                row.append(f"${debit_fund_usage:,.2f}")
            else:
                func = WALLET_REPORT_COLUMN_FUNCTIONS[col]
                if col in ELIGIBILITY_SERVICE_COLS:
                    eligibility_verification = (
                        _get_verification_using_reimbursement_request(
                            ineligible_reimbursements[0], verification
                        )
                    )
                    result = func(eligibility_verification)
                else:
                    result = func(ineligible_reimbursements)
                row.append(result)
        ineligible_expense_rows.append(row)
    return ineligible_expense_rows, Decimal(ineligible_total)


def _totals_rows(
    columns: List,
    reimbursement_amount: str,
    debit_amount: str,
    unsubstantiated_debit_amount: str,
) -> List[List[str]]:
    all_totals_rows = []

    # Format totals row
    totals_row = []
    for idx, col in enumerate(columns):
        if idx == 0:
            totals_row.append("Totals")
        elif col == WalletReportConfigColumnTypes.VALUE_TO_APPROVE_USD.name:
            totals_row.append(reimbursement_amount)
        elif col == WalletReportConfigColumnTypes.DEBIT_CARD_FUND_USAGE_USD.name:
            totals_row.append(debit_amount)
        elif (
            col
            == WalletReportConfigColumnTypes.DEBIT_CARD_FUND_AWAITING_SUBSTANTIATION.name
        ):
            totals_row.append(unsubstantiated_debit_amount)
        else:
            totals_row.append("")
    all_totals_rows.append(totals_row)

    # Add padding
    all_totals_rows.append([""])
    total = Decimal(reimbursement_amount.replace("$", "").replace(",", "")) + Decimal(
        debit_amount.replace("$", "").replace(",", "")
    )
    all_totals_rows.append(["", "", "Total to be approved:", f"${total:,.2f}"])
    if (
        WalletReportConfigColumnTypes.DEBIT_CARD_FUND_AWAITING_SUBSTANTIATION.name
        in columns
    ):
        all_totals_rows.append(
            [
                "",
                "",
                "Total unsubstantiated debit card funds:",
                unsubstantiated_debit_amount,
            ]
        )

    return all_totals_rows


def _format_audit_rows(
    reimbursement_requests: List[ReimbursementRequest], full_report: bool = True
) -> List[Dict]:
    audit_rows = []
    verification_svc = get_verification_service()
    for rr in reimbursement_requests:
        user_id = rr.employee_member_id
        user_profile = User.query.get(user_id)
        dict_row = _get_report_dict(rr, user_profile, verification_svc, full_report)
        audit_rows.append(dict_row)
    return audit_rows


def _get_report_dict(
    rr: ReimbursementRequest,
    user_profile: User,
    verification_svc: EnterpriseVerificationService,
    full_report: bool = True,
) -> dict:
    # get eligibility verification for the user
    eligibility_verification = _get_verification_using_reimbursement_request(
        rr, verification_svc
    )
    dict_row = {
        AUDIT_COLUMN_NAMES[
            AuditColumns.ORGANIZATION_NAME
        ]: rr.wallet.reimbursement_organization_settings.organization.name,
        AUDIT_COLUMN_NAMES[
            AuditColumns.ORGANIZATION_ID
        ]: rr.wallet.reimbursement_organization_settings.organization_id,
        AUDIT_COLUMN_NAMES[AuditColumns.AMOUNT]: convert_cents_to_dollars(
            rr.usd_reimbursement_amount
        ),
        AUDIT_COLUMN_NAMES[AuditColumns.REIMBURSEMENT_METHOD]: (
            rr.reimbursement_method and rr.reimbursement_method.name  # type: ignore[attr-defined] # "str" has no attribute "name"
        )
        or (
            rr.wallet.reimbursement_method and rr.wallet.reimbursement_method.name  # type: ignore[attr-defined] # "str" has no attribute "name"
        ),
        AUDIT_COLUMN_NAMES[AuditColumns.ALEGEUS_ID]: rr.wallet.alegeus_id,
        AUDIT_COLUMN_NAMES[AuditColumns.ORGANIZATION_EMPLOYEE_FIRST_NAME]: _first_name(
            eligibility_verification
        ),
        AUDIT_COLUMN_NAMES[AuditColumns.ORGANIZATION_EMPLOYEE_LAST_NAME]: _last_name(
            eligibility_verification
        ),
        AUDIT_COLUMN_NAMES[AuditColumns.SERVICE_START_DATE]: rr.service_start_date,
    }
    if full_report:
        dict_row[AUDIT_COLUMN_NAMES[AuditColumns.REIMBURSEMENT_ID]] = rr.id
        dict_row[AUDIT_COLUMN_NAMES[AuditColumns.TRANSACTION_TYPE]] = (
            rr.reimbursement_type and rr.reimbursement_type.name  # type: ignore[attr-defined] # "str" has no attribute "name"
        )
        dict_row[AUDIT_COLUMN_NAMES[AuditColumns.WALLET_ID]] = rr.wallet.id
        dict_row[AUDIT_COLUMN_NAMES[AuditColumns.CLIENT_EMPLOYEE_ID]] = _employee_id(
            eligibility_verification
        )
        dict_row[AUDIT_COLUMN_NAMES[AuditColumns.CREATED_DATE]] = rr.created_at
        dict_row[AUDIT_COLUMN_NAMES[AuditColumns.LAST_CENSUS_FILE_BEFORE_DELETED]] = ""
        dict_row[AUDIT_COLUMN_NAMES[AuditColumns.STATE]] = rr.state and rr.state.name  # type: ignore[attr-defined] # "str" has no attribute "name"
        dict_row[AUDIT_COLUMN_NAMES[AuditColumns.TAXATION_STATUS]] = (
            rr.taxation_status and rr.taxation_status.name  # type: ignore[attr-defined] # "str" has no attribute "name"
        ) or (
            rr.wallet.taxation_status and rr.wallet.taxation_status.name  # type: ignore[attr-defined] # "str" has no attribute "name"
        )
        dict_row[
            AUDIT_COLUMN_NAMES[AuditColumns.SERVICE_START_DATE]
        ] = rr.service_start_date
        dict_row[AUDIT_COLUMN_NAMES[AuditColumns.PROGRAM]] = (
            rr.wallet.primary_expense_type.name.capitalize()  # type: ignore[attr-defined] # "str" has no attribute "name"
            if rr.wallet.primary_expense_type is not None
            else ""
        )
        dict_row[AUDIT_COLUMN_NAMES[AuditColumns.COUNTRY]] = (
            user_profile.country
            and user_profile.country.alpha_3
            and rr.wallet.member.profile.country.alpha_3  # type: ignore[union-attr] # Item "None" of "Union[PractitionerProfile, MemberProfile, None]" has no attribute "country" #type: ignore[union-attr] # Item "None" of "Union[Country, None, Any]" has no attribute "alpha_3"
        )

    return dict_row


def _format_transaction_reporting_rows(
    reimbursement_requests: List[ReimbursementRequest], employee_id_column: str
) -> List[Dict]:
    transaction_rows = []
    verification_svc = get_verification_service()

    for rr in reimbursement_requests:
        dict_row = _transaction_report_dict(
            rr=rr,
            employee_id_column=employee_id_column,
            verification_svc=verification_svc,
        )
        transaction_rows.append(dict_row)
    return transaction_rows


def _transaction_report_dict(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    rr: ReimbursementRequest,
    employee_id_column: str,
    verification_svc: EnterpriseVerificationService,
):
    # get eligibility verification info for the user
    eligibility_verification = _get_verification_using_reimbursement_request(
        rr, verification_svc
    )
    if employee_id_column == WalletReportConfigColumnTypes.EMPLOYER_ASSIGNED_ID:
        employee_id = _employer_assigned_id(eligibility_verification)
    else:
        employee_id = _employee_id(eligibility_verification)

    if rr.reimbursement_type == ReimbursementRequestType.DEBIT_CARD:
        date_of_transaction = rr.transactions[0].date
    else:
        date_of_transaction = rr.service_end_date

    return {
        TRANSACTIONAL_REPORT_COLUMN_NAMES[
            TransactionalReportColumns.EMPLOYEE_ID
        ]: employee_id,
        TRANSACTIONAL_REPORT_COLUMN_NAMES[
            TransactionalReportColumns.FIRST_NAME
        ]: _first_name(eligibility_verification),
        TRANSACTIONAL_REPORT_COLUMN_NAMES[
            TransactionalReportColumns.LAST_NAME
        ]: _last_name(eligibility_verification),
        TRANSACTIONAL_REPORT_COLUMN_NAMES[
            TransactionalReportColumns.DATE_OF_TRANSACTION
        ]: date_of_transaction.strftime(  # type: ignore[union-attr] # Item "None" of "Optional[datetime]" has no attribute "strftime"
            "%m/%d/%Y"
        ),
        # TODO: is this correct? Currently it's in cents
        TRANSACTIONAL_REPORT_COLUMN_NAMES[
            TransactionalReportColumns.TRANSACTION_AMOUNT
        ]: f"{rr.amount:,.2f}",
    }


def _currency_code(wallet: ReimbursementWallet) -> str:
    currency_code = "USD"
    country = wallet.member.country
    if country:
        country_currency_code = CountryCurrencyCode.query.filter_by(
            country_alpha_2=country.alpha_2
        ).first()
        if country_currency_code:
            currency_code = country_currency_code.currency_code
    return currency_code


# Collection of column methods.
# These all assume that reimbursement_requests will contain at least 1 reimbursement, and will all be in APPROVED state
def _employee_id(
    eligibility_verification: Optional[EligibilityVerification],
) -> Optional[str]:
    return eligibility_verification.unique_corp_id if eligibility_verification else ""


def _get_verification_using_reimbursement_request(
    reimbursement_request: ReimbursementRequest,
    verification: EnterpriseVerificationService,
) -> Optional[EligibilityVerification]:
    if not reimbursement_request:
        # TODO: confirm there's an alert for this
        log.error(
            "Wallet Client Report found no verification",
            user_id=None,
            organization_id=None,
        )
        return None
    user_id = reimbursement_request.employee_member_id
    org_id = (
        reimbursement_request.wallet.reimbursement_organization_settings.organization_id
    )
    eligibility_verification = verification.get_verification_for_user_and_org(
        user_id=user_id, organization_id=org_id
    )
    if not eligibility_verification:
        log.error(
            "Wallet Client Report found no verification",
            user_id=user_id,
            organization_id=org_id,
        )
        return None
    return eligibility_verification


def _first_name(
    eligibility_verification: Optional[EligibilityVerification],
) -> Optional[str]:
    return eligibility_verification.first_name if eligibility_verification else ""


def _last_name(
    eligibility_verification: Optional[EligibilityVerification],
) -> Optional[str]:
    return eligibility_verification.last_name if eligibility_verification else ""


def _program(reimbursement_requests: List[ReimbursementRequest]) -> str:
    programs = {
        r.wallet.primary_expense_type.name.capitalize()  # type: ignore[attr-defined] # "str" has no attribute "name"
        for r in reimbursement_requests
        if r.wallet.primary_expense_type is not None
    }
    return ", ".join(programs)


def _fx_rate(reimbursement_requests: List[ReimbursementRequest]) -> float:
    wallet = reimbursement_requests[0].wallet
    currency_code = _currency_code(wallet)

    if (
        reimbursement_requests[0].created_at.year
        >= USE_SUBMISSION_DATE_FOR_FX_RATE_ON_AND_AFTER_YEAR
    ):
        as_of_date = reimbursement_requests[0].created_at.year
    else:
        as_of_date = reimbursement_requests[0].service_start_date.year

    fx_rate = (
        ReimbursementRequestExchangeRates.query.filter_by(
            target_currency=currency_code.upper()
        )
        .filter(
            extract("year", ReimbursementRequestExchangeRates.trading_date)
            == as_of_date
        )
        .order_by(ReimbursementRequestExchangeRates.trading_date.desc())
        .first()
    )
    if fx_rate:
        return float(fx_rate.exchange_rate)
    else:
        return 1.0


def _fx_rate_formatted(reimbursement_requests: List[ReimbursementRequest]) -> float:
    # On our reporting sheet, fx rate should be displayed as 1/fx_rate
    fx_rate = _fx_rate(reimbursement_requests)
    return 1.0 / fx_rate


def _local_currency_value_to_approve(
    reimbursement_requests: List[ReimbursementRequest],
) -> str:
    # Non-debit reimbursements
    fx_rate = _fx_rate(reimbursement_requests)
    local_amount = _value_to_approve_usd_amount(reimbursement_requests) * fx_rate
    return f"{local_amount:,.2f}"


def _value_to_approve_usd(reimbursement_requests: List[ReimbursementRequest]) -> str:
    # Non-debit reimbursements
    usd_amount = _value_to_approve_usd_amount(reimbursement_requests)
    return f"${usd_amount:,.2f}"


def _value_to_approve_usd_amount(
    reimbursement_requests: List[ReimbursementRequest],
) -> float:
    return sum(
        _handle_reimbursement_amount(r)
        for r in reimbursement_requests
        if r.reimbursement_type == ReimbursementRequestType.MANUAL
        and r.state in REPORT_REIMBURSEMENT_STATES
    )


def _total_program_to_date_amount(
    reimbursement_requests: List[ReimbursementRequest],
) -> float:
    """
    Get the total of all reimbursement requests on the current plan (annual or lifetime)
    """
    wallet_id = reimbursement_requests[0].reimbursement_wallet_id
    all_requests = ReimbursementRequest.query.filter_by(
        reimbursement_wallet_id=wallet_id
    ).all()
    reimbursement_states = (
        ReimbursementRequestState.APPROVED,
        ReimbursementRequestState.REIMBURSED,
        ReimbursementRequestState.REFUNDED,
        ReimbursementRequestState.INELIGIBLE_EXPENSE,
    )
    return sum(
        _handle_reimbursement_amount(r)
        for r in all_requests
        if r.state in reimbursement_states
    )


def _total_program_to_date(reimbursement_requests: List[ReimbursementRequest]) -> str:
    total_amount = _total_program_to_date_amount(reimbursement_requests)
    return f"${total_amount:,.2f}"


def _prior_program_to_date(reimbursement_requests: List[ReimbursementRequest]) -> str:
    prior_amount = _total_program_to_date_amount(
        reimbursement_requests
    ) - _value_to_approve_usd_amount(reimbursement_requests)
    return f"${prior_amount:,.2f}"


def _reimbursement_type(
    reimbursement_requests: List[ReimbursementRequest],
) -> Optional[str]:
    rt = reimbursement_requests[0].wallet.reimbursement_method
    return rt and rt.name  # type: ignore[attr-defined] # "str" has no attribute "name"


def _country(reimbursement_requests: List[ReimbursementRequest]) -> Optional[str]:
    country = reimbursement_requests[0].wallet.member.profile.country  # type: ignore[union-attr] # Item "None" of "Union[PractitionerProfile, MemberProfile, None]" has no attribute "country"
    return country and country.alpha_3  # type: ignore[return-value] # Incompatible return value type (got "Union[Country, None, Any, str]", expected "Optional[str]")


def _taxation(reimbursement_requests: List[ReimbursementRequest]) -> Optional[str]:
    ts = (
        reimbursement_requests[0].taxation_status
        or reimbursement_requests[0].wallet.taxation_status
    )
    return ts and ts.name  # type: ignore[attr-defined] # "str" has no attribute "name"


def _payroll_dept(
    eligibility_verification: Optional[EligibilityVerification],
) -> Optional[str]:
    return (
        eligibility_verification.record.get("payroll_dept", None)
        if eligibility_verification
        else None
    )


def _debit_card_fund_usage_amount(
    reimbursement_requests: List[ReimbursementRequest],
) -> float:
    return sum(
        _handle_reimbursement_amount(r)
        for r in reimbursement_requests
        if r.reimbursement_type == ReimbursementRequestType.DEBIT_CARD
        and r.state in REPORT_REIMBURSEMENT_STATES
    )


def _debit_card_fund_usage(reimbursement_requests: List[ReimbursementRequest]) -> str:
    debit_amount = _debit_card_fund_usage_amount(reimbursement_requests)
    return f"${debit_amount:,.2f}"


def _debit_card_fund_usage_awaiting_substantiation(
    reimbursement_requests: List[ReimbursementRequest],
) -> str:
    """
    This column provides a peek at upcoming debit expenses not yet approved.

    For this column, we need to do a query for debit card transactions in a pending state. This is because we don't
    attach reimbursement_requests in a pending state to a wallet report, since they're not quite approved yet.
    """
    r = reimbursement_requests[0]
    wallet_id = r.reimbursement_wallet_id
    category_id = r.reimbursement_request_category_id
    all_reimbursement_requests_for_wallet_category = (
        ReimbursementRequest.query.filter_by(
            reimbursement_request_category_id=category_id
        )
        .filter_by(reimbursement_wallet_id=wallet_id)
        .all()
    )
    debit_awaiting_amount = _sum_unsubstantiated_debit_reimbursements(
        all_reimbursement_requests_for_wallet_category
    )
    return f"${debit_awaiting_amount:,.2f}"


def _sum_unsubstantiated_debit_reimbursements(
    reimbursement_requests: List[ReimbursementRequest],
) -> float:
    # 1) reimbursement type should be debit card
    # 2) reimbursement state should be needs receipt, insufficient receipt, receipt submitted
    return sum(
        convert_cents_to_dollars(r.amount)
        for r in reimbursement_requests
        if r.reimbursement_type == ReimbursementRequestType.DEBIT_CARD
        and r.state in UNSUBSTANTIATED_DEBIT_REIMBURSEMENT_STATES
    )


def _total_funds_for_tax_handling(
    reimbursement_requests: List[ReimbursementRequest],
) -> str:
    debit_card_amount = _debit_card_fund_usage_amount(reimbursement_requests)
    reimbursement_amount = _value_to_approve_usd_amount(reimbursement_requests)
    return f"${debit_card_amount + reimbursement_amount:,.2f}"


def _date_of_birth(
    eligibility_verification: Optional[EligibilityVerification],
) -> str:
    return (
        eligibility_verification.date_of_birth.strftime("%m/%d/%Y")
        if eligibility_verification and eligibility_verification.date_of_birth
        else ""
    )


def _employer_assigned_id(
    eligibility_verification: Optional[EligibilityVerification],
) -> Optional[str]:
    return (
        eligibility_verification.employer_assigned_id
        if eligibility_verification
        else ""
    )


def _line_of_business(
    eligibility_verification: Optional[EligibilityVerification],
) -> str:
    return (
        eligibility_verification.record.get("lob", "")
        if eligibility_verification
        else ""
    )


def _direct_payment_fund_usage(
    reimbursement_requests: List[ReimbursementRequest],
) -> str:
    amount = sum(
        _handle_reimbursement_amount(r)
        for r in reimbursement_requests
        if r.reimbursement_type == ReimbursementRequestType.DIRECT_BILLING
        and r.state in REPORT_REIMBURSEMENT_STATES
    )
    return f"${amount:,.2f}"


def _expense_year(
    reimbursement_requests: List[ReimbursementRequest],
) -> str:
    return str(reimbursement_requests[0].service_start_date.year)


def _handle_reimbursement_amount(reimbursement_request):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    amount = reimbursement_request.amount
    if (
        reimbursement_request.state == ReimbursementRequestState.REFUNDED
        and reimbursement_request.amount > 0
    ):
        amount = amount * -1
    return convert_cents_to_dollars(amount)


def _total_ytd_amount(reimbursement_requests: List[ReimbursementRequest]) -> str:
    """
    Get the total of all reimbursement requests for a wallet
    """
    total_amount = sum(
        _handle_reimbursement_amount(r)
        for r in reimbursement_requests
        if r.state in YTD_REPORT_REIMBURSEMENT_STATES
    )
    return f"${total_amount:,.2f}"


def _get_ytd_local_currency_rate(reimbursement_requests: List[ReimbursementRequest]):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    amount = sum(
        _handle_reimbursement_amount(r)
        for r in reimbursement_requests
        if r.state in YTD_REPORT_REIMBURSEMENT_STATES
    )
    fx_rate = _fx_rate(reimbursement_requests)
    local_amount = amount * fx_rate
    return f"{local_amount:,.2f}"


# This goes at the bottom because it needs to have the function definitions preceeding it
WALLET_REPORT_COLUMN_FUNCTIONS = {
    WalletReportConfigColumnTypes.EMPLOYEE_ID.name: _employee_id,
    WalletReportConfigColumnTypes.EMPLOYER_ASSIGNED_ID.name: _employer_assigned_id,
    WalletReportConfigColumnTypes.DATE_OF_BIRTH.name: _date_of_birth,
    WalletReportConfigColumnTypes.FIRST_NAME.name: _first_name,
    WalletReportConfigColumnTypes.LAST_NAME.name: _last_name,
    WalletReportConfigColumnTypes.PROGRAM.name: _program,
    WalletReportConfigColumnTypes.VALUE_TO_APPROVE.name: _local_currency_value_to_approve,
    WalletReportConfigColumnTypes.FX_RATE.name: _fx_rate_formatted,
    WalletReportConfigColumnTypes.VALUE_TO_APPROVE_USD.name: _value_to_approve_usd,
    WalletReportConfigColumnTypes.PRIOR_PROGRAM_TO_DATE.name: _prior_program_to_date,
    WalletReportConfigColumnTypes.TOTAL_PROGRAM_TO_DATE.name: _total_program_to_date,
    WalletReportConfigColumnTypes.REIMBURSEMENT_TYPE.name: _reimbursement_type,
    WalletReportConfigColumnTypes.COUNTRY.name: _country,
    WalletReportConfigColumnTypes.TAXATION.name: _taxation,
    WalletReportConfigColumnTypes.PAYROLL_DEPT.name: _payroll_dept,
    WalletReportConfigColumnTypes.DEBIT_CARD_FUND_USAGE_USD.name: _debit_card_fund_usage,
    WalletReportConfigColumnTypes.DEBIT_CARD_FUND_AWAITING_SUBSTANTIATION.name: _debit_card_fund_usage_awaiting_substantiation,
    WalletReportConfigColumnTypes.TOTAL_FUNDS_FOR_TAX_HANDLING.name: _total_funds_for_tax_handling,
    WalletReportConfigColumnTypes.LINE_OF_BUSINESS.name: _line_of_business,
    WalletReportConfigColumnTypes.DIRECT_PAYMENT_FUND_USAGE.name: _direct_payment_fund_usage,
    WalletReportConfigColumnTypes.EXPENSE_YEAR.name: _expense_year,
}
