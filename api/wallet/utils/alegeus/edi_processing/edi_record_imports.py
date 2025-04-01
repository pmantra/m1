import csv
import datetime
from io import StringIO
from typing import Any, Dict, Tuple

from models.enterprise import Organization
from utils.log import logger
from wallet.alegeus_api import format_name_field
from wallet.constants import (
    ALEGEUS_DEBIT_CARD_STOCK_ID,
    ALEGEUS_PASSWORD_EDI,
    ALEGEUS_PAYROLL_ACCOUNT_NAME,
    ALEGEUS_TPAID,
    MAVEN_ADDRESS,
    EdiTemplateName,
)
from wallet.utils.alegeus.edi_processing.common import (
    AlegeusExportRecordTypes,
    format_file_date,
    format_filename_for_new_employer_config,
    get_plans_from_org_settings,
    get_total_plan_count,
    get_versioned_file,
    validate_input_date,
    validated_plan_items,
)
from wallet.utils.alegeus.upload_to_ftp_bucket import upload_blob

log = logger(__name__)

# These rows are defined in WealthCareAdmin, under data exports -> setup, with their corresponding templates.
ia_header_row = [
    "IA",
    "4",  # IA header row, and IL-EN, IL-EM, IL-EK row to request transaction data
    ALEGEUS_PASSWORD_EDI,
    EdiTemplateName.IMPORT,
    EdiTemplateName.RESULT,
    EdiTemplateName.EXPORT,
]


def write_rows_for_il_records(writer, export_from_date, export_to_date):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Creates the  header row for the IL import file type.

    @param writer: CSV writer
    @param export_from_date: datetime to filter the starting point of the transactions requested by.
    @param export_to_date: datetime to filter the end point of the transactions requested by.
    """
    formatted_export_from_date = (
        datetime.datetime.today() - datetime.timedelta(days=1)
    ).strftime("%Y%m%d")
    formatted_export_to_date = datetime.datetime.today().strftime("%Y%m%d")

    if export_from_date:
        formatted_export_from_date = validate_input_date(export_from_date)

    if export_to_date:
        formatted_export_to_date = validate_input_date(export_to_date)

    for type in AlegeusExportRecordTypes.list():
        writer.writerow(
            [
                "IL",  # Record Type
                ALEGEUS_TPAID,
                None,  # Employer ID
                type,  # Export Record Type
                formatted_export_from_date,  # Export From Time
                formatted_export_to_date,  # Export To Time
                None,  # Employee Status Code
                None,  # Transaction Origin
                None,  # Transaction Type
                "0",  # Transaction Status (all)
                "0",  # Plan Year - All plan years
                "0",  # Output Format,
            ]
        )


def format_il_export_file(is_retry, export_from_date, export_to_date):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Formats the filename and writes the remaining rows to the CSV we are requesting data for.  Outputs the request
    content which we upload to their SFTP server.

    @param is_retry: Boolean to let us know if this is a retry
    @param export_from_date: date to filter the starting point of the transactions requested by.
    @param export_to_date: date to tilter the end point of the transactions requested by.
    """
    file_date = format_file_date()
    if not is_retry:
        destination_filename = f"MAVENIL{file_date}.mbi"
    else:
        version_filename = get_versioned_file()
        destination_filename = f"{version_filename}.mbi"
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(ia_header_row)
    write_rows_for_il_records(writer, export_from_date, export_to_date)

    csv_contents = output.getvalue()
    return destination_filename, csv_contents


def upload_il_file_to_alegeus(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    is_retry: bool = False,
    export_from_date: datetime = None,  # type: ignore[valid-type] # Module "datetime" is not valid as a type
    export_to_date: datetime = None,  # type: ignore[valid-type] # Module "datetime" is not valid as a type
):
    """
    Creates and uploads file request template to the Alegeus SFTP server.

    @param is_retry: Boolean to let us know if this is a retry
    @param export_from_date: datetime to filter the starting point of the transactions requested by.
    @param export_to_date: datetime to filter the end point of the transactions requested by.
    """
    success = False
    try:
        destination_filename, csv_contents = format_il_export_file(
            is_retry, export_from_date, export_to_date
        )
        upload_blob(csv_contents, destination_filename)
        success = True
    except Exception as e:
        log.exception(
            "upload_il_file_to_alegeus: There was an error uploading the blob.",
            error=e,
        )
    else:
        log.info(
            f"upload_il_file_to_alegeus: Uploading file: {destination_filename} for retry: {is_retry}, "
            f"export_from_date: {export_from_date} export_to_date: {export_to_date}"
        )
    finally:
        return success  # noqa  B012  TODO:  return/continue/break inside finally blocks cause exceptions to be silenced. Exceptions should be silenced in except blocks. Control statements can be moved outside the finally block.


