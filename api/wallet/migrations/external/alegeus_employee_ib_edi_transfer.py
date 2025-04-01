import csv
import datetime
from io import StringIO
from typing import Iterable

from app import create_app
from eligibility import e9y
from utils.log import logger
from wallet.constants import (
    ALEGEUS_EDI_PW,
    ALEGEUS_TPAID,
    MAVEN_ADDRESS,
    EdiTemplateName,
)
from wallet.migrations.external.alegeus_employee_edi_transfer import (
    get_all_alegeus_user_wallets,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.utils.alegeus.upload_to_ftp_bucket import upload_blob

"""
This script is deprecated and should not be utilized. It references the deprecated ReimbursementWallet.user_id.
Instead, update the code to use ReimbursementWalletUsers if this functionality is required.
"""

log = logger(__name__)

fieldnames = [
    "record_type",
    "tpa_id",
    "employer_id",
    "employee_id",
    "last_name",
    "first_name",
    "middle_initial",
    "phone",
    "mobile",
    "address_1",
    "address_2",
    "city",
    "state",
    "zip",
    "country",
    "shipping_1",
    "shipping_2",
    "shipping_city",
    "shipping_state",
    "shipping_zip",
    "shipping_country",
    "email",
    "status",
    "eligibility_date",
    "reimbursement_method",
    "termination_date",
]

default_ib_record_rows = {
    "record_type": "IB",
    "tpa_id": ALEGEUS_TPAID,
    "phone": "",
    "mobile": "",
    "address_1": "",
    "address_2": "",
    "city": "",
    "state": "",
    "zip": "",
    "country": "",
    "shipping_1": "",
    "shipping_2": "",
    "shipping_city": "",
    "shipping_state": "",
    "shipping_zip": "",
    "shipping_country": "",
    "status": "2",
    "reimbursement_method": "0",
    "termination_date": "",
}


def format_employees_for_ib_file(all_alegeus_user_wallets):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    filename = f"MAVENIB{datetime.datetime.now().strftime('%Y%m%d%H%M')}.csv"

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
        user = alegeus_wallet.member
        org_employee = alegeus_wallet.organization_employee
        organization = alegeus_wallet.reimbursement_organization_settings.organization
        # note: this method was deprecated in favor of wallet_enablement_by_user_id
        wallet_enablement = e9y.wallet_enablement_by_id_search(  # type: ignore[attr-defined] # Module has no attribute "wallet_enablement_by_id_search"; maybe "wallet_enablement_by_org_identity_search"? #type: ignore[attr-defined] # Module has no attribute "wallet_enablement_by_id_search"; maybe "wallet_enablement_by_org_identity_search"?
            org_employee.eligibility_member_id
        )
        eligibility_date = wallet_enablement and wallet_enablement.eligibility_date
        eligibility_date = eligibility_date or org_employee.created_at.date()

        address = MAVEN_ADDRESS

        row = {
            **default_ib_record_rows,
            "employer_id": organization.alegeus_employer_id,
            "employee_id": org_employee.alegeus_id,
            "last_name": user.last_name,
            "first_name": user.first_name,
            "middle_initial": str(user.middle_name)[:1],
            "email": user.email,
            "eligibility_date": (
                eligibility_date and eligibility_date.strftime("%Y%m%d")
            )
            or "",
            "address_1": address.get("address_1", ""),
            "address_2": address.get("address_2", ""),
            "city": address.get("city", ""),
            "state": address.get("state", ""),
            "zip": address.get("zip", ""),
            "country": address.get("country", ""),
        }
        writer.writerow(row)

    csv_contents = output.getvalue()

    return filename, csv_contents


def create_ib(wallets: Iterable[ReimbursementWallet] = None):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[assignment] # Incompatible default for argument "wallets" (default has type "None", argument has type "Iterable[ReimbursementWallet]")
    if not wallets:
        wallets = get_all_alegeus_user_wallets()
    return format_employees_for_ib_file(wallets)


if __name__ == "__main__":
    with create_app().app_context():
        filename, csv_contents = create_ib()
        try:
            upload_blob(csv_contents, filename)
        except Exception as e:
            log.info(f"There was an error uploading the blob {e}")
