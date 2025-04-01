import csv
import datetime
import io
import zipfile
from collections import defaultdict
from enum import Enum
from typing import Any, Dict, List, Tuple

import flask_login as login
from flask import Blueprint, Response, flash, redirect, request, send_file, url_for
from slugify import slugify
from werkzeug.datastructures import ImmutableMultiDict
from werkzeug.utils import secure_filename

from admin.common import https_url
from cost_breakdown.models.cost_breakdown import ReimbursementRequestToCostBreakdown
from direct_payment.pharmacy.tasks.libs.smp_audit import (
    download_scheduled_file_audit_report,
)
from direct_payment.pharmacy.tasks.rq_job_process_smp_rx import (
    generate_smp_file,
    process_rx_job,
)
from direct_payment.reconciliation.constants import (
    CCRM_CLINIC_GROUP_NAME,
    CCRM_CLINIC_NAMES,
    CLINIC_RECONCILIATION_FILE_PREFIX,
    COLUMBIA_CLINIC_GROUP_NAME,
    COLUMBIA_CLINIC_NAMES,
    NYU_LANGONE_CLINIC_GROUP_NAME,
    NYU_LANGONE_CLINIC_NAMES,
    REPORT_FIELDS,
    US_FERTILITY_CLINIC_GROUP_NAME,
)
from direct_payment.reconciliation.tasks.job_generate_ccrm_reconciliation_report import (
    generate_reconciliation_report,
)
from direct_payment.reconciliation.tasks.job_generate_us_fertility_report import (
    generate_us_fertility_reconciliation_report,
)
from storage.connection import db
from utils.log import logger
from wallet.models.reimbursement import ReimbursementClaim
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.repository.reimbursement_request import ReimbursementRequestRepository
from wallet.repository.reimbursement_wallet import ReimbursementWalletRepository
from wallet.services.payments import save_employer_direct_billing_account
from wallet.services.reimbursement_wallet import ReimbursementWalletService
from wallet.services.wallet_client_reporting import (
    download_client_report_reimbursements_by_date,
)
from wallet.tasks.alegeus_edi import (
    download_transactions_alegeus,
    upload_and_process_new_employer_configs_to_alegeus,
)
from wallet.utils.alegeus.claims.create import create_direct_payment_claim_in_alegeus
from wallet.utils.alegeus.edi_processing.common import encrypt_banking_data
from wallet.utils.alegeus.edi_processing.edi_record_imports import (
    format_is_import_file,
    format_it_import_file,
    format_iu_import_file,
    format_iv_import_file,
    upload_il_file_to_alegeus,
)
from wallet.utils.alegeus.edi_processing.process_edi_balance_update import (
    process_balance_update,
)

BANK_ROUTING_NUMBER_LENGTH = 9
BANK_ACCOUNT_NUMBER_MIN_LENGTH = 3
BANK_ACCOUNT_NUMBER_MAX_LENGTH = 17

URL_PREFIX = "wallet_tools"
REPORTING_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S%z"

wallet = Blueprint(URL_PREFIX, __name__)
log = logger(__name__)


@wallet.route("/retry_request_edi", methods=["POST"])
@login.login_required
def retry_request_edi():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    data = request.form
    start_date = _parse_date(data.get("start_date"))
    end_date = _parse_date(data.get("end_date"))
    success = upload_il_file_to_alegeus(
        is_retry=True, export_from_date=start_date, export_to_date=end_date
    )
    if success:
        flash(
            "File successfully uploaded. Please wait 30 minutes before taking the next step to process the file.",
            category="success",
        )
    else:
        flash(
            "Unable to upload file. Do not attempt to process file.", category="error"
        )
    return redirect(https_url("admin.wallet_tools"))


@wallet.route("/retry_process_edi", methods=["POST"])
@login.login_required
def retry_process_edi():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    download_transactions_alegeus.delay(is_retry=True, team_ns="payments_platform")
    flash("Request submitted to process Request EDI File Import.")
    return redirect(https_url("admin.wallet_tools"))


