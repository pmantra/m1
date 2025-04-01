from __future__ import annotations

import traceback
from datetime import datetime, timezone

from maven import feature_flags

from common import stats
from models.actions import ACTIONS, audit
from storage.connection import db
from tasks.queues import job
from utils import braze_events
from utils.log import logger
from wallet.config import use_alegeus_for_reimbursements
from wallet.constants import HISTORICAL_WALLET_FEATURE_FLAG, NUM_CREDITS_PER_CYCLE
from wallet.models.constants import (
    WALLET_QUALIFICATION_SERVICE_TAG,
    WALLET_QUALIFICATION_UPDATER_TAG,
    BenefitTypes,
    WalletState,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_credit import ReimbursementCycleCredits
from wallet.models.reimbursement_wallet_credit_transaction import (
    ReimbursementCycleMemberCreditTransaction,
)
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.services.payments import assign_payments_customer_id_to_wallet
from wallet.services.reimbursement_benefits import assign_benefit_id
from wallet.services.reimbursement_wallet_messaging import open_zendesk_ticket
from wallet.services.wallet_historical_spend import (
    INTERNAL_TRUST_WHS_URL,
    WalletHistoricalSpendService,
)
from wallet.utils.admin_helpers import FlashMessage, FlashMessageCategory
from wallet.utils.alegeus.enrollments.enroll_wallet import configure_wallet_in_alegeus
from wallet.utils.events import send_wallet_qualification_event

WQS_MONO_RQ_JOB = "wallet_qualification_service_mono_rq_job"

WALLET_APPLICATION_MANUAL_REVIEW_TAG = "customer-need-member_wallet_application_manual_wallet_qualification_application_review"

log = logger(__name__)


def handle_wallet_state_change(
    wallet: ReimbursementWallet,
    old_state: WalletState,
    headers: dict[str, str] | None = None,
) -> list[FlashMessage] | None:
    """
    After changing and committing a wallet, trigger this to audit, add the wallet channel, and send braze events
    """
    old_state = old_state and WalletState(old_state)
    new_state = wallet.state
    messages = []
    if old_state != new_state or wallet.reimbursement_hdhp_plans is not None:
        audit(
            action_type=ACTIONS.change_wallet_status,
            wallet_id=wallet.id,
            wallet_status=wallet.state.value,  # type: ignore[attr-defined] # "str" has no attribute "value"
        )
        # TODO: PAY-3437: Change to User ID and User ESP_ID for Braze refactor
        # Send braze events, and create alegeus_id for the organization employee
        if new_state == WalletState.QUALIFIED:
            messages = _handle_qualified_wallet(wallet, old_state, headers)
        elif new_state == WalletState.DISQUALIFIED:
            braze_events.wallet_state_disqualified(wallet)
    return messages


def _handle_qualified_wallet(
    wallet: "ReimbursementWallet",  # type: ignore  # Added quotes for forward reference
    old_state: "WalletState | None",  # type: ignore  # Added quotes for forward reference
    headers: dict[str, str] | None = None,
) -> list[FlashMessage]:
    log.info(
        "Attepting to perform _handle_qualified_wallet actions",
        wallet_id=f'"{wallet.id}"',
        old_state=str(old_state),
    )
    success = False
    messages = []
    # Assign a Benefit ID if there isn't one already (possible with
    # wallets that have been re-qualified then re-qualified)
    if not wallet.reimbursement_wallet_benefit:
        assign_benefit_id(wallet)

    if (
        not wallet.payments_customer_id
        and wallet.reimbursement_organization_settings.direct_payment_enabled
    ):
        res = assign_payments_customer_id_to_wallet(wallet, headers)  # type: ignore[arg-type] # Argument 2 to "assign_payments_customer_id_to_wallet" has incompatible type "Optional[Mapping[str, str]]"; expected "Mapping[str, str]"
        log.info(
            "Payment Customer ID assignment status",
            wallet_id=str(wallet.id),
            status=str(res),
        )

    if wallet.alegeus_id is None:
        wallet.alegeus_id = wallet._create_alegeus_id()
        log.info(
            "Assigned Alegeus ID to wallet.",
            wallet_id=str(wallet.id),
            alegeus_id=str(wallet.alegeus_id),
        )

    # Set up employee in WCA
    if not use_alegeus_for_reimbursements():
        send_wallet_qualification_event(wallet)
    else:
        try:
            success, messages = configure_wallet_in_alegeus(wallet)
            if not success:
                messages.append(
                    FlashMessage(
                        message="Unable to configure wallet in Alegeus.",
                        category=FlashMessageCategory.ERROR,
                    )
                )
                log.error(
                    "Unable to configure wallet in Alegeus",
                    messages=[fm.message for fm in messages],
                )
                wallet.state = old_state
                db.session.add(wallet)
            else:
                log.info(
                    "Successfully configured wallet in Alegeus",
                    wallet_id=str(wallet.id),
                    alegeus_id=str(wallet.alegeus_id),
                )
        except Exception as e:
            log.exception(
                "Unable to configure wallet in Alegeus",
                wallet_id=str(wallet.id),
                error=e,
                traceback=traceback.format_exc(),
            )
            messages.append(
                FlashMessage(
                    message=f"Unable to configure wallet in Alegeus: error {e}",
                    category=FlashMessageCategory.ERROR,
                )
            )
            # reset the state if there was an issue setting up in Alegeus
            wallet.state = old_state
            db.session.add(wallet)
            return messages

    # Check whether the wallet has cycle-based categories that have not been
    # loaded yet.
    # If so, then populate the wallet's credit balances.
    add_cycles_to_qualified_wallet(wallet)

    # Check for historic wallet spend
    if success:
        hss_success, error_messages = _invoke_historical_spend_service(wallet)
        messages.extend(error_messages)
        # reset the state if there was an issue processing a wallets historical spend
        if not hss_success:
            log.exception(
                "Unable to adjust historical spend for wallet.",
                wallet_id=str(wallet.id),
            )
            wallet.state = old_state
            db.session.add(wallet)
            return messages

    if success:
        send_wallet_qualification_event(wallet)

    return messages


@job("high_mem", service_ns="wallet", team_ns="benefits_experience")
def handle_qualification_of_wallet_created_by_wqs(wallet_id: int) -> int:
    stats.increment(
        metric_name="wallet.services.reimbursement_wallet_state_change.handle_qualification_of_wallet_created_by_wqs.execute_rq_for_qualification",
        pod_name=stats.PodNames.BENEFITS_EXP,
    )
    log.info(
        "WQS: RQ Job attempting to qualify PENDING WQS wallet.",
        wallet_id=str(wallet_id),
    )

    if (wallet := ReimbursementWallet.query.get(wallet_id)) is None:
        log.error("Wallet not found.", wallet_id=str(wallet_id))
        return 1

    if wallet.state != WalletState.PENDING:
        log.warn(
            "This function can only process wallets in the PENDING state.",
            wallet_id=str(wallet_id),
            wallet_state=str(wallet.state),
        )
        return 1

    if not wallet.note or WALLET_QUALIFICATION_SERVICE_TAG not in wallet.note:
        log.warn(
            "This function can only process wallets that contain the wqs tag in the wallet note",
            wallet_id=str(wallet_id),
            wallet_note=wallet.note,
            wqs_tag=WALLET_QUALIFICATION_SERVICE_TAG,
        )
        return 1

    if not _finalize_wallet_state(wallet):
        return 1

    return 0


def _finalize_wallet_state(wallet: ReimbursementWallet) -> bool:
    metric_name = "wallet.services.reimbursement_wallet_state_change.handle_qualification_of_wallet_created_by_wqs.qualification_success"
    try:
        # the wallet has to be set to qualified to adjust it in alegeus. BLECH! Not doing this will return a cryptic 403
        # It's sufficient to just do this in memory.
        old_state = wallet.state
        wallet.state = WalletState.QUALIFIED
        messages = _handle_qualified_wallet(
            wallet=wallet, old_state=old_state, headers={}
        )
        reason = "; ".join(m.message for m in messages)
        wallet_state = wallet.state

        log.info(
            "Qualification of a WQS created wallet - Result",
            wallet_id=str(wallet.id),
            reason=reason,
            wallet_state=str(wallet_state),
            wallet_note=wallet.note,
        )
        wallet.state = wallet_state
        if wallet_state == WalletState.QUALIFIED:
            wallet.note += f"{WALLET_QUALIFICATION_UPDATER_TAG}. Successfully auto-qualified the wallet; "
        elif wallet_state == WalletState.PENDING:
            wallet.note += (
                f"{WALLET_QUALIFICATION_UPDATER_TAG}. Manual Action needed. "
                f"Unable to auto-qualify the wallet. Reason:{reason}; "
            )
        qualified = wallet.state == WalletState.QUALIFIED
        # create a zendesk ticket if the wallet is not qualified. MUST do it before committing the transaction
        if not qualified:
            _create_zendesk_ticket(wallet, reason)
        log.info(
            "WQS: Wallet state and/or note have been updated and the wallet persisted to the DB.",
            wallet_id=str(wallet.id),
            reason=reason,
            wallet_state=str(wallet_state),
            qualified=qualified,
            wallet_note=wallet.note,
        )
        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.BENEFITS_EXP,
            tags=[f"success:{'true' if qualified else 'false'}"],
        )
        # return True if all steps in wallet qualification were successful. This does not imply that the wallet was
        # qualified, just that there were not exceptions during the process.
        to_return = True
    except Exception as e:
        db.session.rollback()
        log.exception(
            "An unexpected exception occurred during alegeus-wallet qualification synch or syncing with alegeus. "
            "No changes (except for wallet note) will be persisted to the database. Investigate urgently.",
            wallet_id=str(wallet.id),
            wallet_state=str(wallet.state),
            error=e,
            traceback=traceback.format_exc(),
            qualified=False,
        )
        reason = (
            f"Manual Action needed. Unable to auto-qualify the wallet. Reason:{e}; "
        )
        wallet.note += reason
        _create_zendesk_ticket(wallet, reason)
        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.BENEFITS_EXP,
            tags=["success:false"],
        )
        to_return = False
    finally:
        db.session.commit()
    return to_return