def upload_ib_file_to_alegeus(wallet, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Creates and uploads employee demographic template to the Alegeus SFTP server.

    @param wallet: Maven wallet we want to update demographics for.
    @param user_id: the ID of the user
    """
    success = False
    try:
        destination_filename, csv_contents = format_ib_import_file(wallet, user_id)
        upload_blob(csv_contents, destination_filename)
        success = True
    except Exception as e:
        log.info(
            "upload_il_file_to_alegeus: There was an error uploading the blob.",
            Exception=e,
        )
    else:
        log.info(
            f"upload_employee_demographics_ib_file_to_alegeus: Uploading file: {destination_filename}, "
            f"for wallet {wallet.id}"
        )
    finally:
        return success  # noqa  B012  TODO:  return/continue/break inside finally blocks cause exceptions to be silenced. Exceptions should be silenced in except blocks. Control statements can be moved outside the finally block.


def format_ib_import_file(wallet, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Format File for a wallet to upload to Alegeus SFTP servers to update a users foreign shipping address
    We're using the Maven_IB_Foreign_Debit_Card IB template in our import template.

    @param wallet: wallet to update on alegeus
    @param user_id: the ID of the user
    """
    destination_filename = (
        f"MAVENIB_{wallet.id}_{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.mbi"
    )

    output = StringIO()
    writer = csv.writer(output)
    # Header IA row for IB
    writer.writerow(
        [
            "IA",
            "2",  # IA header row, and IB demographic import row
            ALEGEUS_PASSWORD_EDI,
            EdiTemplateName.IMPORT_FOREIGN_IB,
            EdiTemplateName.RESULT_FOREIGN_IB,
            EdiTemplateName.EXPORT_FOREIGN_IB,
        ]
    )
    # User Demographic row
    organization = wallet.reimbursement_organization_settings.organization
    first_name, last_name, date_of_birth = wallet.get_first_name_last_name_and_dob()
    wallet_user = wallet.get_user_by_id(user_id)
    member_address = wallet_user and wallet_user.addresses and wallet_user.addresses[0]
    writer.writerow(
        [
            "IB",
            ALEGEUS_TPAID,
            organization.alegeus_employer_id,
            wallet.alegeus_id,
            format_name_field(last_name),
            format_name_field(first_name),
            MAVEN_ADDRESS["address_1"],
            MAVEN_ADDRESS["city"],
            MAVEN_ADDRESS["state"],
            MAVEN_ADDRESS["zip"],
            MAVEN_ADDRESS["country"],
            1,  # Ship to Foreign Address => True
            member_address.street_address,
            "",  # Street Address 2 - ignore
            member_address.city,
            member_address.state,
            member_address.zip_code,
            member_address.country,
        ]
    )

    csv_contents = output.getvalue()
    return destination_filename, csv_contents


def format_is_import_file(organization_list: list) -> Tuple[str, str]:
    """
    Format File for creating a new employer record (IS) to be imported into Alegeus SFTP.

    @param organization_list: a list of organization ids

    Returns:
        Tuple[str, str]: Tuple[file_name: str, csv_contents: str]
    """
    destination_filename = format_filename_for_new_employer_config(
        organization_list, "IS"
    )
    output = StringIO()
    writer = csv.writer(output)
    # Header IA row for IS
    writer.writerow(
        [
            "IA",
            len(organization_list) + 1,  # IA header + IS employer demographic row(s)
            ALEGEUS_PASSWORD_EDI,
            EdiTemplateName.IMPORT,
            EdiTemplateName.RESULT,
            EdiTemplateName.EXPORT,
        ]
    )
    for organization in organization_list:
        organization = Organization.query.filter_by(id=organization).one()
        # Alegeus does not accept the "MVN" prefix for this specific file
        formatted_is_employer_id = organization.alegeus_employer_id[3:]

        writer.writerow(
            [
                "IS",  # Record ID
                ALEGEUS_TPAID,  # Tpa ID
                "Brand",  # Brand ID
                formatted_is_employer_id,  # Employer ID
                organization.name,  # Employer Name
                MAVEN_ADDRESS["address_1"],
                MAVEN_ADDRESS["address_2"],
                MAVEN_ADDRESS["city"],
                MAVEN_ADDRESS["state"],
                MAVEN_ADDRESS["zip"],
                MAVEN_ADDRESS["country"],
                "",  # Employer phone number
                "",  # Fax number
                "",  # Employer email
                "",  # Tax ID Number
                "",  # TIN Indicator
                "",  # Number of Employees
                "walletprocessing@mavenclinic.com",  # Setup email
                1,  # Projected amounts
                "Maven IVR",  # Thermal text
                2,  # Employer card option
                "",  # Primary thermal logo
                "",  # Secondary thermal logo,
                0,  # Card activation
                ALEGEUS_DEBIT_CARD_STOCK_ID,  # Card Stock ID
                36,  # Card expiration in months
                30,  # Card re-issue in lead days
                1,  # Card mailing address indicator
                0,  # Check process method
                37717652277314361,  # Employer options
                "",  # Shipping contact name
                "",  # Shipping contact phone
                "",  # Notes
                "",  # Self-service template override
                "",  # Record tracking number
            ]
        )
    csv_contents = output.getvalue()
    return destination_filename, csv_contents


def format_iv_import_file(organization_list: list, banking_info: Dict[str, Any] = None):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[assignment] # Incompatible default for argument "banking_info" (default has type "None", argument has type "Dict[str, Any]")
    """
    Format File for creating a new employer banking record (IV) to be imported into Alegeus SFTP.

    @param organization_list: a list of organization ids
    @param banking_info: a dictionary representing an organizations banking information
    """
    destination_filename = format_filename_for_new_employer_config(
        organization_list, "IV"
    )
    output = StringIO()
    writer = csv.writer(output)
    # Header IA row for IV
    writer.writerow(
        [
            "IA",
            len(organization_list) + 1,  # IA header row + IV banking information row(s)
            ALEGEUS_PASSWORD_EDI,
            EdiTemplateName.IMPORT,
            EdiTemplateName.RESULT,
            EdiTemplateName.EXPORT,
        ]
    )
    for organization_id in organization_list:
        organization = Organization.query.filter_by(id=organization_id).one()

        # banking info will only be set during automatic upload of a single organization
        writer.writerow(
            [
                "IV",  # Record ID
                ALEGEUS_TPAID,  # Tpa ID
                f"{organization.name}",  # Bank account name
                banking_info["bank_account_usage_code"] if banking_info else 3,
                banking_info["financial_institution"] if banking_info else "",
                banking_info["account_number"] if banking_info else "",
                banking_info["routing_number"] if banking_info else "",
                1,  # Account type default checking
                0,  # Daily POS activity via email
                "",  # Email address to receive POS activity
                1,  # Access level
                "",  # Record tracking number
            ]
        )

    csv_contents = output.getvalue()
    return destination_filename, csv_contents


def format_it_import_file(organization_list: list, payroll_only: bool = False):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Format File for creating a new employer Notional Account record (IT) to be imported into Alegeus SFTP.

    @param organization_list: a list of organization ids
    @param payroll_only: A bool indicating if this organization supports payroll only
    """
    destination_filename = format_filename_for_new_employer_config(
        organization_list, "IT"
    )
    output = StringIO()
    writer = csv.writer(output)
    # Header IA row for IT
    writer.writerow(
        [
            "IA",
            len(organization_list) + 1,  # Header + IT row(s) to set up notional account
            ALEGEUS_PASSWORD_EDI,
            EdiTemplateName.IMPORT,
            EdiTemplateName.RESULT,
            EdiTemplateName.EXPORT,
        ]
    )
    for organization_id in organization_list:
        organization = Organization.query.filter_by(id=organization_id).one()
        if payroll_only:
            bank_account_name = ALEGEUS_PAYROLL_ACCOUNT_NAME
        else:
            bank_account_name = f"{organization.name}"
        writer.writerow(
            [
                "IT",  # Record ID
                ALEGEUS_TPAID,  # Tpa ID
                organization.alegeus_employer_id,  # Employer ID
                bank_account_name,  # Bank account name
                f"{organization.name} Notional Account",  # Employer bank account name
                1,  # Zero balance account
                "",  # Receive daily pos activity via email
                "",  # Email address to receive pos activity
                3,  # Usage type
                "",  # Plan type
                "",  # Record tracking number
            ]
        )
    csv_contents = output.getvalue()
    return destination_filename, csv_contents


def format_iu_import_file(organization_list: list):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Format File for creating a new employer plan records (IU) to be imported into Alegeus SFTP.

    @param organization_list: a list of organization ids
    """
    destination_filename = format_filename_for_new_employer_config(
        organization_list, "IU"
    )
    output = StringIO()
    writer = csv.writer(output)
    total_plan_count = get_total_plan_count(organization_list)
    # Header IA row for IU
    writer.writerow(
        [
            "IA",
            total_plan_count
            + 1,  # IA header row, and multiple IU rows for employer plans
            ALEGEUS_PASSWORD_EDI,
            EdiTemplateName.IMPORT,
            EdiTemplateName.RESULT,
            EdiTemplateName.EXPORT,
        ]
    )
    for organization_id in organization_list:
        organization = Organization.query.filter_by(id=organization_id).one()
        plans = get_plans_from_org_settings(organization)
        for plan in plans:
            plan_items = validated_plan_items(plan)
            writer.writerow(
                [
                    "IU",  # Record ID
                    ALEGEUS_TPAID,  # Tpa ID
                    organization.alegeus_employer_id,  # Employer ID
                    plan_items["plan_id"],
                    plan_items["account_type"],
                    plan_items["start_date"],
                    plan_items["end_date"],
                    plan_items["run_out_date"],  # Run out period end date
                    1,  # Allow partial manual transactions
                    "",  # Max total amount
                    plan_items["default_plan_options"],
                    plan_items["plan_options"],
                    "",  # Grace period date
                    "",  # Coverage tier type ID,
                    "",  # Default coverage tier ID
                    "0000",  # Deposit subtype identifiers
                    90,  # Term employee run out days
                    plan_items["custom_description"],
                    0,  # Auto issue card to dependents
                    "",  # Auto issue card date
                    plan_items["auto_renew"],
                    plan_items["hra_type"],
                    "",  # Record tracking number
                ]
            )
    csv_contents = output.getvalue()
    return destination_filename, csv_contents


def create_file_list(organizations: list, banking_information: Dict[str, Any] = None):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[assignment] # Incompatible default for argument "banking_information" (default has type "None", argument has type "Dict[str, Any]")
    """
    Creates Employer Org CSV files in specific order for uploading into Alegeus
    @param organizations: A list of organization ids
    @param banking_information: A dictionary of banking information or None

    @return a list of tuples containing the filename and the file contents for each type of file (IS, IV, IT, IU)
    """
    file_set = []
    if banking_information is None:
        banking_information = {}
    payroll_only = banking_information.get("payroll_only")

    is_filename, is_csv_content = format_is_import_file(organizations)
    file_set.append((is_filename, is_csv_content))
    # If it is not a payroll only org, create a banking configuration.
    if not payroll_only:
        iv_filename, iv_csv_content = format_iv_import_file(
            organizations, banking_information
        )
        file_set.append((iv_filename, iv_csv_content))
    it_filename, it_csv_content = format_it_import_file(organizations, payroll_only)  # type: ignore[arg-type] # Argument 2 to "format_it_import_file" has incompatible type "Optional[Any]"; expected "bool"
    file_set.append((it_filename, it_csv_content))
    iu_filename, iu_csv_content = format_iu_import_file(organizations)
    file_set.append((iu_filename, iu_csv_content))
    return file_set