@wallet.route("/download_org_config_zip", methods=["POST"])
@login.login_required
def download_edi_org_config_files():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    data = request.form
    org_string = data.get("org_string")
    try:
        organization_list = _parse_organizations(org_string)
    except Exception as e:
        flash(
            f"There is an error in the list of organization ids entered. Please check and try again. Error Message: {e}",
            category="error",
        )
        return redirect(https_url("admin.wallet_tools"))
    try:
        file_list = downloaded_file_list(organization_list)
    except Exception as e:
        flash(
            "Unable to generate files. Please check all organizations and associated Reimbursement Plans are setup "
            f"properly. Error Message: {e}",
            category="error",
        )
        return redirect(https_url("admin.wallet_tools"))
    date_format = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    zipped_file = io.BytesIO()
    with zipfile.ZipFile(zipped_file, "w") as csv_zip:
        for filename, file_content in file_list:
            csv_zip.writestr(filename, file_content)
    return Response(
        zipped_file.getvalue(),
        mimetype="application/zip",
        headers={
            "Content-Disposition": f"attachment;filename=Alegeus_New_Employer_Configuration_Files_{date_format}.zip"
        },
    )


@wallet.route("/download_ih_file", methods=["POST"])
@login.login_required
def download_ih_file():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    year = request.form.get("year", None)
    wallet_id = request.form.get("wallet_id", None)
    ros_id = request.form.get("ros_id", None)

    if year is None:
        log.error(
            "Params missing from request to generate IH file",
            year=str(year),
            wallet_id=str(wallet_id),
            ros_id=str(ros_id),
        )
        flash("'Year' is required for generate IH file")
        return redirect(https_url("admin.wallet_tools"))

    if int(year) <= datetime.datetime.now(datetime.timezone.utc).year:
        log.error(
            "Invalid year supplied for request to generate IH file",
            year=str(year),
            wallet_id=str(wallet_id),
            ros_id=str(ros_id),
        )
        flash("'Year' must be in the future")
        return redirect(https_url("admin.wallet_tools"))

    filters = dict()

    if wallet_id:
        filters["wallet_ids"] = [wallet_id]
    if ros_id:
        filters["ros_ids"] = [ros_id]

    try:
        generated_file_string_buffer = process_balance_update(
            year=int(year), dry_run=True, upload_to_gcs=False, **filters
        )
        byte_buffer = io.BytesIO(
            generated_file_string_buffer.getvalue().encode("utf-8")
        )
    except Exception as exc:
        flash(
            f"Exception encountered while attempting to generate IH file: {str(exc)}",
            category="error",
        )
        return redirect(https_url("admin.wallet_tools"))

    flash("Successfully generated IH file", category="success")

    return send_file(
        byte_buffer,
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"IH_{year}.csv",  # type: ignore[call-arg] # Unexpected keyword argument "download_name" for "send_file"
    )


@wallet.route("/create_employer_configurations", methods=["POST"])
@login.login_required
def create_employer_configurations():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    success, data_dict = _parse_employer_configuration_form_data(request.form)
    if success:
        try:
            org_id = data_dict["org_id"]
            encrypted_information = encrypt_banking_data(org_id, data_dict)
            upload_and_process_new_employer_configs_to_alegeus.delay(
                encrypted_information,
                org_id,
                job_timeout=60 * 60,
                team_ns="payments_platform",
            )
            flash(
                "Configuration process started. Please check #wallet-edi-alegeus-config for job notifications.",
                category="success",
            )
            return redirect(https_url("admin.wallet_tools"))
        except Exception as e:
            flash(
                f"Configuration process not started. Please fix error: {e}",
                category="error",
            )
            return redirect(https_url("admin.wallet_tools"))
    else:
        flash(data_dict, category="error")
        return redirect(https_url("admin.wallet_tools"))


@wallet.route("/employer_direct_billing_account", methods=["POST"])
@login.login_required
def add_employer_direct_billing_account():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    success, data_dict = _parse_employer_direct_billing_account_form_data(request.form)
    if success:
        try:
            org_settings = ReimbursementOrganizationSettings.query.filter(
                ReimbursementOrganizationSettings.id == data_dict["org_settings_id"]
            ).one_or_none()
            if not org_settings:
                flash(
                    "Cannot load Reimbursement Organization settings.", category="error"
                )
                return redirect(https_url("admin.wallet_tools"))

            save_employer_direct_billing_account(
                org_settings=org_settings,
                account_type=data_dict["account_type"],
                account_holder_type=data_dict["account_holder_type"],
                account_number=data_dict["account_number"],
                routing_number=data_dict["routing_number"],
                headers=request.headers,  # type: ignore[arg-type] # Argument "headers" to "save_employer_direct_billing_account" has incompatible type "EnvironHeaders"; expected "Optional[Mapping[str, str]]"
            )

            flash(
                f"Bank account saved for {org_settings}.",
                category="success",
            )

            return redirect(https_url("admin.wallet_tools"))
        except Exception as e:
            flash(
                f"Failed to add account. Error: {e}",
                category="error",
            )
            return redirect(https_url("admin.wallet_tools"))
    else:
        flash(data_dict, category="error")
        return redirect(https_url("admin.wallet_tools"))