def add_cycles_to_qualified_wallet(wallet: ReimbursementWallet) -> None:
    """
    Checks whether the wallet has cycle-based categories which have previously loaded
    the wallet with credits upon qualification.

    If the wallet has cycle-based categories that have not been loaded, then we populate the wallet
    with credits according to the organization's allowed categories.
    """
    log.info("Starting process to add credits to a wallet.", wallet_id=str(wallet.id))
    wallet_reimbursement_organization_settings_id: int = (
        wallet.reimbursement_organization_settings_id
    )
    # First, determine whether the wallet is cycle-based
    # NOTE this query acts on ALL allowed categories for the ROS and not visible wallet categories
    org_allowed_cycle_based_categories: list[
        ReimbursementOrgSettingCategoryAssociation
    ] = (
        db.session.query(ReimbursementOrgSettingCategoryAssociation)
        .filter(
            ReimbursementOrgSettingCategoryAssociation.reimbursement_organization_settings_id
            == wallet_reimbursement_organization_settings_id,
            ReimbursementOrgSettingCategoryAssociation.benefit_type
            == BenefitTypes.CYCLE,
        )
        .all()
    )
    if not org_allowed_cycle_based_categories:
        log.info(
            "No cycle-based ReimbursementOrgSettingsCategoryAssociations,"
            " therefore not adding credits",
            wallet_id=str(wallet.id),
        )
        return

    wallet_id: int = wallet.id
    # Check whether this wallet has already been qualified and given categories before
    already_has_cycle_based_balance_entries: bool = (
        db.session.query(ReimbursementCycleCredits)
        .filter(ReimbursementCycleCredits.reimbursement_wallet_id == wallet_id)
        .count()
    ) > 0

    if not already_has_cycle_based_balance_entries:
        # The credits have not been populated yet, so we need to populate them.

        # Make sure to do this in one transaction. A partial failure
        # could result in only some of the categories being populated.
        # NOTE: datetime.now() is a disallowed pattern. This should be updated # noqa
        # as soon as possible. see lint_disallowed (or remove noqa) for more information.
        creation_time: datetime = datetime.now(timezone.utc)  # type: ignore[valid-type] # Module "datetime" is not valid as a type # noqa

        for category in org_allowed_cycle_based_categories:
            num_credits: int = NUM_CREDITS_PER_CYCLE * category.num_cycles

            balance_entry: ReimbursementCycleCredits = ReimbursementCycleCredits(
                reimbursement_wallet_id=wallet.id,
                reimbursement_organization_settings_allowed_category_id=category.id,
                amount=num_credits,
            )
            transaction: ReimbursementCycleMemberCreditTransaction = ReimbursementCycleMemberCreditTransaction(
                reimbursement_cycle_credits_id=balance_entry.id,
                # There is no affiliated reimbursement request for wallet qualification
                reimbursement_request_id=None,
                # This is a debit to the account not affiliated with any procedure,
                # so the reimbursement_wallet_global_procedures_id is NULL
                reimbursement_wallet_global_procedures_id=None,
                amount=num_credits,
                notes=f"Added {num_credits} credits for wallet qualification",
                created_at=creation_time,
            )
            db.session.add(balance_entry)
            db.session.add(transaction)
        log.info(
            "Added cycle-based credits and transactions for wallet.",
            wallet_id=str(wallet.id),
        )
    else:
        log.info("Wallet already has credits", wallet_id=str(wallet.id))


