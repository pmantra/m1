import csv
import datetime
from io import StringIO
from typing import Iterable

from app import create_app
from eligibility import e9y
from utils.log import logger
from utils.payments import convert_cents_to_dollars
from wallet.constants import ALEGEUS_EDI_PW, ALEGEUS_TPAID, EdiTemplateName
from wallet.migrations.external.alegeus_employee_edi_transfer import (
    get_all_alegeus_user_wallets,
)
from wallet.models.constants import AlegeusAccountType, AlegeusCoverageTier
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.utils.alegeus.upload_to_ftp_bucket import upload_blob

log = logger(__name__)

fieldnames = [
    "record_type",
    "tpa_id",
    "employer_id",
    "employee_id",
    "coverage_tier_id",
    "plan_id",
    "account_type_code",
    "plan_start_date",
    "plan_end_date",
    "account_status",
    "auto_add_dependents",
    "annual_election_amount",
    "employee_pay_period_election",
    "employer_pay_period_election",
    "effective_date",
    "termination_date",
]

default_ic_record_rows = {
    "record_type": "IC",
    "tpa_id": ALEGEUS_TPAID,
    "account_type_code": "",
    "account_status": "2",
    "auto_add_dependents": "1",
    "employee_pay_period_election": "0.00",
    "employer_pay_period_election": "0.00",
    "termination_date": "",
}


def format_employees_for_ic_file(all_alegeus_wallets):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    filename = f"MAVENIC{datetime.datetime.now().strftime('%Y%m%d%H%M')}.csv"

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "IA",
            str(len(all_alegeus_wallets)),
            ALEGEUS_EDI_PW,
            EdiTemplateName.IMPORT,
            EdiTemplateName.RESULT,
            EdiTemplateName.EXPORT,
        ]
    )

    writer = csv.DictWriter(output, fieldnames=fieldnames)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "DictWriter[str]", variable has type "_writer")

    for alegeus_wallet in all_alegeus_wallets:
        org_employee = alegeus_wallet.organization_employee
        organization = alegeus_wallet.reimbursement_organization_settings.organization
        # note: this method was deprecated in favor of wallet_enablement_by_user_id
        wallet_enablement = e9y.wallet_enablement_by_id_search(  # type: ignore[attr-defined] # Module has no attribute "wallet_enablement_by_id_search"; maybe "wallet_enablement_by_org_identity_search"? #type: ignore[attr-defined] # Module has no attribute "wallet_enablement_by_id_search"; maybe "wallet_enablement_by_org_identity_search"?
            org_employee.eligibility_member_id
        )
        eligibility_date = wallet_enablement and wallet_enablement.eligibility_date
        eligibility_date = eligibility_date or org_employee.created_at.date()

        data_to_write = []
        # For HDHP plans
        hdhp_plans = alegeus_wallet.reimbursement_hdhp_plans
        for hdhp_plan in hdhp_plans:
            plan = hdhp_plan.reimbursement_plan
            account_type_code = plan.reimbursement_account_type.alegeus_account_type
            alegeus_coverage_tier = hdhp_plan.alegeus_coverage_tier

            if alegeus_coverage_tier == AlegeusCoverageTier.SINGLE:
                deductible = (
                    plan.reimbursement_plan_coverage_tier
                    and plan.reimbursement_plan_coverage_tier.single_amount
                )
            elif alegeus_coverage_tier == AlegeusCoverageTier.FAMILY:
                deductible = (
                    plan.reimbursement_plan_coverage_tier
                    and plan.reimbursement_plan_coverage_tier.family_amount
                )
            else:
                deductible = 0

            # According to our setup with Alegeus, DTR accounts should have an annual election amount of $0
            annual_election_amount = (
                0 if account_type_code == AlegeusAccountType.DTR.value else deductible
            )
            data_to_write.append(
                (
                    plan,
                    account_type_code,
                    annual_election_amount,
                    alegeus_coverage_tier,
                )
            )

        # For non-HDHP plans
        org_settings = alegeus_wallet.reimbursement_organization_settings
        allowed_categories = org_settings.allowed_reimbursement_categories
        for allowed_category in allowed_categories:
            request_category = allowed_category.reimbursement_request_category
            plan = request_category.reimbursement_plan
            account_type_code = (
                plan.reimbursement_account_type.alegeus_account_type if plan else ""
            )
            annual_election_amount = (
                allowed_category.reimbursement_request_category_maximum
                and convert_cents_to_dollars(
                    allowed_category.reimbursement_request_category_maximum
                )
            )
            data_to_write.append(
                (plan, account_type_code, annual_election_amount, None)
            )

        for (
            plan,
            account_type_code,
            annual_election_amount,
            alegeus_coverage_tier,
        ) in data_to_write:
            if plan:
                if eligibility_date and eligibility_date > plan.start_date:
                    effective_date = eligibility_date.strftime("%Y%m%d")
                else:
                    effective_date = ""

                row = {
                    **default_ic_record_rows,
                    "employer_id": organization.alegeus_employer_id,
                    "employee_id": org_employee.alegeus_id,
                    "coverage_tier_id": alegeus_coverage_tier
                    and alegeus_coverage_tier.name,
                    "plan_id": plan.alegeus_plan_id,
                    "account_type_code": account_type_code,
                    "plan_start_date": plan.start_date.strftime("%Y%m%d"),
                    "plan_end_date": plan.end_date.strftime("%Y%m%d"),
                    "annual_election_amount": annual_election_amount or 0,
                    "effective_date": effective_date,
                }
                writer.writerow(row)

    csv_contents = output.getvalue()

    return filename, csv_contents


def create_ic(wallets: Iterable[ReimbursementWallet] = None):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[assignment] # Incompatible default for argument "wallets" (default has type "None", argument has type "Iterable[ReimbursementWallet]")
    if not wallets:
        wallets = get_all_alegeus_user_wallets()
    return format_employees_for_ic_file(wallets)


if __name__ == "__main__":
    with create_app().app_context():
        filename, csv_contents = create_ic()
        try:
            upload_blob(csv_contents, filename)
        except Exception as e:
            log.info(f"There was an error uploading the blob {e}")