def _parse_date(date_str):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    try:
        if not date_str:
            dt = None
        else:
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except ValueError as e:
        flash(f"Unable to set filter dates. e={e}", category="error")
        return
    return dt


def _parse_organizations(org_str):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    values = [int(org_id) for org_id in org_str.split(",") if org_id]
    return values


def _parse_employer_configuration_form_data(form: Dict[str, Any]):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    account_number = form.get("account_number")
    routing_number = form.get("routing_number")
    payroll_only = bool(form.get("payroll_only"))
    if not payroll_only:
        if (
            len(account_number) < BANK_ACCOUNT_NUMBER_MIN_LENGTH  # type: ignore[arg-type] # Argument 1 to "len" has incompatible type "Optional[Any]"; expected "Sized"
            or len(account_number) > BANK_ACCOUNT_NUMBER_MAX_LENGTH  # type: ignore[arg-type] # Argument 1 to "len" has incompatible type "Optional[Any]"; expected "Sized"
        ):
            return False, "Invalid Account Number"
        elif len(routing_number) != BANK_ROUTING_NUMBER_LENGTH:  # type: ignore[arg-type] # Argument 1 to "len" has incompatible type "Optional[Any]"; expected "Sized"
            return False, "Invalid Routing Number"
    banking_information = {
        "org_id": form["org_id"],
        "bank_account_usage_code": form["bank_account_usage_code"],
        "financial_institution": form.get("financial_institution"),
        "account_number": account_number,
        "routing_number": routing_number,
        "payroll_only": payroll_only,
    }
    return True, banking_information


def downloaded_file_list(organizations) -> List[Tuple[str, str]]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    file_list = [
        format_is_import_file(organizations),
        format_iv_import_file(organizations),
        format_it_import_file(organizations),
        format_iu_import_file(organizations),
    ]
    return file_list


def _parse_employer_direct_billing_account_form_data(form: Dict[str, Any]):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    account_number = form.get("account_number")
    routing_number = form.get("routing_number")
    if (
        len(account_number) < BANK_ACCOUNT_NUMBER_MIN_LENGTH  # type: ignore[arg-type] # Argument 1 to "len" has incompatible type "Optional[Any]"; expected "Sized"
        or len(account_number) > BANK_ACCOUNT_NUMBER_MAX_LENGTH  # type: ignore[arg-type] # Argument 1 to "len" has incompatible type "Optional[Any]"; expected "Sized"
    ):
        return False, "Invalid Account Number"
    elif len(routing_number) != BANK_ROUTING_NUMBER_LENGTH:  # type: ignore[arg-type] # Argument 1 to "len" has incompatible type "Optional[Any]"; expected "Sized"
        return False, "Invalid Routing Number"
    banking_information = {
        "org_settings_id": form["org_settings_id"],
        "account_type": form["account_type"],
        "account_holder_type": form["account_holder_type"],
        "account_number": account_number,
        "routing_number": routing_number,
    }
    return True, banking_information


@wallet.route("/wallet_client_report_reimbursements_audit", methods=(["POST"]))
@login.login_required
def download_wallet_client_report_reimbursements():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if not login.current_user.is_authenticated:
        return redirect(https_url(".login_view"))

    date_input = request.form.get("peakone_date")
    peakone_date = datetime.datetime.strptime(date_input, "%Y-%m-%d").date()  # type: ignore[arg-type] # Argument 1 to "strptime" of "datetime" has incompatible type "Optional[Any]"; expected "str"

    if not peakone_date:
        flash("Invalid Request: Please provide a valid Date")
        return

    report = download_client_report_reimbursements_by_date(peakone_date)
    fp = io.BytesIO()
    fp.write(report.getvalue().encode())
    fp.seek(0)
    report.close()

    today = datetime.datetime.today().strftime("%Y%m%d")
    filename = secure_filename(
        f"{peakone_date}_Wallet_Reimbursement_Report_Audit_{today}.csv"
    )
    return send_file(  # type: ignore[call-arg] # Unexpected keyword argument "download_name" for "send_file"
        fp, mimetype="text/csv", as_attachment=True, download_name=filename
    )