def _invoke_historical_spend_service(wallet: ReimbursementWallet) -> tuple[bool, list]:
    if not (
        feature_flags.bool_variation(HISTORICAL_WALLET_FEATURE_FLAG, default=False)
    ):
        log.info(
            "Historical spend adjustment has been skipped.", wallet_id=str(wallet.id)
        )
        return True, []
    try:
        historical_spend_service = WalletHistoricalSpendService(
            whs_base_url=INTERNAL_TRUST_WHS_URL
        )
        error_messages = historical_spend_service.process_historical_spend_wallets(
            file_id=None,
            reimbursement_organization_settings_id=wallet.reimbursement_organization_settings_id,
            wallet_ids=[wallet.id],
        )
        if error_messages:
            msg = "Error processing historical wallet spend. Wallet state does not need to be rolled back."
            log.error(msg, wallet_id=str(wallet.id), error_message=error_messages)
            error_messages = [
                FlashMessage(message=msg, category=FlashMessageCategory.ERROR)
            ]
        return not bool(error_messages), error_messages
    except Exception as e:
        log.exception(
            "Exception handling wallet historic spend updates. Wallet state must be rolled back",
            wallet_id=str(wallet.id),
            error=str(e),
        )
        error_messages = [
            FlashMessage(
                message=f"Error processing wallet historic spend entries. Please manually adjust. Error: {e}",
                category=FlashMessageCategory.ERROR,
            )
        ]
        return False, error_messages


