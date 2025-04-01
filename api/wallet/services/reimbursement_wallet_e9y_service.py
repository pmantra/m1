from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
from json import JSONDecodeError
from typing import Iterator, List, Optional, Tuple, Union, cast

import pytz
from dateutil.relativedelta import relativedelta
from requests import Response
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from typing_extensions import TypeGuard

from authn.models.user import User
from common import stats
from cost_breakdown.errors import CreateDirectPaymentClaimErrorResponseException
from eligibility import get_verification_service
from eligibility.e9y import EligibilityVerification
from eligibility.e9y import model as e9y_model
from models.profiles import Address
from storage.connector import RoutingSession, RoutingSQLAlchemy
from utils.launchdarkly import allow_cycle_currency_switch_process
from utils.log import logger
from utils.payments import convert_cents_to_dollars
from wallet.alegeus_api import AlegeusApi, is_request_successful
from wallet.models.constants import (
    BenefitTypes,
    ChangeType,
    EligibilityLossRule,
    ReimbursementRequestState,
    ReimbursementRequestType,
    SyncIndicator,
    WalletState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.reimbursement import (
    ReimbursementClaim,
    ReimbursementPlan,
    ReimbursementRequest,
    ReimbursementRequestCategory,
    ReimbursementRequestCategoryExpenseTypes,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_e9y_blacklist import (
    ReimbursementWalletBlacklist,
)
from wallet.models.reimbursement_wallet_eligibility_sync import (
    ReimbursementWalletEligibilitySyncMeta,
)
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.services.currency import DEFAULT_CURRENCY_CODE, CurrencyService
from wallet.services.reimbursement_wallet_benefit_type_converter import (
    ReimbursementWalletBenefitTypeConverter,
)
from wallet.utils.alegeus.claims.create import (
    get_reimbursement_account_from_request_and_wallet,
)
from wallet.utils.alegeus.enrollments.enroll_wallet import (
    configure_wallet_allowed_category,
)
from wallet.utils.payment_ops import (
    NoEligibilityPaymentOpsZendeskTicket,
    ROSChangePaymentOpsZendeskTicket,
)

log = logger(__name__)


BASE_METRIC_NAME = "wallet_e9y_service"


class WalletProcessingError(Exception):
    def __init__(self, message: str, wallet_id: int) -> None:
        self.message = message
        self.wallet_id = wallet_id
        super().__init__(self.message)


class WalletEligibilityService:
    """
    A service class responsible for managing reimbursement wallets state with eligibility change

    This service handles various operations related to wallet eligibility, including:
    - Checking and updating wallet eligibility status
    - Managing wallet states (RUNOUT, DISQUALIFIED, etc.)
    - Handling changes in Reimbursement Organization Settings (ROS)
    - Processing dependent users
    - Interacting with external systems (Alegeus API, Payment Ops)

    The main entry point for eligibility processing is the `process_wallet` method,
    which performs a series of checks and updates on a given wallet.

    This service is designed to be used in conjunction with periodic eligibility
    checks (e.g., cron jobs) or on-demand eligibility verifications.

    Usage:
        service = WalletEligibilityService(db)
        sync_meta = service.process_wallet(wallet, sync_indicator)

    Note:
    - This service requires a database session to perform its operations.
    - It interacts with external services like e9y and Alegeus, so proper
      configuration of these services is necessary for full functionality.

    Attributes:
        db (db): The connector's db.
        e9y_service (EnterpriseVerificationService): Service for eligibility verification.
        alegeus_api (AlegeusApi): API client for interacting with Alegeus.
        dry_run (bool): stateless run for a given wallet
        bypass_alegeus (bool): whether we want to send request to alegeus, mainly used for testing with
    """

    def __init__(
        self,
        db: RoutingSQLAlchemy,
        dry_run: bool = False,
        bypass_alegeus: bool = False,
    ):
        self.db = db
        self.e9y_service = get_verification_service()
        self.currency_service = CurrencyService()
        self.alegeus_api = AlegeusApi()
        self.dry_run = dry_run
        self.bypass_alegeus = bypass_alegeus

    @contextmanager
    def _fresh_session(self) -> Iterator[RoutingSession]:
        """
        Creates a fresh session for database operations with proper cleanup.
        Note: Does NOT handle commits - that should be done by the caller
        to respect dry_run settings.
        """
        session = self.db.session()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def create_sync_meta(
        wallet: ReimbursementWallet,
        change_type: ChangeType,
        eligibility_record: EligibilityVerification,
        new_ros: Optional[ReimbursementOrganizationSettings] = None,
        sync_indicator: Optional[SyncIndicator] = SyncIndicator.CRON_JOB,
        old_ros_id: Optional[int] = None,
    ) -> ReimbursementWalletEligibilitySyncMeta:
        """
        Create a ReimbursementWalletEligibilitySyncMeta object with the current state of the wallet.

        Args:
            wallet (ReimbursementWallet): The wallet being processed.
            change_type (ChangeType): The type of change occurring.
            eligibility_record (EligibilityVerification): The eligibility record for the wallet's user.
            new_ros (Optional[ReimbursementOrganizationSettings]): The new ROS, if applicable.
            sync_indicator (Optional[SyncIndicator]): The indicator of how the sync was initiated.
            old_ros_id: (Optional[int]): old ros id

        Returns:
            ReimbursementWalletEligibilitySyncMeta: An object containing metadata about the sync operation.
        """
        if ChangeType.RUNOUT == change_type:
            latest_ros_id = None
        elif ChangeType.DISQUALIFIED == change_type:
            latest_ros_id = None
        else:
            latest_ros_id = new_ros.id

        sync_meta = ReimbursementWalletEligibilitySyncMeta(
            wallet_id=wallet.id,
            sync_time=datetime.utcnow(),
            sync_initiator=sync_indicator,
            change_type=change_type,
            # this should be current ros's start_date
            previous_end_date=None,
            latest_end_date=eligibility_record.effective_range.upper if eligibility_record and eligibility_record.effective_range else None,  # type: ignore[arg-type]
            previous_ros_id=old_ros_id or wallet.reimbursement_organization_settings_id,
            latest_ros_id=latest_ros_id,
            user_id=wallet.employee_member.id if wallet.employee_member else None,  # type: ignore[arg-type]
        )
        dependent_ids = [
            user.id
            for user in wallet.all_active_users
            if user.id != wallet.employee_member.id
        ]
        sync_meta.dependents_ids = dependent_ids
        return sync_meta

    def set_wallet_to_runout(
        self,
        wallet: ReimbursementWallet,
        eligibility_record: EligibilityVerification,
        session: RoutingSession,
        eligibility_term_date: bool = True,
        sync_indicator: Optional[SyncIndicator] = SyncIndicator.CRON_JOB,
    ) -> ReimbursementWalletEligibilitySyncMeta:
        """
        Set the wallet state to RUN OUT and create a sync meta object.

        Args:
            wallet (ReimbursementWallet): The wallet to set to RUN OUT state.
            eligibility_record (EligibilityVerification): The eligibility record for the wallet's user.
            session (RoutingSession): A fresh session obj
            eligibility_term_date (bool): If eligbility record contain `effective_range.upper` for term_date
            sync_indicator (Optional[SyncIndicator]): The indicator of how the sync was initiated.

        Returns:
            ReimbursementWalletEligibilitySyncMeta: An object containing metadata about the sync operation.
        """
        sync_meta = self.create_sync_meta(
            wallet,
            ChangeType.RUNOUT,
            eligibility_record,
            sync_indicator=sync_indicator,
        )
        wallet.state = WalletState.RUNOUT
        runout_period = wallet.reimbursement_organization_settings.run_out_days
        loss_rule = wallet.reimbursement_organization_settings.eligibility_loss_rule
        if not loss_rule:
            log.error(
                f"No loss rule configured for wallet {wallet} with ros {wallet.reimbursement_organization_settings_id}"
            )
            stats.increment(
                metric_name=f"{BASE_METRIC_NAME}.set_wallet_to_runout",
                pod_name=stats.PodNames.BENEFITS_EXP,
                tags=["error_type:no_loss_rule_configured"],
            )
            raise ValueError(
                f"No loss rule configured for ros: {wallet.reimbursement_organization_settings_id}"
            )
        else:
            # Todo: in the future, eligbility_record will be the truth for this info
            # For the case that org is terminated and no term date information on eligbility record part
            # we will try use ROS.ended_at first, organization.term_date second
            if not eligibility_term_date:
                if wallet.reimbursement_organization_settings.ended_at:
                    termination_date = (
                        wallet.reimbursement_organization_settings.ended_at
                    )
                elif wallet.employee_member.organization_v2.terminated_at:
                    termination_date = (
                        wallet.employee_member.organization_v2.terminated_at
                    )
                else:
                    # This is for the case that user is still valid for the org but choose to drop out for wallet
                    if EligibilityLossRule.TERMINATION_DATE == loss_rule:
                        termination_date = eligibility_record.effective_range.lower
                    elif (
                        EligibilityLossRule.END_OF_MONTH_FOLLOWING_TERMINATION
                        == loss_rule
                    ):
                        termination_date = self.get_last_day_of_month(
                            cast(date, eligibility_record.effective_range.lower)
                        )
                    else:
                        raise ValueError(
                            f"No termination date found for wallet: {wallet.id}"
                        )
            else:
                if EligibilityLossRule.TERMINATION_DATE == loss_rule:
                    termination_date = eligibility_record.effective_range.upper
                elif (
                    EligibilityLossRule.END_OF_MONTH_FOLLOWING_TERMINATION == loss_rule
                ):
                    termination_date = self.get_last_day_of_month(
                        cast(date, eligibility_record.effective_range.upper)
                    )
                else:
                    raise ValueError(
                        f"Unexpected elibility loss rule value: {loss_rule}"
                    )

        log.info(
            f"Wallet {wallet.id} set to RUNOUT state with end date {termination_date} with runout_period {runout_period}"
        )
        # Use employee user_id since runout happened to employee member rather than dependents
        user_address = self.get_user_address(wallet.employee_member.id, session)
        if not user_address:
            stats.increment(
                metric_name=f"{BASE_METRIC_NAME}.set_wallet_to_runout.get_user_address",
                tags=["error_type:failed_get_address"],
                pod_name=stats.PodNames.BENEFITS_EXP,
            )

        if self.bypass_alegeus:
            return sync_meta
        try:
            resp = self.alegeus_api.update_employee_termination_date(
                wallet, termination_date, user_address
            )
            if not is_request_successful(resp):
                log.error(
                    f"Failed to terminate alegeus employee service: {wallet.id} due to response: {resp}"
                )
                stats.increment(
                    metric_name=f"{BASE_METRIC_NAME}.terminate_employee_service.error",
                    tags=[f"error_type:{resp}"],
                    pod_name=stats.PodNames.BENEFITS_EXP,
                )
                raise WalletProcessingError(message=str(resp), wallet_id=wallet.id)
        except Exception as e:
            log.error(f"Failed to set termination date for wallet {wallet} due to {e}")
            stats.increment(
                metric_name=f"{BASE_METRIC_NAME}.set_wallet_to_runout",
                tags=["error_type:failed_update_alegeus_service"],
                pod_name=stats.PodNames.BENEFITS_EXP,
            )
            raise WalletProcessingError(
                message="Failed to terminate employee services in Alegeus",
                wallet_id=wallet.id,
            ) from e
        return sync_meta

    def get_employee_user(
        self, wallet: ReimbursementWallet, session: RoutingSession
    ) -> Optional[User]:
        """Used to identify users belonging to wallets which were set to RUNOUT"""
        users = (
            session.query(User)
            .join(
                ReimbursementWalletUsers,
                User.id == ReimbursementWalletUsers.user_id,
            )
            .filter(
                ReimbursementWalletUsers.reimbursement_wallet_id == wallet.id,
                ReimbursementWalletUsers.type == WalletUserType.EMPLOYEE,
            )
            .all()
        )

        return users[0] if users else None

    def undo_set_wallet_to_runout(
        self, wallet: ReimbursementWallet, session: RoutingSession
    ) -> bool:
        metric_name = f"{BASE_METRIC_NAME}.undo_set_wallet_to_runout"

        employee_user: User | None = self.get_employee_user(
            wallet=wallet, session=session
        )

        if not employee_user:
            log.error("No employee user found for wallet", wallet_id=str(wallet.id))
            stats.increment(
                metric_name=f"{metric_name}.error",
                tags=["error_type:no_employee_user"],
                pod_name=stats.PodNames.BENEFITS_EXP,
            )
            return False

        # Use the employee to find the e9y record
        eligibility_record = self.e9y_service.get_verification_for_user_and_org(
            user_id=employee_user.id,
            organization_id=wallet.reimbursement_organization_settings.organization_id,
        )

        ros: ReimbursementOrganizationSettings | None = self.get_ros_for_user(
            eligibility_record=eligibility_record, session=session
        )

        if not ros:
            log.error("No valid ROS found for wallet", wallet_id=str(wallet.id))
            stats.increment(
                metric_name=f"{metric_name}.error",
                tags=["error_type:no_employee_user"],
                pod_name=stats.PodNames.BENEFITS_EXP,
            )
            return False

        if eligibility_record.effective_range is None or (
            eligibility_record.effective_range.upper
            and eligibility_record.effective_range.upper <= date.today()
        ):
            log.error(
                "Expired eligibility found for wallet",
                wallet_id=str(wallet.id),
                effective_range=str(eligibility_record.effective_range),
            )
            stats.increment(
                metric_name=f"{metric_name}.error",
                tags=["error_type:expired_eligibility"],
                pod_name=stats.PodNames.BENEFITS_EXP,
            )
            return False

        if ros.id != wallet.reimbursement_organization_settings_id:
            log.error(
                "Wallet ROS does not match member's eligible ROS",
                wallet_id=str(wallet.id),
                eligible_ros=str(ros.id),
                wallet_ros_id=str(wallet.reimbursement_organization_settings_id),
            )
            stats.increment(
                metric_name=f"{metric_name}.error",
                tags=["error_type:ros_mismatch"],
                pod_name=stats.PodNames.BENEFITS_EXP,
            )
            return False

        # Set the wallet back to QUALIFIED
        wallet.state = WalletState.QUALIFIED

        # Set the RWUs back to ACTIVE
        for rwu in wallet.reimbursement_wallet_users:
            if rwu.status == WalletUserStatus.REVOKED:
                rwu.status = WalletUserStatus.ACTIVE
                log.info(
                    "Wallet user set back to active",
                    wallet_id=str(wallet.id),
                    rwu_id=str(rwu.id),
                )

        # Call Alegeus to remove termination date
        user_address = self.get_user_address(employee_user.id, session)

        if self.bypass_alegeus:
            return True

        resp = self.alegeus_api.update_employee_termination_date(
            wallet=wallet, termination_date=None, member_address=user_address
        )

        if not is_request_successful(resp):
            log.error(
                "Failed to un-terminate Alegeus employee",
                wallet_id=str(wallet.id),
                response=str(resp),
            )
            stats.increment(
                metric_name=f"{metric_name}.error",
                tags=["error_type:unterminate_failed"],
                pod_name=stats.PodNames.BENEFITS_EXP,
            )
            return False

        # Finally - everything is done
        return True

    def set_wallet_to_disqualified(
        self,
        wallet: ReimbursementWallet,
        eligibility_record: EligibilityVerification,
        sync_indicator: Optional[SyncIndicator] = SyncIndicator.CRON_JOB,
    ) -> ReimbursementWalletEligibilitySyncMeta:
        """
        Set the wallet state to DISQUALIFIED and create a sync meta object.

        Args:
            wallet (ReimbursementWallet): The wallet to set to DISQUALIFIED state.
            eligibility_record (EligibilityVerification): The eligibility record for the wallet's user.
            sync_indicator (Optional[SyncIndicator]): The indicator of how the sync was initiated.

        Returns:
            ReimbursementWalletEligibilitySyncMeta: An object containing metadata about the sync operation.
        """
        sync_meta = self.create_sync_meta(
            wallet,
            ChangeType.DISQUALIFIED,
            eligibility_record,
            sync_indicator=sync_indicator,
        )
        wallet.state = WalletState.DISQUALIFIED
        log.info(f"Wallet {wallet.id} set to DISQUALIFIED state")
        return sync_meta

    def change_wallet_ros(
        self,
        wallet: ReimbursementWallet,
        new_ros: ReimbursementOrganizationSettings,
        eligibility_record: EligibilityVerification,
        session: RoutingSession,
        sync_indicator: Optional[SyncIndicator] = SyncIndicator.CRON_JOB,
    ) -> Optional[ReimbursementWalletEligibilitySyncMeta]:
        """
        Change the wallet's Reimbursement Organization Settings (ROS) and create a sync meta object.

        Args:
            wallet (ReimbursementWallet): The wallet to update.
            new_ros (ReimbursementOrganizationSettings): The new ROS to apply to the wallet.
            eligibility_record (EligibilityVerification): The eligibility record for the wallet's user.
            session: (RoutingSession): A fresh routing session object
            sync_indicator (Optional[SyncIndicator]): The indicator of how the sync was initiated.

        Returns:
            ReimbursementWalletEligibilitySyncMeta: An object containing metadata about the sync operation.
        """
        try:
            old_ros_id = wallet.reimbursement_organization_settings_id

            if self.update_category_settings(wallet, old_ros_id, new_ros.id, session):
                sync_meta = self.create_sync_meta(
                    wallet,
                    ChangeType.ROS_CHANGE,
                    eligibility_record,
                    new_ros=new_ros,
                    old_ros_id=old_ros_id,
                    sync_indicator=sync_indicator,
                )
                if not self.dry_run:
                    self.notify_payment_ops_of_ros_change(
                        wallet, old_ros_id, new_ros.id
                    )
                    log.info(
                        f"Wallet {wallet.id} ROS changed from {old_ros_id} to {new_ros.id}"
                    )
                else:
                    # For dry run, we will switch back the wallet to the old_ros_id
                    self.get_or_create_categories_by_ros_id(wallet, old_ros_id)
                return sync_meta
            return None
        except Exception as e:
            log.exception(f"Error changing ROS for wallet {wallet.id}: {str(e)}", exc=e)
            raise WalletProcessingError(
                f"Failed to change ROS for wallet {wallet.id}", wallet.id
            )

    @staticmethod
    def remove_user_access(
        wallet: ReimbursementWallet, user: User, session: RoutingSession
    ) -> None:
        """
        Remove a user's access to a wallet by setting their status to REVOKED.

        Args:
            wallet (ReimbursementWallet): The wallet to remove access from.
            user (User): The user whose access should be removed.
            session: (RoutingSession): A fresh routing session object
        """
        wallet_user = (
            session.query(ReimbursementWalletUsers)
            .join(ReimbursementWalletUsers.wallet)
            .filter(
                ReimbursementWallet.id == wallet.id,
                ReimbursementWalletUsers.user_id == user.id,
            )
            .first()
        )

        if wallet_user:
            wallet_user.status = WalletUserStatus.REVOKED
            log.info(f"{wallet_user.user_id}: {wallet_user.status}")
            log.info(f"User {user.id} access revoked for wallet {wallet.id}")

    def update_category_settings(
        self,
        wallet: ReimbursementWallet,
        old_ros_id: int,
        new_ros_id: int,
        session: RoutingSession,
    ) -> bool:
        """
        Update category settings when changing from one ROS to another.

        This method handles the complex logic of updating category settings, including
        checking for overlaps in expense types and adjusting balances accordingly.

        Args:
            wallet (ReimbursementWallet): The wallet being updated.
            old_ros_id (int): The ID of the old ROS.
            new_ros_id (int): The ID of the new ROS.
            session: (RoutingSession): A fresh routing session object
        """
        try:
            old_ros = session.query(ReimbursementOrganizationSettings).get(old_ros_id)
            new_ros = session.query(ReimbursementOrganizationSettings).get(new_ros_id)

            if not old_ros or not new_ros:
                raise ValueError(
                    f"Cannot find ReimbursementOrganizationSettings for ids {old_ros_id} and {new_ros_id}"
                )

            # Get category associations for old and new ROS
            old_categories = self.get_categories_for_wallet(wallet)
            old_employer_id, old_employee_id = self.get_employer_employee_id(wallet)
            # we need to also get all the spent before switching the ros_id
            old_categories_spent = {
                old_cat.reimbursement_request_category_id: self.get_spent_amount(
                    wallet, old_cat
                )
                for old_cat in old_categories
            }

            old_wallet_is_mmb_gold: bool = self.is_wallet_mmb_gold(wallet)
            # Switches the ROS ID to the new ROS and read the categories for the new ROS
            wallet.reimbursement_organization_settings_id = new_ros_id
            # Expire since reimbursement_organization_settings_id was set
            session.expire(wallet, ["reimbursement_organization_settings"])

            new_categories = self.get_categories_for_wallet(wallet)
            # Check if wallet is gold with the new ROS
            new_wallet_is_mmb_gold: bool = self.is_wallet_mmb_gold(wallet)

            if (
                allow_cycle_currency_switch_process(wallet=wallet)
                and old_wallet_is_mmb_gold
                and new_wallet_is_mmb_gold
            ):
                log.info(
                    "Source wallet and destination are mmb gold...checking if it's a cycle <-> currency conversion case"
                )
                stats.increment(
                    metric_name=f"{BASE_METRIC_NAME}.is_amazon_qualified_wallet",
                    pod_name=stats.PodNames.BENEFITS_EXP,
                    tags=[
                        f"old_ros_id:{str(old_ros_id)}",
                        f"new_ros_id:{str(new_ros_id)}",
                    ],
                )
                # Attempt to run our benefit type switch logic
                if (
                    matched_categories := self.is_cycle_currency_conversion(
                        wallet=wallet,
                        old_categories=old_categories,
                        new_categories=new_categories,
                    )
                ) != (None, None):
                    source, destination = matched_categories
                    log.info(
                        "cycle <-> currency conversion case detected",
                        wallet_id=str(wallet.id),
                        source_category_association=str(source),
                        destination_category_association=str(destination),
                    )
                    stats.increment(
                        metric_name=f"{BASE_METRIC_NAME}.check_cycle_currency_switch",
                        pod_name=stats.PodNames.BENEFITS_EXP,
                        tags=[
                            "type:success",
                            f"old_ros_id:{str(old_ros_id)}",
                            f"new_ros_id:{str(new_ros_id)}",
                        ],
                    )
                    converter = ReimbursementWalletBenefitTypeConverter(
                        session=session,
                        alegeus_api=self.alegeus_api,
                        bypass_alegeus=self.bypass_alegeus,
                    )

                    if (
                        source
                        and destination
                        and source.benefit_type == BenefitTypes.CYCLE
                        and destination.benefit_type == BenefitTypes.CURRENCY
                    ):
                        stats.increment(
                            metric_name=f"{BASE_METRIC_NAME}.cycle_currency_switch_detected",
                            pod_name=stats.PodNames.BENEFITS_EXP,
                            tags=[
                                "type:cycle_to_currency",
                                f"old_ros_id:{str(old_ros_id)}",
                                f"new_ros_id:{str(new_ros_id)}",
                            ],
                        )
                        return converter.convert_cycle_to_currency_and_update_alegeus(
                            wallet=wallet,
                            cycle_category=source,
                            currency_category=destination,
                        )
                    elif (
                        source
                        and destination
                        and source.benefit_type == BenefitTypes.CURRENCY
                        and destination.benefit_type == BenefitTypes.CYCLE
                    ):
                        stats.increment(
                            metric_name=f"{BASE_METRIC_NAME}.cycle_currency_switch_detected",
                            pod_name=stats.PodNames.BENEFITS_EXP,
                            tags=[
                                "type:currency_to_cycle",
                                f"old_ros_id:{str(old_ros_id)}",
                                f"new_ros_id:{str(new_ros_id)}",
                            ],
                        )
                        return converter.convert_currency_to_cycle_and_update_alegeus(
                            wallet=wallet,
                            currency_category=source,
                            cycle_category=destination,
                        )
                    stats.increment(
                        metric_name=f"{BASE_METRIC_NAME}.cycle_currency_switch_detected",
                        pod_name=stats.PodNames.BENEFITS_EXP,
                        tags=[
                            "type:undefined",
                            f"old_ros_id:{str(old_ros_id)}",
                            f"new_ros_id:{str(new_ros_id)}",
                        ],
                    )
                    raise WalletProcessingError(
                        message="Invalid conversion for benefit <--> currency conversion",
                        wallet_id=wallet.id,
                    )
                else:
                    log.info(
                        "Not a valid benefit type conversion case...continuing with other checks",
                        wallet_id=str(wallet.id),
                    )
                    stats.increment(
                        metric_name=f"{BASE_METRIC_NAME}.check_cycle_currency_switch",
                        pod_name=stats.PodNames.BENEFITS_EXP,
                        tags=[
                            "type:failed",
                            f"old_ros_id:{str(old_ros_id)}",
                            f"new_ros_id:{str(new_ros_id)}",
                        ],
                    )
                    pass

            # The following two checks perform the necessary check for
            # are we getting a non-mmb wallet => mmb wallet case, if conditions are met
            # we proceed with carry over automation, otherwise we raise it to the ops

            # Check if the old wallet is MMB
            if old_wallet_is_mmb_gold:
                # Since the old wallet is a Gold wallet, switch back to the old ROS and let ops handle
                wallet.reimbursement_organization_settings_id = old_ros_id
                self.escalate_eligibility_issue_to_payment_ops(
                    wallet,
                    "Got a carry over case we can't handle - existing wallet is MMB wallet instead of traditional",
                )
                return False

            # Check if the new wallet is NOT MMB
            if not new_wallet_is_mmb_gold:
                # Since the new wallet is a Green wallet, switch back to the old ROS and let ops handle
                wallet.reimbursement_organization_settings_id = old_ros_id
                self.escalate_eligibility_issue_to_payment_ops(
                    wallet,
                    "Got a carry over case we can't handle - wallet with new ROS is not MMB wallet, still traditional",
                )
                return False

            # We are finally sure that this is a Green -> Gold (MMB) switch that can be handled
            # Set the members wallet to the new ROS and create accounts in Alegeus
            new_categories = self.get_or_create_categories_by_ros_id(wallet, new_ros_id)
            # Expire since reimbursement_organization_settings_id was set
            session.expire(wallet, ["reimbursement_organization_settings"])

            old_category_map = {
                cat.reimbursement_request_category_id: cat for cat in old_categories
            }
            # Create a mapping of expense types to categories for old ROS
            old_expense_type_map = self.get_category_expense_type_map(
                old_categories, session
            )

            # we first terminate plans has the same account type otherwise new plan won't be enrolled properly
            matching_acct_type_plans = self.get_matching_alegeus_categories(
                old_categories, new_categories, session=session
            )
            self.process_matching_acct_type_alegeus_plan(
                wallet, matching_acct_type_plans, session=session
            )

            for new_category in new_categories:
                new_category_id = new_category.reimbursement_request_category_id
                new_expense_types = frozenset(
                    self.get_expense_types(cast(int, new_category_id), session)
                )
                log.info(
                    f"new category id: {new_category_id}, new expense_types: {new_expense_types}"
                )
                if new_category_id in old_category_map:
                    # Exact category match found, no action needs to be done
                    continue
                else:
                    overlapped_amounts = {}
                    # For each new category, check all old categories have overlap with
                    # this new category, accumulate the amount of spent
                    for old_cat_id, old_expense_types in old_expense_type_map.items():
                        if (
                            new_expense_types & old_expense_types
                        ):  # Check for intersection
                            overlap_amount = old_categories_spent[old_cat_id]
                            if overlap_amount > 0:
                                overlapped_amounts[old_cat_id] = overlap_amount
                    if overlapped_amounts:
                        log.info(
                            f"Expense type overlap found for new category {new_category_id}. "
                            f"Overlapped amounts: {overlapped_amounts}"
                        )

                        total_overlap_amount = sum(overlapped_amounts.values())
                        # there's multiple old category overlap with the new category
                        # no way to have the same alegeus plan id
                        if len(overlapped_amounts) > 1:
                            log.info(
                                f"Multiple old categories found overlap with new category: {new_category_id} for wallet: {wallet.id}"
                            )
                            self.adjust_carry_over_spent(
                                wallet,
                                new_category,
                                total_overlap_amount,
                                session=session,
                            )
                        else:
                            # only one old category overlap with new one, we want to compare
                            # the alegeus plan id
                            old_alegeus_plan = self.get_alegeus_plan(
                                old_category_map[list(overlapped_amounts.keys())[0]],
                                session=session,
                            )
                            new_alegeus_plan = self.get_alegeus_plan(
                                new_category, session=session
                            )

                            if (
                                old_alegeus_plan
                                and new_alegeus_plan
                                and old_alegeus_plan.alegeus_plan_id
                                != new_alegeus_plan.alegeus_plan_id
                            ):
                                self.adjust_carry_over_spent(
                                    wallet,
                                    new_category,
                                    total_overlap_amount,
                                    session=session,
                                )

            # Set terminate date for all the plans associate with old ros_id
            new_map = {
                item.reimbursement_request_category_id: item for item in new_categories
            }
            if not self.bypass_alegeus:
                for category in old_categories:
                    if category.reimbursement_request_category_id in new_map:
                        log.info(f"Skipping same plan: {category.id}")
                        continue
                    reimbursement_plan = self.get_alegeus_plan(
                        category, session=session
                    )
                    if not reimbursement_plan:
                        log.error(f"No reimbursement plan found for {category}")
                        continue
                    try:
                        self.terminate_alegeus_plan(
                            cast(str, old_employer_id),
                            cast(str, old_employee_id),
                            cast(ReimbursementPlan, reimbursement_plan),
                        )
                    except Exception as e:
                        log.error(
                            f"Failed to set termination date for plan {reimbursement_plan} due to {e}"
                        )
                        stats.increment(
                            metric_name=f"{BASE_METRIC_NAME}.update_category_settings",
                            tags=["error_type:fail_terminate_employee_account"],
                            pod_name=stats.PodNames.BENEFITS_EXP,
                        )

            return True
        except Exception as e:
            log.exception(
                f"Error updating category settings for wallet {wallet.id}: {str(e)}"
            )
            raise WalletProcessingError(
                f"Failed to update category settings for wallet {wallet.id}", wallet.id
            )

    def get_alegeus_account_type(
        self,
        category: ReimbursementOrgSettingCategoryAssociation,
        session: RoutingSession,
    ) -> Optional[str]:
        """
        Get the Alegeus account type for a given category.

        Args:
            category: The category association to check.
            session: (RoutingSession): A fresh routing session object

        Returns:
            The Alegeus account type if found, None otherwise.
        """
        plan = self.get_alegeus_plan(category, session)
        if plan and plan.reimbursement_account_type:
            return plan.reimbursement_account_type.alegeus_account_type
        return None

    def get_matching_alegeus_categories(
        self,
        old_categories: List[ReimbursementOrgSettingCategoryAssociation],
        new_categories: List[ReimbursementOrgSettingCategoryAssociation],
        session: RoutingSession,
    ) -> List[
        Tuple[
            ReimbursementOrgSettingCategoryAssociation,
            ReimbursementOrgSettingCategoryAssociation,
        ]
    ]:
        """
        Find categories between old and new ROS that have matching Alegeus account types.
        Skips exact matches (same category IDs) since they don't need transfer/adjustment.

        Args:
            old_categories: List of category associations from the old ROS
            new_categories: List of category associations from the new ROS
            session: (RoutingSession): A fresh routing session object

        Returns:
            List of tuples containing (old_category, new_category) pairs that have matching
            Alegeus account types but different category IDs
        """
        matching_pairs = []

        # Create map of old categories' alegeus account types
        old_category_alegeus_types = {}
        for old_cat in old_categories:
            account_type = self.get_alegeus_account_type(old_cat, session)
            if account_type:
                old_category_alegeus_types[old_cat] = account_type

        # Compare against new categories
        for new_cat in new_categories:
            new_account_type = self.get_alegeus_account_type(new_cat, session)
            if new_account_type:
                # Find matching old categories
                for old_cat, old_account_type in old_category_alegeus_types.items():
                    # Skip if it's the exact same category
                    if (
                        old_cat.reimbursement_request_category_id
                        == new_cat.reimbursement_request_category_id
                    ):
                        continue
                    if old_account_type == new_account_type:
                        matching_pairs.append((old_cat, new_cat))

        return matching_pairs

    def process_matching_acct_type_alegeus_plan(
        self,
        wallet: ReimbursementWallet,
        matching_pairs: List[
            Tuple[
                ReimbursementOrgSettingCategoryAssociation,
                ReimbursementOrgSettingCategoryAssociation,
            ]
        ],
        session: RoutingSession,
    ) -> None:
        if not matching_pairs:
            return
        employer_id, employee_id = self.get_employer_employee_id(wallet)
        # For each account type match
        for old_cat, new_cat in matching_pairs:
            # terminate the old plan first so we can enroll to the new plan
            old_plan = self.get_alegeus_plan(old_cat, session)
            if not self.bypass_alegeus:
                self.terminate_alegeus_plan(
                    cast(str, employer_id),
                    cast(str, employee_id),
                    cast(ReimbursementPlan, old_plan),
                )
                # borrow logic similar to action_enroll_wallet_in_alegeus
                success, _ = configure_wallet_allowed_category(
                    wallet=wallet,
                    allowed_category_id=new_cat.id,
                )
                if not success:
                    stats.increment(
                        metric_name=f"{BASE_METRIC_NAME}.process_matching_acct_type_alegeus_plan.error",
                        tags=[
                            f"error_type:failed_to_enroll_alegeus:{new_cat.reimbursement_request_category_id}"
                        ],
                        pod_name=stats.PodNames.BENEFITS_EXP,
                    )

    @staticmethod
    def get_employer_employee_id(
        wallet: ReimbursementWallet,
    ) -> Tuple[str, Optional[str]]:
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = cast(str, organization.alegeus_employer_id)
        employee_id = wallet.alegeus_id
        return employer_id, employee_id

    def terminate_alegeus_plan(
        self, employer_id: str, employee_id: str, plan: ReimbursementPlan
    ) -> None:
        if not self.bypass_alegeus:
            log.info(
                f"Terminating alegeus plan {plan}, for employer: {employer_id}, employee: {employee_id}"
            )
            resp = self.alegeus_api.terminate_employee_account(
                employer_id,
                employee_id,
                plan,
                date.today(),
            )
            if not is_request_successful(resp):
                log.error(
                    f"Failed to terminate alegeus plan: {plan} due to response: {resp}"
                )
                stats.increment(
                    metric_name=f"{BASE_METRIC_NAME}.terminate_alegeus_plan.error",
                    tags=[
                        f"error_type:failed_to_terminate_alegeus_plan:{plan.alegeus_plan_id}"
                    ],
                    pod_name=stats.PodNames.BENEFITS_EXP,
                )

    def get_category_expense_type_map(
        self,
        categories: list[ReimbursementOrgSettingCategoryAssociation],
        session: RoutingSession,
    ) -> dict[int, frozenset[str]]:
        result: dict[int, frozenset[str]] = {}
        for cat in categories:
            expense_types = frozenset(
                self.get_expense_types(
                    cast(int, cat.reimbursement_request_category_id), session
                )
            )
            if not expense_types:
                log.error(
                    f"No expense type found for: {cat.reimbursement_request_category_id}"
                )
                expense_types = []
            result[cast(int, cat.reimbursement_request_category_id)] = expense_types
        return result

    @staticmethod
    def get_alegeus_plan(
        category: ReimbursementOrgSettingCategoryAssociation, session: RoutingSession
    ) -> Optional[ReimbursementPlan]:
        """
        Get the Alegeus plan ID for a given category.

        Args:
            category (ReimbursementOrgSettingCategoryAssociation): The category to get the plan ID for.
            session: (RoutingSession): A fresh routing session object

        Returns:
            Optional[str]: The Alegeus plan ID if found, None otherwise.
        """
        reimbursement_request_category = (
            session.query(ReimbursementRequestCategory)
            .filter_by(id=category.reimbursement_request_category_id)
            .first()
        )

        if (
            reimbursement_request_category
            and reimbursement_request_category.reimbursement_plan
        ):
            return reimbursement_request_category.reimbursement_plan

        return None

    def get_categories_for_wallet(
        self, wallet: ReimbursementWallet
    ) -> List[ReimbursementOrgSettingCategoryAssociation]:
        """
        Get categories associated with wallet but don't create any DB records or Alegeus records

        Args:
            wallet (ReimbursementWallet): The wallet to get categories for.

        Returns:
            List[ReimbursementOrgSettingCategoryAssociation]: A list of category associations.
        """
        categories = wallet.get_wallet_allowed_categories
        return categories

    def get_or_create_categories_by_ros_id(
        self, wallet: ReimbursementWallet, ros_id: Optional[int] = None
    ) -> List[ReimbursementOrgSettingCategoryAssociation]:
        """
        Get categories associated with a specific ROS ID by creating ReimbursementWalletAllowedCategorySettings
        and creating categories in Alegeus

        Args:
            wallet (ReimbursementWallet): The wallet to get categories for.
            ros_id (Optional[int]): The ROS ID to get categories for. If None, uses the wallet's current ROS.

        Returns:
            List[ReimbursementOrgSettingCategoryAssociation]: A list of category associations.
        """
        if not ros_id:
            return wallet.get_or_create_wallet_allowed_categories
        else:
            wallet.reimbursement_organization_settings_id = ros_id
            # unset cache to prevent stale result
            wallet._cached_get_allowed_categories = None
            return wallet.get_or_create_wallet_allowed_categories

    def adjust_carry_over_spent(
        self,
        wallet: ReimbursementWallet,
        new_category: ReimbursementRequestCategory,
        total_overlap_amount: int,
        session: RoutingSession,
    ) -> None:
        reimburse_request = self.update_internal_balance(
            wallet, new_category, total_overlap_amount, session=session
        )
        if not self.bypass_alegeus:
            self.call_alegeus_for_adjustment(
                wallet,
                new_category,
                cast(ReimbursementRequest, reimburse_request),
                total_overlap_amount,
                session=session,
            )
        else:
            log.info(
                f"Bypass Alegeus call: Calling alegeus for wallet: {wallet.id}, category: {new_category.id}, with amount: {total_overlap_amount}"
            )

    @staticmethod
    def get_expense_types(category_id: int, session: RoutingSession) -> List[str]:
        """
        Get expense types associated with a specific category ID.

        Args:
            category_id (int): The ID of the category to get expense types for.
            session: (RoutingSession): A fresh routing session object

        Returns:
            List[str]: A list of expense type strings.
        """
        expense_types = (
            session.query(ReimbursementRequestCategoryExpenseTypes.expense_type)
            .filter(
                ReimbursementRequestCategoryExpenseTypes.reimbursement_request_category_id
                == category_id
            )
            .all()
        )
        return [et[0].value for et in expense_types]  # type: ignore[attr-defined]

    @staticmethod
    def create_claim(
        reimbursement_request: ReimbursementRequest,
        wallet: ReimbursementWallet,
        amount: int,
    ) -> Optional[ReimbursementClaim]:
        reimbursement_claim = ReimbursementClaim(
            reimbursement_request=reimbursement_request,
            amount=convert_cents_to_dollars(amount),
            status="APPROVED",
        )
        reimbursement_account = get_reimbursement_account_from_request_and_wallet(
            reimbursement_request, wallet
        )
        if not reimbursement_account:
            log.error(
                f"No reimbursement account found for wallet {wallet.id}, fail to create reimbursement claim"
            )
            return None

        reimbursement_claim.create_alegeus_claim_id()
        return reimbursement_claim

    def call_alegeus_for_adjustment(
        self,
        wallet: ReimbursementWallet,
        new_category: ReimbursementOrgSettingCategoryAssociation,
        reimbursement_request: ReimbursementRequest,
        amount: int,
        session: RoutingSession,
    ) -> None:
        """
        Call the Alegeus API to adjust the plan amount for a wallet and category.

        Args:
            wallet (ReimbursementWallet): The wallet to adjust.
            new_category (ReimbursementOrgSettingCategoryAssociation): The category being adjusted.
            amount (int): The amount to adjust by.
            reimbursement_request: (ReimbursementRequest): new reimbursement request represent this adjustment
            session: (RoutingSession): A fresh routing session object
        """
        log.info(
            f"Calling Alegeus for adjustment: Wallet {wallet.id}, "
            f"New Category {new_category.id}, Amount: {amount}"
        )
        if self.dry_run:
            log.info(
                "Dry Run: Calling Alegeus for adjustment: Wallet {wallet.id}, New Category {new_category.id}, Amount: {amount} "
            )
        else:
            plan = self.get_alegeus_plan(new_category, session)
            reimbursement_claim = self.create_claim(
                reimbursement_request, wallet, amount
            )
            if not reimbursement_claim:
                stats.increment(
                    metric_name=f"{BASE_METRIC_NAME}.call_alegeus_for_adjustment.failure",
                    pod_name=stats.PodNames.BENEFITS_EXP,
                    tags=["error_type:error_create_claim"],
                )
                log.error(f"Failed to create reimbursement_claim for {wallet.id}")
                return
            try:
                # open question: wallet balance vs carry over spent
                resp = self.alegeus_api.post_adjust_plan_amount(
                    wallet=wallet,
                    claim_id=reimbursement_claim.alegeus_claim_id,
                    reimbursement_amount=amount,
                    plan=plan,
                    service_start_date=reimbursement_request.service_start_date,
                )
                # lightweight validation, status code
                self.validate_response(resp, reimbursement_claim=reimbursement_claim)
            except Exception as e:
                # retry failed
                log.error(f"Got exception {e} after retry")
                stats.increment(
                    metric_name=f"{BASE_METRIC_NAME}.call_alegeus_for_adjustment.failure",
                    pod_name=stats.PodNames.BENEFITS_EXP,
                    tags=["error_type:error_call_alegeus"],
                )

    @staticmethod
    def validate_response(
        response: Response, reimbursement_claim: ReimbursementClaim
    ) -> None:
        reimbursement_claim_id = reimbursement_claim.id
        try:
            if not is_request_successful(response):
                if not response.status_code:
                    raise CreateDirectPaymentClaimErrorResponseException(
                        f"Response status code unavailable in the response for claim {reimbursement_claim_id}"
                    )
                else:
                    raise CreateDirectPaymentClaimErrorResponseException(
                        f"Unsuccessful response status code {str(response.status_code)} in the response for claim {reimbursement_claim_id}"
                    )

            response_json = response.json()

            if response_json.get("ErrorCode") is None:
                raise CreateDirectPaymentClaimErrorResponseException(
                    f"ErrorCode in the response is unavailable for claim {reimbursement_claim_id}",
                )

            error_code = str(response_json.get("ErrorCode"))
            if error_code != "0":
                raise CreateDirectPaymentClaimErrorResponseException(
                    f"Error in the response for claim {reimbursement_claim_id}, code: {error_code}"
                )
        except Exception as e:
            try:
                # Response should not contain PHI/PII -- see:
                # https://developer.api.wealthcare.com/api-details/overview#api=wealthcare-system-integration-rest-api-8-0&operation=SubmitManualClaim_2021_04
                log.exception(
                    "Error in validating response",
                    response=response.json(),
                    error_type=type(e).__name__,
                    error=str(e),
                )
            except JSONDecodeError:
                log.exception(
                    "Error in validating response",
                    response=response.content,  # log a non-json response in validating the response
                    error_type=type(e).__name__,
                    error=str(e),
                )
            raise e

    def update_internal_balance(
        self,
        wallet: ReimbursementWallet,
        new_category: ReimbursementOrgSettingCategoryAssociation,
        amount: int,
        session: RoutingSession,
    ) -> Optional[ReimbursementRequest]:
        log.info(
            f"Updating internal balance: Wallet {wallet.id}, "
            f"Category {new_category.id}, Amount: {amount}"
        )
        if not self.dry_run:
            # create one new reimbursement request
            utc_now = datetime.now(pytz.UTC)

            # Convert to Eastern Time (handles both EST and EDT automatically)
            eastern = pytz.timezone("America/New_York")
            eastern_time = utc_now.astimezone(eastern)

            new_reimbursement_request = ReimbursementRequest(
                label="historical spend adjustment",
                description="historical spend adjustment based on eligibility change",
                transaction_amount=amount,
                service_provider="historical spend adjustment",
                # there should be util already
                category=new_category.reimbursement_request_category,
                # Note: this relationship is the reason reimbursement request get persisted even under dry_run
                wallet=wallet,
                state=ReimbursementRequestState.REIMBURSED,
                reimbursement_type=ReimbursementRequestType.MANUAL,
                # current date: Use eastern time to avoid date in the future causing alegeus reject, consistent with
                # post call to alegeus
                service_start_date=eastern_time.date(),
            )
            transaction_amount = self.currency_service.to_money(
                amount=amount, currency_code=DEFAULT_CURRENCY_CODE
            )
            new_reimbursement_request = (
                self.currency_service.process_reimbursement_request(
                    transaction=transaction_amount, request=new_reimbursement_request
                )
            )
            session.add(new_reimbursement_request)
            return new_reimbursement_request
        else:
            log.info(
                f"Dry Run: Created new reimbursement request: {wallet.id},"
                f"Category {new_category.id}, Amount: {amount}"
            )
            return None

    @staticmethod
    def get_spent_amount(
        wallet: ReimbursementWallet,
        category: ReimbursementOrgSettingCategoryAssociation,
    ) -> int:
        """
        Get the spent amount for a specific wallet and category.

        Args:
            wallet (ReimbursementWallet): The wallet to check.
            category (ReimbursementOrgSettingCategoryAssociation): The category to check.

        Returns:
            int: The spent amount for the given wallet and category.
        """
        if (
            category.reimbursement_request_category_id
            in wallet.approved_amount_by_category_alltime
        ):
            return wallet.approved_amount_by_category_alltime[
                category.reimbursement_request_category_id
            ]
        else:
            return 0

    @staticmethod
    def notify_payment_ops_of_ros_change(
        wallet: ReimbursementWallet, old_ros_id: int, new_ros_id: int
    ) -> None:
        """
        Create a ticket in the payment ops system for a wallet ROS change.

        Args:
            wallet (ReimbursementWallet): The wallet that had its ROS changed.
            old_ros_id (int): The ID of the old ROS.
            new_ros_id (int): The ID of the new ROS.
        """
        log.info(
            f"Created payment ops ticket for wallet {wallet.id} ROS change from {old_ros_id} to {new_ros_id}"
        )
        user = wallet.employee_member
        if not user:
            log.error(f"No employee user found for wallet {wallet.id}")
            return

        ticket = ROSChangePaymentOpsZendeskTicket(
            user=user,
            wallet_id=wallet.id,
            old_ros_id=old_ros_id,
            new_ros_id=new_ros_id,
        )

        ticket.update_zendesk()

        log.info(
            "Created Payment Ops ticket for wallet ROS change",
            wallet_id=str(wallet.id),
            user_id=user.id,
            old_ros_id=old_ros_id,
            new_ros_id=new_ros_id,
            ticket_id=ticket.recorded_ticket_id,
        )

    @staticmethod
    def _get_ros_by_org_id(
        eligibility_record: EligibilityVerification, session: RoutingSession
    ) -> Optional[ReimbursementOrganizationSettings]:
        today = datetime.now(timezone.utc)
        try:
            ros = (
                session.query(ReimbursementOrganizationSettings)
                .filter(
                    ReimbursementOrganizationSettings.organization_id
                    == eligibility_record.organization_id,
                    ReimbursementOrganizationSettings.started_at <= today,
                    or_(
                        ReimbursementOrganizationSettings.ended_at == None,
                        ReimbursementOrganizationSettings.ended_at > today,
                    ),
                )
                .one_or_none()
            )
            return ros
        except Exception as e:
            log.error(
                f"Got exception {e} when getting ROS based on eligibility record id: {eligibility_record.organization_id}"
            )
            stats.increment(
                metric_name=f"{BASE_METRIC_NAME}.get_ros_for_user.error",
                pod_name=stats.PodNames.BENEFITS_EXP,
                tags=["reason:no_ros_based_on_org_id"],
            )
            return None

    def get_ros_for_user(
        self, eligibility_record: EligibilityVerification, session: RoutingSession
    ) -> Optional[ReimbursementOrganizationSettings]:
        """
        Get the ReimbursementOrganizationSettings for a user based on their eligibility record.

        Args:
            eligibility_record (EligibilityVerification): The eligibility record for the user.
            session: (RoutingSession): A fresh routing session object

        Returns:
            Optional[ReimbursementOrganizationSettings]: The ROS for the user if found, None otherwise.
        """
        if not eligibility_record:
            return None

        try:
            sub_population_id = self.e9y_service.get_sub_population_id_for_user_and_org(
                user_id=eligibility_record.user_id,
                organization_id=eligibility_record.organization_id,
            )

            if sub_population_id is None:
                log.warning(
                    "No sub population found for user in org",
                    user_id=eligibility_record.user_id,
                    organization_id=eligibility_record.organization_id,
                )
                stats.increment(
                    metric_name=f"{BASE_METRIC_NAME}.get_ros_for_user",
                    pod_name=stats.PodNames.BENEFITS_EXP,
                    tags=["type:ros_org_id"],
                )
                log.warning("Fallback to using eligibility record's ros_id to find ROS")
                return self._get_ros_by_org_id(eligibility_record, session=session)

            ros_ids = self.e9y_service.get_eligible_features_by_sub_population_id(
                sub_population_id=sub_population_id,
                feature_type=e9y_model.FeatureTypes.WALLET_FEATURE,
            )
            stats.increment(
                metric_name=f"{BASE_METRIC_NAME}.get_ros_for_user",
                pod_name=stats.PodNames.BENEFITS_EXP,
                tags=["type:sub_pop_id"],
            )

            if not ros_ids:
                log.warning(
                    "No eligible ROSs found for sub population",
                    sub_population_id=sub_population_id,
                    user_id=eligibility_record.user_id,
                )
                stats.increment(
                    metric_name=f"{BASE_METRIC_NAME}.get_ros_for_user.error",
                    pod_name=stats.PodNames.BENEFITS_EXP,
                    tags=["reason:no_ros_based_on_sub_pop"],
                )
                return None
            ros_id = ros_ids[0]

            ros = session.query(ReimbursementOrganizationSettings).get(ros_id)
            return ros

        except Exception as e:
            log.error(
                "Error getting ROS for user",
                user_id=eligibility_record.user_id,
                organization_id=eligibility_record.organization_id,
                error=str(e),
            )
            return None

    @staticmethod
    def escalate_eligibility_issue_to_payment_ops(
        wallet: ReimbursementWallet, reason: str
    ) -> None:
        """
        Escalate an issue to the operations team by creating a ticket.

        Args:
            wallet (ReimbursementWallet): The wallet with the issue.
            reason (str): The reason for escalation.
        """
        log.info(f"Escalated to ops: Wallet {wallet.id}, Reason: {reason}")
        stats.increment(
            metric_name=f"{BASE_METRIC_NAME}.escalate_eligibility_issue_to_payment_ops",
            pod_name=stats.PodNames.BENEFITS_EXP,
            tags=[f"reason:{reason[:50]}"],  # Truncate reason to avoid too long tags
        )
        user = wallet.employee_member
        if not user:
            log.error(f"No employee user found for wallet {wallet.id}")
            return

        ticket = NoEligibilityPaymentOpsZendeskTicket(
            user=user, wallet_id=wallet.id, reason=reason
        )

        ticket.update_zendesk()

        log.info(
            "Escalated to Payment Ops due to no eligibility record",
            wallet_id=str(wallet.id),
            user_id=user.id,
            reason=reason,
            ticket_id=ticket.recorded_ticket_id,
        )

    @staticmethod
    def is_wallet_mmb_gold(wallet: ReimbursementWallet) -> bool:
        if wallet.state not in (WalletState.QUALIFIED, WalletState.RUNOUT):
            return False

        if not wallet.reimbursement_organization_settings:
            return False

        direct_payment_enabled = (
            wallet.reimbursement_organization_settings.direct_payment_enabled
        )
        # Per conversation with James Lee, expense types and members are wallet level
        # attrs and it shouldn't change, checking direct payment should be sufficient

        return direct_payment_enabled

    @staticmethod
    def get_last_day_of_month(date_obj: date) -> date:
        return date_obj + relativedelta(day=31)

    @staticmethod
    def get_user_address(user_id: int, session: RoutingSession) -> Optional[Address]:
        return session.query(Address).filter(Address.user_id == user_id).one_or_none()

    @staticmethod
    def is_wallet_blacklisted(
        wallet: ReimbursementWallet, session: RoutingSession
    ) -> bool:
        """Check if a wallet is currently blacklisted from eligibility processing"""
        blacklist_entry = (
            session.query(ReimbursementWalletBlacklist)
            .filter(
                ReimbursementWalletBlacklist.reimbursement_wallet_id == wallet.id,
                ReimbursementWalletBlacklist.deleted_at.is_(None),
            )
            .first()
        )
        return blacklist_entry is not None

    @staticmethod
    def is_wallet_id(wallet: Union[ReimbursementWallet, int]) -> TypeGuard[int]:
        return isinstance(wallet, int)

    def process_wallet(
        self,
        wallet: Union[ReimbursementWallet, int],
        sync_indicator: Optional[SyncIndicator] = SyncIndicator.CRON_JOB,
    ) -> Optional[ReimbursementWalletEligibilitySyncMeta]:
        """
        Process a wallet to check and update its eligibility status.

        This method performs the main logic for checking a wallet's eligibility,
        updating its status, and handling any necessary changes.

        Args:
            wallet (ReimbursementWallet): The wallet to process.
            sync_indicator (Optional[SyncIndicator]): The indicator of how the sync was initiated.

        Returns:
            Optional[ReimbursementWalletEligibilitySyncMeta]: Sync metadata if changes were made, None otherwise.

        Flow Chart:
        +-------------------------+
        |         Start           |
        +-------------------------+
                   |
                   v
        +-------------------------+
        |   Get employee user     |
        +-------------------------+
                   |
                   v
        +-------------------------+
        | Employee user exists?   |
        +-------------------------+
             |             |
            Yes            No
             |             |
             v             v
        +------------+ +----------------------+
        |Get eligibility| |Log error and return None|
        |   record   | +----------------------+
        +------------+
             |
             v
        +-------------------------+
        |Eligibility record exists?|
        +-------------------------+
             |             |
            Yes            No
             |             |
             v             v
        +------------+ +------------------+
        |Is effective| |  Escalate to ops |
        | range None?| |  Return None     |
        +------------+ +------------------+
             |             |
            No             Yes
             |             |
             v             v
        +------------+ +------------------+
        |Is end date | |Set wallet to RUNOUT|
        |   valid?   | |Return sync meta   |
        +------------+ +------------------+
             |             |
            Yes            No
             |             |
             v             v
        +------------+ +------------------------+
        |Get new ROS | |Set wallet to DISQUALIFIED|
        | for user   | |Return sync meta         |
        +------------+ +------------------------+
             |
             v
        +-------------------------+
        |    New ROS exists?      |
        +-------------------------+
             |             |
            Yes            No
             |             |
             v             v
        +------------+ +------------------------+
        |New ROS ID !=| |Set wallet to DISQUALIFIED|
        |Current ROS? | |Return sync meta         |
        +------------+ +------------------------+
             |             |
            Yes            No
             |             |
             v             v
        +------------+ +------------------+
        |Change wallet| |Process dependent|
        |    ROS     | |     users       |
        +------------+ +------------------+
             |                   |
             |    +--------------+
             |    |
             v    v
        +-------------------------+
        |   Any changes made?     |
        +-------------------------+
             |             |
            Yes            No
             |             |
             v             v
        +------------+ +------------------+
        |Return sync | |    Return None   |
        |   meta     | |                  |
        +------------+ +------------------+
             |             |
             |             |
             v             v
        +-------------------------+
        |          End            |
        +-------------------------+
        """
        metric_name = f"{BASE_METRIC_NAME}.process_wallet"
        result: Optional[ReimbursementWalletEligibilitySyncMeta] = None

        stats.increment(
            f"{metric_name}.count",
            stats.PodNames.BENEFITS_EXP,
            tags=[f"sync_indicator:{sync_indicator.value}"],
        )

        with stats.timed(f"{metric_name}.duration", stats.PodNames.BENEFITS_EXP):
            try:
                with self._fresh_session() as session:
                    if self.is_wallet_id(wallet):
                        wallet = (
                            session.query(ReimbursementWallet)
                            .filter(ReimbursementWallet.id == wallet)
                            .first()
                        )
                    wallet = cast(ReimbursementWallet, wallet)
                    wallet_id = wallet.id

                    if self.is_wallet_blacklisted(wallet, session):
                        log.info(
                            "Skipping blacklisted wallet",
                            wallet_id=wallet.id,
                            sync_indicator=sync_indicator,
                        )
                        return None

                    with session.no_autoflush:
                        associated_users = wallet.all_active_users
                        employee_user = wallet.employee_member

                        if not employee_user:
                            log.error(f"No employee user found for wallet {wallet.id}")
                            stats.increment(
                                metric_name=f"{metric_name}.error",
                                tags=["error_type:no_employee_user"],
                                pod_name=stats.PodNames.BENEFITS_EXP,
                            )
                            return None

                        eligibility_record = self.e9y_service.get_verification_for_user_and_org(
                            user_id=employee_user.id,
                            organization_id=wallet.reimbursement_organization_settings.organization_id,
                        )

                        if not eligibility_record:
                            log.error(
                                f"No eligibility record found for user {employee_user.id} in org {wallet.reimbursement_organization_settings.organization_id}"
                            )
                            stats.increment(
                                metric_name=f"{metric_name}.error",
                                tags=["error_type:no_eligibility_record"],
                                pod_name=stats.PodNames.BENEFITS_EXP,
                            )
                            if self.dry_run:
                                log.info(
                                    "Dry Run: Escalate to ops with error: No eligibility record found"
                                )
                            else:
                                self.escalate_eligibility_issue_to_payment_ops(
                                    wallet, "No eligibility record found"
                                )
                            return None

                        if eligibility_record.effective_range is None:
                            log.error(
                                f"Effective range is None for eligibility record of user {employee_user.id}"
                            )
                            stats.increment(
                                metric_name=f"{metric_name}.error",
                                tags=["error_type:null_effective_range"],
                                pod_name=stats.PodNames.BENEFITS_EXP,
                            )
                            if self.dry_run:
                                log.info(
                                    "Dry Run: Escalate to ops with error: Effective range is None"
                                )
                            else:
                                self.escalate_eligibility_issue_to_payment_ops(
                                    wallet, "Effective range is None"
                                )
                            return None

                        if (
                            eligibility_record.effective_range.upper
                            and eligibility_record.effective_range.upper <= date.today()
                        ):
                            result = self.set_wallet_to_runout(
                                wallet,
                                eligibility_record,
                                session=session,
                                sync_indicator=sync_indicator,
                            )
                            stats.increment(
                                f"{metric_name}.state_change",
                                pod_name=stats.PodNames.BENEFITS_EXP,
                                tags=[
                                    f"new_state:{WalletState.RUNOUT.value}",
                                    "reason:terminate_date_found",
                                ],
                            )
                            dependent_changes = self.process_dependent_users(
                                wallet, associated_users, employee_user, session
                            )
                            if dependent_changes:
                                log.info(f"Remove access for {dependent_changes}")
                            if self.dry_run:
                                log.info(
                                    f"Dry Run: Expect wallet in runout state, created metadata: {result}"
                                )

                                log.info(f"Dry Run: {wallet.state}")
                            else:
                                session.add(result)
                                session.commit()
                            return result

                        new_ros = self.get_ros_for_user(
                            eligibility_record, session=session
                        )
                        if not new_ros:
                            log.info(
                                f"No new ROS found for wallet: {wallet.id} based on eligibility record, setting it to runout"
                            )
                            # Per conversation with product, we will use runout instead disqualified
                            result = self.set_wallet_to_runout(
                                wallet,
                                eligibility_record,
                                session=session,
                                eligibility_term_date=False,
                                sync_indicator=sync_indicator,
                            )
                            stats.increment(
                                f"{metric_name}.state_change",
                                pod_name=stats.PodNames.BENEFITS_EXP,
                                tags=[
                                    f"new_state:{WalletState.RUNOUT.value}",
                                    "reason:no_ros_found_based_on_e9y",
                                ],
                            )
                            dependent_changes = self.process_dependent_users(
                                wallet, associated_users, employee_user, session
                            )
                            if dependent_changes:
                                log.info(f"Remove access for {dependent_changes}")
                            if self.dry_run:
                                log.info(
                                    f"Dry Run: Expect wallet in disqualify state, created metadata: {result}"
                                )
                                log.info(f"Dry Run: {wallet.state}")
                            else:
                                session.add(result)
                                session.commit()
                            return result

                        if new_ros.id != wallet.reimbursement_organization_settings_id:
                            if self.dry_run:
                                log.info("Dry Run: Found ROS not same")
                            try:
                                # Send survey
                                result = self.change_wallet_ros(
                                    wallet,
                                    new_ros,
                                    eligibility_record,
                                    session=session,
                                    sync_indicator=sync_indicator,
                                )
                                stats.increment(
                                    f"{metric_name}.ros_change",
                                    pod_name=stats.PodNames.BENEFITS_EXP,
                                    tags=[
                                        f"old_ros:{wallet.reimbursement_organization_settings_id}",
                                        f"new_ros:{new_ros.id}",
                                    ],
                                )
                                if self.dry_run:
                                    log.info(
                                        f"Dry Run: Expect wallet update ros id from {wallet.reimbursement_organization_settings_id} to {new_ros.id}"
                                    )
                            except WalletProcessingError as wpe:
                                log.exception(
                                    f"Failed to change ROS for wallet {wpe.wallet_id}: {wpe.message}",
                                    exc=wpe,
                                )
                                stats.increment(
                                    metric_name=f"{metric_name}.error",
                                    tags=["error_type:ros_change_failure"],
                                    pod_name=stats.PodNames.BENEFITS_EXP,
                                )
                                session.rollback()
                                return None

                        dependent_changes = self.process_dependent_users(
                            wallet, associated_users, employee_user, session
                        )
                        stats.gauge(
                            metric_name=f"{metric_name}.dependent_changes",
                            pod_name=stats.PodNames.BENEFITS_EXP,
                            metric_value=len(dependent_changes),
                        )

                        if not result and dependent_changes:
                            result = self.create_sync_meta(
                                wallet,
                                ChangeType.DEPENDENT_CHANGE,
                                eligibility_record,
                                new_ros=new_ros,
                                sync_indicator=sync_indicator,
                            )
                            if self.dry_run:
                                log.info(f"Dry Run: Expect dependant change {result}")
                        if not self.dry_run and result:
                            session.add(result)
                            session.commit()

            except SQLAlchemyError as e:
                log.exception(
                    f"Database error occurred while processing wallet {wallet_id}: {str(e)}",
                    exc=e,
                )
                stats.increment(
                    metric_name=f"{metric_name}.error",
                    tags=["error_type:database_error"],
                    pod_name=stats.PodNames.BENEFITS_EXP,
                )
                return None

            except Exception as e:
                log.exception(
                    f"Unexpected error occurred while processing wallet {wallet_id}: {str(e)}",
                    exc=e,
                )
                stats.increment(
                    metric_name=f"{metric_name}.error",
                    tags=["error_type:unexpected_exception"],
                    pod_name=stats.PodNames.BENEFITS_EXP,
                )
                return None

            return result  # No changes were made, so no sync_meta is created

    def process_dependent_users(
        self,
        wallet: ReimbursementWallet,
        associated_users: List[User],
        employee_user: User,
        session: RoutingSession,
    ) -> List[Tuple[int, str]]:
        """
        Process dependent users associated with a wallet.

        This method checks the eligibility of dependent users and removes their access if necessary.

        Args:
            wallet (ReimbursementWallet): The wallet to process dependents for.
            associated_users (List[User]): The list of users associated with the wallet.
            employee_user (User): The primary employee user of the wallet.
            session: (RoutingSession): A fresh routing session object

        Returns:
            List[Tuple[int, str]]: A list of tuples containing user IDs and change types for dependents.
        """
        dependent_changes = []
        for user in associated_users:
            if user.id != employee_user.id:
                eligibility_record = self.e9y_service.get_verification_for_user_and_org(
                    user_id=user.id,
                    organization_id=wallet.reimbursement_organization_settings.organization_id,
                )

                if not eligibility_record or (
                    eligibility_record.effective_range
                    and eligibility_record.effective_range.upper
                    and eligibility_record.effective_range.upper <= date.today()
                ):
                    stats.increment(
                        metric_name=f"{BASE_METRIC_NAME}.process_dependent_users.dependent_user_access_removed",
                        pod_name=stats.PodNames.BENEFITS_EXP,
                        tags=[f"user_id:{user.id}"],
                    )
                    dependent_changes.append((user.id, "access_removed"))
                    self.remove_user_access(wallet, user, session)
        return dependent_changes

    @staticmethod
    def is_cycle_currency_conversion(
        wallet: ReimbursementWallet,
        old_categories: list[ReimbursementOrgSettingCategoryAssociation],
        new_categories: list[ReimbursementOrgSettingCategoryAssociation],
    ) -> tuple[
        ReimbursementOrgSettingCategoryAssociation,
        ReimbursementOrgSettingCategoryAssociation,
    ] | tuple[None, None]:
        """
        This method attempts to do the following
         1. match old and new categories which are the same - these don't need to be migrated
         2. the only remaining unmatched categories should be a cycle and a currency
        If both of the above succeed, then it is a valid conversion case, the conversion categories are returned as a tuple

        Note: This method is specific to Amazon's plan design

        Args:
            wallet (ReimbursementWallet): The wallet to process
            old_categories (list[ReimbursementOrgSettingCategoryAssociation]): categories of old ROS/wallet
            new_categories (list[ReimbursementOrgSettingCategoryAssociation]): categories of new ROS/wallet

        Returns: (tuple[ReimbursementOrgSettingCategoryAssociation, ReimbursementOrgSettingCategoryAssociation] | tuple[None, None]): returns a tuple of categories if it is a valid cycle/currency conversion case, otherwise returns (None, None)
        """
        # Make a copy so we don't modify the input
        old_categories_copy: list[
            ReimbursementOrgSettingCategoryAssociation
        ] = old_categories.copy()
        unmatched_categories: list[ReimbursementOrgSettingCategoryAssociation] = []

        for new_category in new_categories:
            if new_category.benefit_type == BenefitTypes.CURRENCY:
                matched: bool = False
                for idx, old_category in enumerate(old_categories_copy):
                    if (
                        old_category.benefit_type == BenefitTypes.CURRENCY
                        and new_category.reimbursement_request_category_id
                        == old_category.reimbursement_request_category_id
                        and new_category.reimbursement_request_category.reimbursement_plan.alegeus_plan_id
                        == old_category.reimbursement_request_category.reimbursement_plan.alegeus_plan_id
                    ):
                        log.info(
                            "Matching categories found between old and new categories",
                            matching_reimbursement_request_category_id=str(
                                new_category.reimbursement_request_category_id
                            ),
                            matching_alegeus_plan_id=str(
                                new_category.reimbursement_request_category.reimbursement_plan.alegeus_plan_id
                            ),
                            new_category_association_id=str(new_category.id),
                            old_category_association_id=str(old_category.id),
                            wallet_id=str(wallet.id),
                        )
                        matched = True
                        old_categories_copy.pop(idx)
                        break

                if not matched:
                    log.info(
                        "Categories do not match between old and new categories - adding to unmatched_categories",
                        new_reimbursement_request_category_id=str(
                            new_category.reimbursement_request_category_id
                        ),
                        new_alegeus_plan_id=str(
                            new_category.reimbursement_request_category.reimbursement_plan.alegeus_plan_id
                        ),
                        new_category_association_id=str(new_category.id),
                        wallet_id=str(wallet.id),
                    )
                    unmatched_categories.append(new_category)

            elif new_category.benefit_type == BenefitTypes.CYCLE:
                log.info(
                    "Adding cycle category to unmatched_categories",
                    new_reimbursement_request_category_id=str(
                        new_category.reimbursement_request_category_id
                    ),
                    new_category_association_id=str(new_category.id),
                    wallet_id=str(wallet.id),
                )
                unmatched_categories.append(new_category)
            else:
                raise ValueError(
                    f"Unhandled benefit type found {str(new_category.benefit_type)}"
                )

        if len(unmatched_categories) == 1 and len(old_categories_copy) == 1:
            # We have a valid case
            old_category = old_categories_copy[0]
            new_category = unmatched_categories[0]

            if {old_category.benefit_type, new_category.benefit_type} == {
                BenefitTypes.CYCLE,
                BenefitTypes.CURRENCY,
            }:
                log.info(
                    "Valid benefit conversion categories found",
                    old_reimbursement_request_category_id=str(
                        old_category.reimbursement_request_category_id
                    ),
                    new_reimbursement_request_category_id=str(
                        new_category.reimbursement_request_category_id
                    ),
                    old_alegeus_plan_id=str(
                        old_category.reimbursement_request_category.reimbursement_plan.alegeus_plan_id
                    ),
                    new_alegeus_plan_id=str(
                        new_category.reimbursement_request_category.reimbursement_plan.alegeus_plan_id
                    ),
                    old_category_association_id=str(old_category.id),
                    new_category_association_id=str(new_category.id),
                    wallet_id=str(wallet.id),
                )
                return old_category, new_category
            else:
                log.info(
                    "Matched categories are either both cycle or both currency, not a valid conversion case",
                    old_reimbursement_request_category_id=str(
                        old_category.reimbursement_request_category_id
                    ),
                    new_reimbursement_request_category_id=str(
                        new_category.reimbursement_request_category_id
                    ),
                    old_alegeus_plan_id=str(
                        old_category.reimbursement_request_category.reimbursement_plan.alegeus_plan_id
                    ),
                    new_alegeus_plan_id=str(
                        new_category.reimbursement_request_category.reimbursement_plan.alegeus_plan_id
                    ),
                    old_category_association_id=str(old_category.id),
                    new_category_association_id=str(new_category.id),
                    wallet_id=str(wallet.id),
                )
                return None, None

        else:
            log.info(
                "Mismatched benefit conversion categories found",
                wallet_id=str(wallet.id),
            )
            return None, None
