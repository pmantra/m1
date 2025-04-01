from datetime import datetime, timedelta

from models.profiles import PractitionerProfile
from payments.models.constants import PROVIDER_CONTRACTS_EMAIL
from payments.models.practitioner_contract import PractitionerContract
from payments.services.practitioner_contract import PractitionerContractService
from tasks.queues import job
from utils.log import logger
from utils.mail import send_message

log = logger(__name__)


@job
def export_practitioner_contracts() -> None:
    PractitionerContractService().export_data_to_csv()


@job
def report_missing_or_expiring_contracts() -> None:
    log.info("Looking for missing/expiring practitioner contracts")

    # Using sets to easily subtract one from another
    all_practitioner_ids = set()
    active_contracts_by_practitioner = {}
    future_contracts_by_practitioner = {}
    practitioner_ids_missing_contracts = set()
    practitioner_ids_expiring_contracts = set()
    today = datetime.utcnow().date()
    next_week = today + timedelta(days=7)

    practitioners = PractitionerProfile.query.filter(
        PractitionerProfile.active == 1
    ).all()
    for practitioner in practitioners:
        # Care advocates don't have contracts
        # Can't do with database because they could have multiple verticals
        if not practitioner.is_cx:
            all_practitioner_ids.add(practitioner.user_id)

    active_contracts = (
        PractitionerContract.query.filter(
            PractitionerContract.practitioner_id.in_(all_practitioner_ids),
            PractitionerContract.active == 1,
        )
        .order_by(PractitionerContract.practitioner_id)
        .all()
    )
    for active_contract in active_contracts:
        active_contracts_by_practitioner[
            active_contract.practitioner_id
        ] = active_contract

    # Missing contracts
    practitioner_ids_missing_contracts = all_practitioner_ids - set(
        active_contracts_by_practitioner.keys()
    )

    # Future contracts
    future_contracts = (
        PractitionerContract.query.filter(
            PractitionerContract.practitioner_id.in_(all_practitioner_ids),
            PractitionerContract.start_date > today,
        )
        .order_by(PractitionerContract.practitioner_id, PractitionerContract.start_date)
        .all()
    )
    for future_contract in future_contracts:
        future_contracts_by_practitioner[
            future_contract.practitioner_id
        ] = future_contract

    # Find expiring or missing contracts
    for prac_id, active_contract in active_contracts_by_practitioner.items():
        # No end date = no problem
        if not active_contract.end_date:
            continue
        # End date is close
        elif active_contract.end_date < next_week:
            # No future contract = problem
            if prac_id not in future_contracts_by_practitioner:
                practitioner_ids_expiring_contracts.add(prac_id)
            else:
                # Gap between contracts = problem
                future_contract = future_contracts_by_practitioner[prac_id]
                date_diff = future_contract.start_date - active_contract.end_date
                if date_diff.days > 1:
                    practitioner_ids_expiring_contracts.add(prac_id)

    if (
        not practitioner_ids_missing_contracts
        and not practitioner_ids_expiring_contracts
    ):
        return

    if practitioner_ids_missing_contracts and practitioner_ids_expiring_contracts:
        notification_title = "Providers with missing and expiring contracts"
    elif practitioner_ids_missing_contracts:
        notification_title = "Providers with missing contracts"
    else:
        notification_title = "Providers with expiring contracts"

    notification_messages = []
    if practitioner_ids_missing_contracts:
        log.warning(
            "Missing practitioner contracts",
            practitioner_ids=practitioner_ids_missing_contracts,
        )
        notification_text = f"The following providers have no active contract: {list(practitioner_ids_missing_contracts)}"
        notification_messages.append(notification_text)

    if practitioner_ids_expiring_contracts:
        log.warning(
            "Expiring practitioner contracts",
            practitioner_ids=practitioner_ids_expiring_contracts,
        )
        notification_text = f"The following providers have contracts that will expire soon: {list(practitioner_ids_expiring_contracts)}"
        notification_messages.append(notification_text)

    send_message(
        to_email=PROVIDER_CONTRACTS_EMAIL,
        subject=notification_title,
        text="\n".join(notification_messages),
        internal_alert=True,
        production_only=True,
    )
