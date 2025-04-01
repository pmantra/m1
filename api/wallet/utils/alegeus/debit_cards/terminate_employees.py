from __future__ import annotations

from datetime import datetime

from common import stats
from common.constants import Environment
from eligibility.e9y import grpc_service as e9y_service
from storage.connection import db
from utils.log import logger
from utils.mail import send_message
from wallet.alegeus_api import AlegeusApi, is_request_successful
from wallet.models.constants import AlegeusCardStatus, CardStatus
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_debit_card import (
    ReimbursementWalletDebitCard,
    map_alegeus_card_status_codes,
)
from wallet.utils.alegeus.enrollments.enroll_wallet import get_banking_info

metric_prefix = "api.wallet.utils.alegeus.debit_cards.terminate_employees"

log = logger(__name__)

PROGRAM_WALLET_OPS_EMAIL = "walletprocessing@mavenclinic.com"


def handle_terminated_employees(allowed_debit_card_ids: list | None = None) -> bool:
    """
    Finds employee with debit cards in the NEW or ACTIVE state and cross-references the Eligibility Service for
    terminated employees.  If record not found, set employee to terminated in Alegeus and Maven.

    @param allowed_debit_card_ids: A list of accepted debit card ids if manual intervention needed.
    """

    def tag_successful(successful: bool, reason: str | None = None) -> None:
        metric_name = f"{metric_prefix}.handle_terminated_employees"
        tags = []
        if successful:
            tags.append("success:true")
        else:
            tags.append("success:false")
            tags.append(f"reason:{reason}")
        stats.increment(
            metric_name=f"{metric_name}",
            pod_name=stats.PodNames.PAYMENTS_POD,
            tags=tags,
        )

    if Environment.current() == Environment.PRODUCTION:
        live_debit_cards = ReimbursementWalletDebitCard.query.filter(
            ReimbursementWalletDebitCard.card_status.in_(
                [CardStatus.NEW.value, CardStatus.ACTIVE.value]
            )
        ).all()
    elif allowed_debit_card_ids is not None:
        live_debit_cards = ReimbursementWalletDebitCard.query.filter(
            ReimbursementWalletDebitCard.card_status.in_(
                [CardStatus.NEW.value, CardStatus.ACTIVE.value]
            ),
            ReimbursementWalletDebitCard.id.in_(allowed_debit_card_ids),
        ).all()
    else:
        log.info(
            "Skipping handle_terminated_employees on non-production environment or empty allowed list."
        )
        return False

    terminated_employee_ids = []
    error_terminating_employees = []

    # api = AlegeusApi()
    try:
        for debit_card in live_debit_cards:
            wallet = debit_card.reimbursement_wallet
            employee_is_terminated = False

            # Check the e9y service for member.  If not found, proceed to terminate employee in Alegeus
            for user in wallet.all_active_users:
                wallet_enablement = e9y_service.wallet_enablement_by_user_id_search(
                    user_id=user.id
                )
                if wallet_enablement is None:
                    log.info(
                        "handle_terminated_employees wallet enablement not found for wallet.",
                        wallet_id=wallet.id,
                        user_id=user.id,
                    )
                    employee_is_terminated = True
                elif (
                    wallet_enablement.eligibility_end_date is not None
                    and wallet_enablement.eligibility_end_date
                    <= datetime.today().date()
                ):
                    log.info(
                        "handle_terminated_employees wallet enablement ended before today.",
                        wallet_id=wallet.id,
                        user_id=user.id,
                        eligibility_end_date=wallet_enablement.eligibility_end_date,
                    )
                    employee_is_terminated = True

                if employee_is_terminated:
                    # record member id for terminated employee
                    terminated_employee_ids.append(user.id)

                    # try terminating employee and setting debit to inactive in Alegeus
                    # termination_success = set_employee_to_terminated(api, wallet)
                    # if termination_success:
                    #     debit_success = update_debit_card_status(
                    #         api,
                    #         debit_card,
                    #         AlegeusCardStatus.TEMP_INACTIVE,
                    #         CardStatusReason.EMPLOYMENT_ENDED,
                    #     )
                    # if not termination_success or not debit_success:
                    #   # Record errored user, so we can manually terminate them. Continue processing the remaining records.
                    #     error_terminating_employees.append(wallet.user_id)
                    #     continue

    except Exception as e:
        log.exception(
            "handle_terminated_employees failed",
            error=e,
        )
        tag_successful(successful=False, reason="unexpected_error")
        raise e

    #  db.session.commit()
    log.info(
        f"handle_terminated_employees. Total terminations:{len(terminated_employee_ids)}, "
        f"Total terminations not updated:{len(error_terminating_employees)}"
    )

    send_terminated_email_report(terminated_employee_ids, error_terminating_employees)
    tag_successful(successful=True)
    return True


