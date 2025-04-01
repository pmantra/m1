from __future__ import annotations

from datetime import datetime
from typing import Optional

from requests import HTTPError

from audit_log.utils import emit_audit_log_update
from authn.models.user import User
from common import stats
from models.profiles import Address
from storage.connection import db
from utils.braze_events import debit_card_mailed
from utils.data import normalize_phone_number
from utils.log import logger
from utils.service_owner_mapper import service_ns_team_mapper
from wallet import alegeus_api
from wallet.alegeus_api import is_request_successful
from wallet.models.constants import (
    AlegeusCardStatus,
    AlegeusDebitCardCountries,
    CardStatus,
    CardStatusReason,
    WalletUserStatus,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_debit_card import (
    ReimbursementWalletDebitCard,
    map_alegeus_card_status_codes,
)
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.tasks.alegeus_edi import upload_employee_demographics_ib_file_to_alegeus
from wallet.utils.alegeus.enrollments.enroll_wallet import get_banking_info
from wallet.utils.employee_dob import get_employee_health_profile_dob

log = logger(__name__)

metric_prefix = "api.wallet.utils.alegeus.debit_cards.manage"


def request_debit_card(wallet: ReimbursementWallet, user: User | None = None) -> bool:
    def tag_successful(
        successful: bool,
        reason: str | None = None,
        end_point: str | None = None,
    ) -> None:
        metric_name = f"{metric_prefix}.request_debit_card"
        if successful:
            tags = ["success:true"]
        else:
            tags = ["success:false", f"reason:{reason}", f"end_point:{end_point}"]

        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.PAYMENTS_POD,
            tags=tags,
        )

    api = alegeus_api.AlegeusApi()

    try:
        issue_response = api.post_issue_new_card(wallet)

        if (
            alegeus_api.is_request_successful(issue_response)
            and issue_response.json() is not None
        ):

            card_issue_data = issue_response.json()

            debit_card = ReimbursementWalletDebitCard(
                reimbursement_wallet_id=wallet.id,
                card_proxy_number=card_issue_data.get("CardProxyNumber"),
                card_last_4_digits=card_issue_data.get("CardLast4Digits"),
                card_status=CardStatus.NEW,
                card_status_reason=CardStatusReason.NONE,
            )

            # The card issuance response does not have all of the metadata needed to create the
            # card object. Attempt to fill them in, but do not error out if there's a failure.
            # These fields can be updated later when syncing card status.
            details_response = api.get_debit_card_details(
                wallet, issue_response.json().get("CardProxyNumber")
            )
            if (
                alegeus_api.is_request_successful(details_response)
                and details_response.json() is not None
            ):
                card_details_data = details_response.json()

                card_status, card_status_reason = map_alegeus_card_status_codes(
                    card_details_data.get("CardStatusCode")
                )
                debit_card.card_status = card_status
                debit_card.card_status_reason = card_status_reason

                if card_details_data.get("CreationDate"):
                    try:
                        debit_card.created_date = datetime.strptime(
                            card_details_data.get("CreationDate"), "%Y%m%d"
                        ).date()
                    except ValueError:
                        log.error(
                            f"Unable to parse debit card creation date for wallet: {wallet.id}"
                        )
                if card_details_data.get("IssueDate"):
                    try:
                        debit_card.issued_date = datetime.strptime(
                            card_details_data.get("IssueDate"), "%Y%m%d"
                        ).date()
                    except ValueError:
                        log.error(
                            f"Unable to parse debit card issue date for wallet: {wallet.id}"
                        )
            else:
                log.error(
                    f"Unable to read debit card details for wallet: {wallet.id}, Alegeus request failed."
                )
                tag_successful(
                    False,
                    reason="alegeus_api_failure",
                    end_point="post_issue_new_card",
                )

            # Set the current card on the wallet
            wallet.debit_card = debit_card
            db.session.add(debit_card)
            db.session.add(wallet)
            db.session.commit()

            tag_successful(True)
            # If no user was specified, then we inform every active user associated with the wallet.
            if user is None:
                all_active_users = (
                    db.session.query(User)
                    .join(
                        ReimbursementWalletUsers,
                        ReimbursementWalletUsers.user_id == User.id,
                    )
                    .filter(
                        ReimbursementWalletUsers.reimbursement_wallet_id == wallet.id,
                        ReimbursementWalletUsers.status == WalletUserStatus.ACTIVE,
                    )
                    .all()
                )
                log.info(
                    "Preparing to send debit_card_mailed notifications.",
                    user_ids=", ".join(str(u.id) for u in all_active_users),
                )
                for active_user in all_active_users:
                    debit_card_mailed(active_user)
            else:
                log.info(
                    "Preparing to send debit_card_mailed notifications.",
                    user_id=str(user.id),
                )
                debit_card_mailed(user)
            return True
        else:
            log.error(
                f"Unable to create debit card for wallet: {wallet.id}, Alegeus request failed."
            )

            tag_successful(
                successful=False,
                reason="alegeus_api_failure",
                end_point="post_issue_new_card",
            )
    except Exception as e:
        log.exception(f"Unable to create debit card for wallet: {wallet.id}", error=e)
        tag_successful(
            successful=False,
            reason="exception",
            end_point="post_issue_new_card",
        )

    return False