class SMPFileType(Enum):
    SCHEDULED = "SCHEDULED"
    SHIPPED = "SHIPPED"
    CANCELLED = "CANCELLED"
    REIMBURSEMENT = "REIMBURSEMENT"


@wallet.route("/handle_smp_rx_file", methods=["POST"])
@login.login_required
def handle_smp_rx_file():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    data = request.form
    download_file = data.get("download_file")
    process_file = data.get("process_file")
    file_type = SMPFileType(data.get("file_type"))
    file_date = datetime.datetime.strptime(data.get("file_date"), "%Y-%m-%d").date()  # type: ignore[arg-type] # Argument 1 to "strptime" of "datetime" has incompatible type "Optional[Any]"; expected "str"

    if download_file:
        try:
            temp_file, filename = generate_smp_file(file_type.value, file_date)
            if temp_file:
                return send_file(  # type: ignore[call-arg] # Unexpected keyword argument "download_name" for "send_file"
                    temp_file,
                    mimetype="text/csv",
                    as_attachment=True,
                    download_name=filename,
                )
            else:
                flash(f"File not found: {filename}", category="error")
        except Exception as e:
            flash(f"Unable to generate file. Error: {e}", category="error")
            return redirect(https_url("admin.wallet_tools"))
    elif process_file:
        process_rx_job.delay(file_type=file_type.value, date=file_date)
        flash(
            f"{file_type.value} processing for {file_date}. Please see #mmb-rx-oops-alerts to ensure no errors were "
            "reported.",
            category="info",
        )

    return redirect(https_url("admin.wallet_tools"))


@wallet.route("/reconciliation_report", methods=["POST"])
@login.login_required
def retrieve_ccrm_reconciliation_report():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    data = request.form
    clinic_group_name = data.get("clinic_name")
    if clinic_group_name == CCRM_CLINIC_GROUP_NAME:
        clinic_names = CCRM_CLINIC_NAMES
    elif clinic_group_name == COLUMBIA_CLINIC_GROUP_NAME:
        clinic_names = COLUMBIA_CLINIC_NAMES
    elif clinic_group_name == NYU_LANGONE_CLINIC_GROUP_NAME:
        clinic_names = NYU_LANGONE_CLINIC_NAMES
    else:
        flash("Unable to generate file, missing clinic", category="error")
        return redirect(https_url("admin.wallet_tools"))
    return _retrieve_reconciliation_report(clinic_group_name, clinic_names)


@wallet.route("/us_fertility_reconciliation_report", methods=["POST"])
@login.login_required
def retrieve_us_fertility_reconciliation_report():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return _retrieve_zipped_us_reconciliation_reports()


def _retrieve_reconciliation_report(group_name, clinic_names):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    data = request.form
    (
        start_time,
        end_time,
        start_time_str,
        end_time_str,
    ) = _gather_form_data_for_recon_reports(data)
    records, success = generate_reconciliation_report(
        True, group_name, clinic_names, start_time, end_time
    )

    if success:
        try:
            file_name = f"{CLINIC_RECONCILIATION_FILE_PREFIX}_{group_name}_{start_time_str}_to_{end_time_str}.csv"

            report = io.StringIO()
            csvwriter = csv.writer(report, delimiter=",")
            csvwriter.writerow(REPORT_FIELDS)
            csvwriter.writerows(records)

            report.seek(0)
            response = Response(report)

            response.headers["Content-Description"] = "File Transfer"
            response.headers["Cache-Control"] = "no-cache"
            response.headers["Content-Type"] = "text/csv"
            response.headers[
                "Content-Disposition"
            ] = f"attachment; filename={file_name}"

            return response
        except Exception as e:
            flash(
                f"Unable to generate file for {CCRM_CLINIC_GROUP_NAME}. Error: {e}",
                category="error",
            )
            return redirect(https_url("admin.wallet_tools"))
    else:
        flash(
            f"Error in getting the report data for {CCRM_CLINIC_GROUP_NAME}.",
            category="error",
        )
        return redirect(https_url("admin.wallet_tools"))


