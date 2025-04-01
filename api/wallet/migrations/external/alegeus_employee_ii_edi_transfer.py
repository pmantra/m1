import csv
import datetime
from io import StringIO
from typing import Iterable

from app import create_app
from storage.connection import db
from utils.log import logger
from utils.payments import convert_cents_to_dollars
from wallet.constants import ALEGEUS_EDI_PW, ALEGEUS_TPAID, EdiTemplateName
from wallet.migrations.external.alegeus_employee_edi_transfer import (
    get_all_alegeus_user_wallets,
)
from wallet.models.constants import AlegeusClaimStatus, ReimbursementRequestState
from wallet.models.reimbursement import ReimbursementClaim
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.utils.alegeus.upload_to_ftp_bucket import upload_blob

log = logger(__name__)

fieldnames = [
    "record_type",
    "tpa_id",
    "employer_id",
    "employee_id",
    "plan_id",
    "account_type_code",
    "merchant_name",
    "date_of_service_from",
    "date_of_service_to",
    "approved_claim_amount",
    "reimbursement_method",
    "plan_start_date",
    "plan_end_date",
    "enforce_amount_effective_dates",
    "enforce_participant_eligibility_dates",
    "note",
    "tracking_number",
]

default_ii_record_rows = {
    "record_type": "II",
    "tpa_id": ALEGEUS_TPAID,
    "reimbursement_method": 0,
    "enforce_amount_effective_dates": "0",
    "enforce_participant_eligibility_dates": "0",
    "note": f"Conversion Account Balance {datetime.datetime.now().year}",
}


def format_employees_for_ii_file(all_alegeus_user_wallets):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    filename = f"MAVENII{datetime.datetime.now().strftime('%Y%m%d%H%M')}.csv"

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "IA",
            str(len(all_alegeus_user_wallets)),
            ALEGEUS_EDI_PW,
            EdiTemplateName.IMPORT,
            EdiTemplateName.RESULT,
            EdiTemplateName.EXPORT,
        ]
    )

    writer = csv.DictWriter(output, fieldnames=fieldnames)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "DictWriter[str]", variable has type "_writer")

    for alegeus_wallet in all_alegeus_user_wallets:
        org_employee = alegeus_wallet.organization_employee
        organization = alegeus_wallet.reimbursement_organization_settings.organization
        hdhp_plans = alegeus_wallet.reimbursement_hdhp_plans

        data_to_write = []

        # For HDHP plans
        for hdhp_plan in hdhp_plans:
            plan = hdhp_plan.reimbursement_plan
            if plan and plan.category:
                account_type_code = (
                    plan.reimbursement_account_type
                    and plan.reimbursement_account_type.alegeus_account_type
                )
                requests = plan.category.reimbursement_requests

                for request in requests:
                    # We will only be submitting ReimbursementRequests that have already been Reimbursed via the EDI
                    if request.state == ReimbursementRequestState.REIMBURSED:
                        data_to_write.append((plan, account_type_code, request))

        # For non HDHP plans
        for request in alegeus_wallet.reimbursement_requests:
            # We will only be submitting ReimbursementRequests that have already been Reimbursed via the EDI
            if request.state == ReimbursementRequestState.REIMBURSED:
                category = request.category
                if category and category.reimbursement_plan:
                    plan = category.reimbursement_plan
                    account_type_code = (
                        plan.reimbursement_account_type
                        and plan.reimbursement_account_type.alegeus_account_type
                    )

                    data_to_write.append((plan, account_type_code, request))

        for plan, account_type_code, request in data_to_write:
            claim_amount = convert_cents_to_dollars(request.amount)
            new_claim = ReimbursementClaim(
                reimbursement_request=request,
                amount=claim_amount,
                status=AlegeusClaimStatus.PAID.value,
            )
            new_claim.create_alegeus_claim_id()

            row = {
                **default_ii_record_rows,
                "employer_id": organization.alegeus_employer_id,
                "employee_id": org_employee.alegeus_id,
                "plan_id": plan.alegeus_plan_id,
                "account_type_code": account_type_code,
                "merchant_name": request.service_provider,
                "date_of_service_from": request.service_start_date.strftime("%Y%m%d"),
                "date_of_service_to": request.service_start_date.strftime("%Y%m%d"),
                "approved_claim_amount": claim_amount,
                "plan_start_date": plan.start_date.strftime("%Y%m%d"),
                "plan_end_date": plan.end_date.strftime("%Y%m%d"),
                "tracking_number": new_claim.alegeus_claim_id,
            }
            writer.writerow(row)
            db.session.add(new_claim)
    db.session.commit()

    csv_contents = output.getvalue()

    return filename, csv_contents


def create_ii(wallets: Iterable[ReimbursementWallet] = None):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[assignment] # Incompatible default for argument "wallets" (default has type "None", argument has type "Iterable[ReimbursementWallet]")
    if not wallets:
        wallets = get_all_alegeus_user_wallets()
    return format_employees_for_ii_file(wallets)


if __name__ == "__main__":
    with create_app().app_context():
        filename, csv_contents = create_ii()
        try:
            upload_blob(csv_contents, filename)
        except Exception as e:
            log.info(f"There was an error uploading the blob {e}")