def report_lost_stolen_debit_card(wallet: ReimbursementWallet) -> bool:
    def tag_successful(
        successful: bool,
        reason: str | None = None,
        end_point: str | None = None,
    ) -> None:
        metric_name = f"{metric_prefix}.report_lost_stolen_debit_card"
        tags = []
        if successful:
            tags.append("success:true")
        else:
            tags.append("success:false")
            tags.append(f"reason:{reason}")
            tags.append(f"end_point:{end_point}")

        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.PAYMENTS_POD,
            tags=tags,
        )

    api = alegeus_api.AlegeusApi()

    try:
        report_debit_card_response = api.put_debit_card_update_status(
            wallet,
            wallet.debit_card.card_proxy_number,
            AlegeusCardStatus.LOST_STOLEN,
        )
        if (
            alegeus_api.is_request_successful(report_debit_card_response)
            and report_debit_card_response.json() is not None
        ):
            debit_card_details = report_debit_card_response.json()

            card_status, card_status_reason = map_alegeus_card_status_codes(
                debit_card_details.get("CardStatusCode")
            )
            # Update debit card
            debit_card = wallet.debit_card
            debit_card.card_status = card_status
            debit_card.card_status_reason = card_status_reason

            emit_audit_log_update(wallet)
            db.session.add(debit_card)
            db.session.commit()

            tag_successful(True)
            return True
        else:
            log.error(
                f"Unable to update debit card status to lost/stolen for wallet: {wallet.id}, Alegeus request failed."
            )

            tag_successful(
                successful=False,
                reason="alegeus_api_failure",
                end_point="put_debit_card_update_status",
            )
    except Exception as e:
        log.exception(
            f"Unable to update debit card status for wallet: {wallet.id}", error=e
        )
        tag_successful(
            successful=False,
            reason="exception",
            end_point="put_debit_card_update_status",
        )

    return False


def update_alegeus_demographics_for_debit_card(
    wallet: ReimbursementWallet, user_id: int, address: Optional[Address]
) -> bool:
    """
    Update the Alegeus employee information that is only set for members with a debit card
    """

    def tag_successful(
        successful: bool, reason: Optional[str] = None, end_point: Optional[str] = None
    ) -> None:
        metric_name = f"{metric_prefix}.update_alegeus_demographics_for_debit_card"
        if successful:
            tags = ["success:true"]
        else:
            tags = ["success:false", f"reason:{reason}", f"end_point:{end_point}"]
        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.PAYMENTS_POD,
            tags=tags,
        )

    api = alegeus_api.AlegeusApi()

    # Get Employee DOB and validate. Fallback to eligibility DOB in case we don't have it in our member profile
    employee_dob = get_employee_health_profile_dob(wallet)
    if not employee_dob:
        first_name, last_name, employee_dob = wallet.get_first_name_last_name_and_dob()
        if not employee_dob:
            log.error(
                f"Unable to find employee date of birth from health profile or e9y for wallet: {wallet.id}"
            )
            tag_successful(
                successful=False,
                reason="no_employee_health_profile_date_of_birth",
            )
            return False

    # Get member address and validate. Ensure country is US/CA
    # TODO: PAY-3437
    if not address:
        log.exception(
            "Unable to update address for user - missing address",
            user_id=user_id,
            wallet_id=wallet.id,
        )
        tag_successful(
            successful=False,
            reason="no_address",
        )
        return False

    if address.country not in AlegeusDebitCardCountries.ALL.value:
        log.exception(
            "Unable to update address - invalid country",
            user_id=user_id,
            wallet_id=wallet.id,
        )
        tag_successful(
            successful=False,
            reason="invalid_member_country",
        )
        return False

    if address.country == AlegeusDebitCardCountries.CA.value:
        # Don't send member address parameter to demographics update. This will have us fallback
        # To Maven's default address, and we'll send the shipping address through EDI IB instead.
        log.info(f"EDI IB demographics update for wallet: {wallet.id}")
        service_ns_tag = "wallet"
        team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
        upload_employee_demographics_ib_file_to_alegeus.delay(
            wallet.id, user_id, service_ns=service_ns_tag, team_ns=team_ns_tag
        )
        address = None

    try:
        # Get the ACH account to send it back and avoid clearing it. Failure is okay.
        banking_info = get_banking_info(api, wallet)

        # Update existing alegeus record with employee dob, new address, new first name, new last name.
        res = api.put_employee_services_and_banking(
            wallet=wallet,
            banking_info=banking_info,
            member_address=address,
            employee_dob=employee_dob,
        )
        if not alegeus_api.is_request_successful(res):
            tag_successful(
                False,
                reason="alegeus_api_failure",
                end_point="put_employee_services_and_banking",
            )
            raise HTTPError("Alegeus Request put_employee_services_and_banking failed")
        return True
    except Exception as e:
        log.exception(
            "Unable to update alegeus address, first name, or last name for wallet when calling "
            f"put_employee_services_and_banking: {wallet.id}",
            error=e,
        )
        tag_successful(
            successful=False,
            reason="exception",
            end_point="put_employee_services_and_banking",
        )
        return False