def set_employee_to_terminated(api: AlegeusApi, wallet: ReimbursementWallet) -> bool:
    """
    Sends the members' termination date to Alegeus.
    """
    # Set termination date in Alegeus to today's date
    termination_date = datetime.today()
    try:
        # Get the ACH account to send it back and avoid clearing it. Failure is okay.
        banking_info = get_banking_info(api, wallet)

        # Update existing alegeus record termination date.
        response = api.put_employee_services_and_banking(
            wallet=wallet,
            banking_info=banking_info,
            termination_date=termination_date,
        )
        if is_request_successful(response):
            return True
        else:
            log.error(
                "set_employee_to_terminated failed when calling put_employee_services_and_banking",
                wallet_id=wallet.id,
                user_id=wallet.employee_member.id,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "id"
            )
            return False
    except Exception as e:
        log.exception(
            "set_employee_to_terminated failed when calling put_employee_services_and_banking",
            wallet_id=wallet.id,
            error=e,
        )
        raise e


def update_debit_card_status(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    api: AlegeusApi,
    debit_card: ReimbursementWalletDebitCard,
    status_code: AlegeusCardStatus,
    status_code_reason=None,
) -> bool:
    """
    Calls the update the status of a debit card in Alegeus first,
    followed by updating the debit card status and reason in Maven.
    """
    wallet = debit_card.reimbursement_wallet
    try:
        update_debit_card_response = api.put_debit_card_update_status(
            wallet,
            debit_card.card_proxy_number,
            status_code,
        )
        if (
            is_request_successful(update_debit_card_response)
            and update_debit_card_response.json() is not None
        ):
            debit_card_details = update_debit_card_response.json()

            card_status, mapped_status_reason = map_alegeus_card_status_codes(
                debit_card_details.get("CardStatusCode")
            )
            debit_card.update_status(card_status, card_status_reason=status_code_reason)
            db.session.add(debit_card)
            return True
        else:
            log.error(
                "update_debit_card_status put_debit_card_update_status failed.",
                wallet_id=wallet.id,
            )
            return False
    except Exception as e:
        log.exception(
            "update_debit_card_status failed when calling put_debit_card_update_status",
            wallet_id=debit_card.reimbursement_wallet.id,
            error=e,
        )
        raise e


def send_terminated_email_report(all_terminated_ids, error_terminated_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Sends an email to notify operations that users have been updated to terminate. It also alerts
    if there were any errors during processing.
    """

    total_errors = len(error_terminated_ids)
    total_terminated_ids = len(all_terminated_ids)
    if total_terminated_ids > 0 or total_errors > 0:
        if total_errors == 0:
            email_text = (
                f"User ids for terminated employees found: {all_terminated_ids}."
                "Please manually check each user and take action to remedy the data or terminate the member."
            )
        else:
            email_text = (
                f"User ids for terminated employees found: {all_terminated_ids}. "
                f"An error occurred while terminating the user in Alegeus for the following user ids: {error_terminated_ids}. "
                "Please manually terminate these employees in Alegeus and update the debit card status in Admin to "
                "temporary inactive."
            )
        date = datetime.now().strftime("%Y-%m-%d")
        send_message(
            to_email=PROGRAM_WALLET_OPS_EMAIL,
            subject=f"Alegeus Terminated Employees Report for {date}.",
            text=email_text,
            internal_alert=True,
            production_only=True,
        )