def _retrieve_zipped_us_reconciliation_reports():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Process a zip file of us fertility clinics to be downloaded in admin.
    """
    import zipfile

    data = request.form
    (
        start_time,
        end_time,
        start_time_str,
        end_time_str,
    ) = _gather_form_data_for_recon_reports(data)
    records, success = generate_us_fertility_reconciliation_report(
        True, start_time, end_time
    )
    if success:
        reports = _group_records_by_client_name(records)
        try:
            zip_buffer = io.BytesIO()
            zip_filename = f"{CLINIC_RECONCILIATION_FILE_PREFIX}_{US_FERTILITY_CLINIC_GROUP_NAME}_{start_time_str}_to_{end_time_str}.zip"
            with zipfile.ZipFile(
                zip_buffer, "a", zipfile.ZIP_DEFLATED, False
            ) as zip_file:
                for client_name, records in reports.items():
                    file_name = f"{CLINIC_RECONCILIATION_FILE_PREFIX}_{slugify(client_name)}_{start_time_str}_to_{end_time_str}.csv"
                    report = io.StringIO()

                    csvwriter = csv.writer(report, delimiter=",")
                    csvwriter.writerow(REPORT_FIELDS)
                    csvwriter.writerows(records)
                    report.seek(0)
                    zip_file.writestr(file_name, report.getvalue())

            zip_buffer.seek(0)
            response = Response(zip_buffer)

            response.headers["Content-Description"] = "File Transfer"
            response.headers["Cache-Control"] = "no-cache"
            response.headers["Content-Type"] = "application/zip"
            response.headers[
                "Content-Disposition"
            ] = f"attachment; filename={zip_filename}"

            return response
        except Exception as e:
            flash(
                f"Unable to generate file for {US_FERTILITY_CLINIC_GROUP_NAME}. Error: {e}",
                category="error",
            )
            return redirect(https_url("admin.wallet_tools"))
    else:
        flash(
            f"Error in getting the report data for {US_FERTILITY_CLINIC_GROUP_NAME}.",
            category="error",
        )
        return redirect(https_url("admin.wallet_tools"))


def _gather_form_data_for_recon_reports(data: ImmutableMultiDict) -> Tuple:
    start_date = _parse_date(data.get("start_date"))
    end_date = _parse_date(data.get("end_date"))

    end_time = int(end_date.timestamp())
    start_time = int(start_date.timestamp())

    start_time_str = datetime.datetime.fromtimestamp(start_time).strftime(
        REPORTING_TIMESTAMP_FORMAT
    )
    end_time_str = datetime.datetime.fromtimestamp(end_time).strftime(
        REPORTING_TIMESTAMP_FORMAT
    )
    return start_time, end_time, start_time_str, end_time_str


def _group_records_by_client_name(records: List) -> Dict:
    reports = defaultdict(list)
    for record in records:
        client_name = record[4]
        reports[client_name].append(record)
    return reports


@wallet.route("/handle_smp_rx_file_audit", methods=["POST"])
@login.login_required
def handle_smp_rx_file_audit():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    data = request.form
    download_audit = data.get("download_audit")
    file_date = (
        datetime.datetime.strptime(data.get("file_date"), "%Y-%m-%d")  # type: ignore[arg-type] # Argument 1 to "strptime" of "datetime" has incompatible type "Optional[Any]"; expected "str"
        if data.get("file_date")
        else None
    )
    if download_audit:
        try:
            report, error_message = download_scheduled_file_audit_report(file_date)
            if error_message:
                flash(f"Unable to process audit: {error_message}", category="error")
                return redirect(https_url("admin.wallet_tools"))

            report.seek(0)
            fp = io.BytesIO()
            fp.write(report.getvalue().encode())
            fp.seek(0)
            report.close()
            filename = f"smp_rx_audit_report_{file_date}.csv"
            return send_file(  # type: ignore[call-arg] # Unexpected keyword argument "download_name" for "send_file"
                fp,
                mimetype="text/csv",
                as_attachment=True,
                download_name=filename,
            )
        except Exception as e:
            flash(f"Unable to generate file. Error: {e}", category="error")
            return redirect(https_url("admin.wallet_tools"))

    return redirect(https_url("admin.wallet_tools"))


@wallet.route("/copy_wallet", methods=["POST"])
@login.login_required
def copy_wallet():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    source_wallet_id = request.form.get("source_wallet_id", None)
    target_ros_id = request.form.get("target_ros_id", None)
    create_prior_spend = bool(request.form.get("create_prior_spend", False))

    if None in (source_wallet_id, target_ros_id, create_prior_spend):
        log.error(
            "Params missing from request to copy wallet",
            source_wallet_id=source_wallet_id,
            target_ros_id=target_ros_id,
            create_prior_spend=create_prior_spend,
        )
        flash("Missing source_wallet_id and/or target_ros_id")
        return redirect(https_url("admin.wallet_tools"))

    source_wallet = db.session.query(ReimbursementWallet).get(source_wallet_id)
    target_ros = db.session.query(ReimbursementOrganizationSettings).get(target_ros_id)

    if not source_wallet:
        msg_str = "Could not find wallet based on provided ID"
        log.error(
            msg_str, source_wallet_id=source_wallet_id, target_ros_id=target_ros_id
        )
        flash(msg_str, category="error")
        return redirect(https_url("admin.wallet_tools"))

    if not target_ros:
        msg_str = "Could not find ROS based on provided ID"
        log.error(
            msg_str, source_wallet_id=source_wallet_id, target_ros_id=target_ros_id
        )
        flash(msg_str, category="error")
        return redirect(https_url("admin.wallet_tools"))

    wallet_repo = ReimbursementWalletRepository(session=db.session)
    requests_repo = ReimbursementRequestRepository(session=db.session)
    wallet_service = ReimbursementWalletService(
        requests_repo=requests_repo, wallet_repo=wallet_repo
    )

    try:
        created_dict = wallet_service.copy_and_persist_wallet_objs(
            source=source_wallet,
            target=target_ros,
            create_prior_spend_entry=create_prior_spend,
        )
    except Exception as exc:
        flash(
            f"Exception encountered while attempting to copy wallet: {str(exc)}",
            category="error",
        )
        return redirect(https_url("admin.wallet_tools"))

    flash("Successfully copied wallet to new ROS", category="success")
    return redirect(
        url_for("reimbursementwallet.edit_view", id=created_dict["wallet"].id)
    )


@wallet.route("/resubmit_alegeus_reimbursement", methods=["POST"])
@login.login_required
def resubmit_claim_alegeus_reimbursement():  # type: ignore[no-untyped-def]
    reimbursement_request_id = request.form["reimbursement_request_id"]

    # Check if ReimbursementClaim already exists
    existing_claim = ReimbursementClaim.query.filter(
        ReimbursementClaim.reimbursement_request_id == reimbursement_request_id
    ).first()

    if existing_claim:
        flash(
            f"Reimbursement claim already exists for this request (Claim ID: {existing_claim.id})",
            category="error",
        )
        return redirect(
            url_for("reimbursementrequest.edit_view", id=reimbursement_request_id)
        )

    rr_repository = ReimbursementRequestRepository()
    reimbursement_request = rr_repository.get_reimbursement_request_by_id(
        reimbursement_request_id=int(reimbursement_request_id)
    )

    # Get claim type from ReimbursementRequestToCostBreakdown
    rr_to_cb = ReimbursementRequestToCostBreakdown.query.filter(
        ReimbursementRequestToCostBreakdown.reimbursement_request_id
        == reimbursement_request_id
    ).first()

    if not rr_to_cb:
        flash("No cost breakdown found for this request", category="error")
        return redirect(
            url_for("reimbursementrequest.edit_view", id=reimbursement_request_id)
        )

    claim_type = rr_to_cb.claim_type

    try:
        create_direct_payment_claim_in_alegeus(
            wallet=reimbursement_request.wallet,
            reimbursement_request=reimbursement_request,
            claim_type=claim_type,
        )
        flash("Reimbursement request successfully submitted", category="success")
    except Exception as e:
        flash(f"Failed to create claim in Alegeus: {str(e)}", category="error")
        return redirect(
            url_for("reimbursementrequest.edit_view", id=reimbursement_request_id)
        )

    return redirect(
        url_for("reimbursementrequest.edit_view", id=reimbursement_request_id)
    )