def add_phone_number_to_alegeus(wallet: ReimbursementWallet, user: User) -> bool:
    def tag_successful(
        successful: bool,
        reason: Optional[str] = None,
        end_point: Optional[str] = None,
    ) -> None:
        metric_name = f"{metric_prefix}.add_phone_number_to_alegeus"
        if successful:
            tags = ["success:true"]
        else:
            tags = ["success:false", f"reason:{reason}", f"end_point:{end_point}"]

        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.PAYMENTS_POD,
            tags=tags,
        )

    api = alegeus_api.AlegeusApi()
    user_phone_number = user.member_profile and user.member_profile.phone_number

    if not user_phone_number:
        log.error(f"Unable to find member phone number for wallet: {wallet.id}")
        tag_successful(
            successful=False,
            reason="no_member_phone_number",
        )
        return False

    try:
        res = normalize_phone_number(user_phone_number, None)
        country_code = res[1].country_code

        if country_code != 1:
            log.error(
                f"Member phone number is not sent to Alegeus, country code {country_code} is not US/CA"
            )
            tag_successful(successful=False, reason="alegeus_request_not_sent")
            return False

        normalized_phone_number = res[1].national_number

        # Add member phone number to alegeus record.
        response = api.post_add_employee_phone_number(
            wallet=wallet,
            phone_number=normalized_phone_number,
        )

        if alegeus_api.is_request_successful(response):
            tag_successful(successful=True)
            return True
        else:
            log.error(
                "Unable to add user phone number to alegeus record. Alegeus request failed.",
                user_id=user.id,
                wallet_id=wallet.id,
            )
            tag_successful(
                successful=False,
                reason="alegeus_api_failure",
                end_point="post_add_employee_phone_number",
            )
    except Exception as e:
        log.exception(
            "Unable to add phone number to alegeus for wallet when calling "
            f"post_add_employee_phone_number: {wallet.id}",
            error=e,
        )
        tag_successful(
            successful=False,
            reason="exception",
            end_point="post_add_employee_phone_number",
        )

    return False


def remove_phone_number_from_alegeus(
    wallet: ReimbursementWallet, phone_number: str
) -> bool:
    def tag_successful(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        successful: bool,
        reason: str = None,  # type: ignore[assignment] # Incompatible default for argument "reason" (default has type "None", argument has type "str")
        end_point: str = None,  # type: ignore[assignment] # Incompatible default for argument "end_point" (default has type "None", argument has type "str")
    ):
        metric_name = f"{metric_prefix}.remove_phone_number_from_alegeus"
        tags = []
        if successful:
            tags.append("success:true")
        else:
            tags.append("success:false")
            tags.append(f"reason:{reason}")
            tags.append(f"end_point:{end_point}")

        stats.increment(
            metric_name=f"{metric_name}",
            pod_name=stats.PodNames.PAYMENTS_POD,
            tags=tags,
        )

    api = alegeus_api.AlegeusApi()

    try:
        res = normalize_phone_number(phone_number, None)
        normalized_phone_number = res[1].national_number
        country_code = res[1].country_code
        phone_nums = api.get_member_phone_numbers(wallet=wallet)
        if is_request_successful(phone_nums) and len(phone_nums.json()) > 0:
            has_phone_num = False
            for num in phone_nums.json():
                if num["PhoneNumber"] == f"{country_code}{normalized_phone_number}":
                    has_phone_num = True
                    break
            if has_phone_num:
                response = api.delete_remove_employee_phone_number(
                    wallet=wallet,
                    phone_number=normalized_phone_number,
                )

                if alegeus_api.is_request_successful(response):
                    tag_successful(successful=True)
                    return True
                else:
                    log.error(
                        f"Unable to remove member phone number from alegeus record : {wallet.id}, Alegeus request failed."
                    )
                    tag_successful(
                        successful=False,
                        reason="alegeus_api_failure",
                        end_point="delete_remove_employee_phone_number",
                    )
            else:
                log.error(
                    f"Unable to find a matching phone number against Alegeus records: {wallet.id}"
                )
        else:
            log.error(
                f"Unable to retrieve member phone number(s) from alegeus record : {wallet.id}, Alegeus request failed."
            )

            tag_successful(
                successful=False,
                reason="alegeus_api_failure",
                end_point="get_member_phone_numbers",
            )
    except Exception as e:
        log.exception(
            "Unable to remove phone number from alegeus for wallet when calling "
            f"remove_phone_number_from_alegeus: {wallet.id}",
            error=e,
        )
        tag_successful(
            successful=False,
            reason="exception",
            end_point="get_member_phone_numbers",
        )

    return False