def handle_wallet_settings_change(
    wallet: ReimbursementWallet,
) -> list[FlashMessage] | None:
    """
    Trigger this after certain wallet settings changes to update configuration in Alegeus
    """
    messages = []

    if use_alegeus_for_reimbursements():
        try:
            success, messages = configure_wallet_in_alegeus(wallet)

            if not success:
                log.error(
                    "Unable to configure wallet in Alegeus",
                    messages=[fm.message for fm in messages],
                )
        except Exception as e:
            log.exception("Unable to configure wallet in Alegeus", error=e)

    return messages


def _create_zendesk_ticket(wallet: ReimbursementWallet, reason: str) -> None:
    """
    Create the zendesk ticket and stamp it on the reimbursement_wallet_user. Does not commit an expects the caller to
    commit
    :param wallet: The wallet that failed qualification
    :param reason: The reason the wallet failed qualification
    """
    try:
        # this is at wallet qualification so safe to assume that there should be one and only one user.
        reimbursement_wallet_user: ReimbursementWalletUsers = (
            db.session.query(ReimbursementWalletUsers)
            .filter(
                ReimbursementWalletUsers.reimbursement_wallet_id == wallet.id,
                ReimbursementWalletUsers.user_id == wallet.member.id,
            )
            .one()
        )

        ticket_id = open_zendesk_ticket(
            reimbursement_wallet_user,
            content=reason,
            called_by=WQS_MONO_RQ_JOB,
            additional_tags=[WALLET_APPLICATION_MANUAL_REVIEW_TAG],
        )
        log.info(
            "Unable to Qualify wallet. Zendesk ticket created.",
            ticket_id=str(ticket_id),
            additional_tags=[WALLET_APPLICATION_MANUAL_REVIEW_TAG],
            content=reason,
            called_by=WQS_MONO_RQ_JOB,
            user_id=str(reimbursement_wallet_user.user_id),
            reimbursement_wallet_user_id=str(reimbursement_wallet_user.id),
        )
    except Exception as e:
        log.error(
            "Unable to create Zendesk ticket.",
            wallet_id=str(wallet.id),
            wallet_state=str(wallet.state),
            error=e,
            traceback=traceback.format_exc(),
        )
