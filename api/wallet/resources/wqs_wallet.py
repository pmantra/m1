from __future__ import annotations

import secrets
import traceback
from traceback import format_exc
from typing import Optional, TypedDict, cast

from flask import request
from flask_restful import abort

import eligibility
from authn.models.user import User
from common import stats
from common.services.api import InternalServiceResource
from eligibility import e9y
from storage.connection import db
from tracks import service as tracks_service
from utils.log import logger
from wallet.models.constants import (
    WALLET_QUALIFICATION_SERVICE_TAG,
    ReimbursementMethod,
    ReimbursementRequestExpenseTypes,
    WalletState,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.organization_employee_dependent import OrganizationEmployeeDependent
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
    ReimbursementOrgSettingsExpenseType,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.repository.reimbursement_wallet import (
    ReimbursementWalletRepository,
    WalletAndRWU,
)
from wallet.repository.wallet_user_invite import WalletUserInviteRepository
from wallet.resources.reimbursement_wallet_dashboard import can_apply_for_wallet
from wallet.resources.wallet_invitation import (
    check_invitation,
    mark_invitation_as_claimed,
)
from wallet.schemas.wqs_wallet import WQSWalletPOSTRequest, WQSWalletPUTRequest
from wallet.services.reimbursement_wallet_messaging import (
    get_or_create_rwu_channel,
    open_zendesk_ticket,
)
from wallet.services.reimbursement_wallet_state_change import (
    WALLET_APPLICATION_MANUAL_REVIEW_TAG,
    handle_qualification_of_wallet_created_by_wqs,
)

WQS_MONO_RESOURCE = "wqs_mono_resource"

log = logger(__name__)

PUT_ACCEPTABLE_WALLET_STATES = (WalletState.PENDING, WalletState.DISQUALIFIED)


class WQSWalletResource(InternalServiceResource):
    """
    Resource to service the Wallet Qualifications Service's
    wallet creation functionality.
    """

    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Create a new ReimbursementWallet for a user.
        The Wallet Qualifications Service has its own internal endpoint
        for these operations because it has far more capabilities than
        the existing ReimbursementWalletResource endpoint, e.g. it can
        set the reimbursement method.
        """
        post_request: WQSWalletPOSTRequest = WQSWalletPOSTRequest.from_request(
            request.json if request.is_json else None
        )
        log.info(
            "WQSWalletPOSTRequest received.",
            user_id=str(self.user.id),
            reimbursement_organization_settings_id=f"'{post_request.reimbursement_organization_settings_id}'",
            state=str(post_request.state),
            wallet_user_type=str(post_request.wallet_user_type),
            wallet_user_status=str(post_request.wallet_user_status),
            primary_expense_type=str(post_request.primary_expense_type),
            is_inside_the_usa=str(post_request.is_inside_the_usa),
            dependent_first_name=str(post_request.dependent_first_name),
            dependent_last_name=str(post_request.dependent_last_name),
        )
        reimbursement_organization_settings_id = int(
            post_request.reimbursement_organization_settings_id
        )
        verification_svc: eligibility.EnterpriseVerificationService = (
            eligibility.get_verification_service()
        )
        verification: e9y.EligibilityVerification | None = (
            verification_svc.get_verification_for_user(user_id=self.user.id)
        )
        if verification is None or not verification:
            abort(403, message="Not Authorized for Wallet")
        user_can_apply_for_wallet = can_apply_for_wallet(
            self.user.id, verification_svc
        ).can_apply_for_wallet
        if not user_can_apply_for_wallet:
            abort(403, message="Not Authorized for Wallet")
        organization_id: int | None = (
            db.session.query(ReimbursementOrganizationSettings.organization_id)
            .filter(
                ReimbursementOrganizationSettings.id
                == reimbursement_organization_settings_id
            )
            .scalar()
        )
        if organization_id is None or organization_id != verification.organization_id:
            abort(403, message="Not Authorized for that Wallet Organization")

        track_svc = tracks_service.TrackSelectionService()
        if not track_svc.is_enterprise(user_id=self.user.id):
            abort(403, message="Not Authorized")

        # Check whether a wallet already exists.
        has_existing_wallet: bool = (
            db.session.query(ReimbursementWallet)
            .join(
                ReimbursementWalletUsers,
                ReimbursementWalletUsers.reimbursement_wallet_id
                == ReimbursementWallet.id,
            )
            .filter(
                ReimbursementWalletUsers.user_id == self.user.id,
                ReimbursementWallet.reimbursement_organization_settings_id
                == reimbursement_organization_settings_id,
                ReimbursementWalletUsers.status.in_(
                    [WalletUserStatus.ACTIVE, WalletUserStatus.PENDING]
                ),
            )
            .count()
            > 0
        )
        if has_existing_wallet:
            # This scenario should be impossible because the WQS should call PUT
            # if the user is already an active RWU.
            log.error(
                "Tried to create a wallet for a user who already has a wallet.",
                user_id=str(self.user.id),
            )
            abort(409, message="The user is already an RWU.")

        # TODO: get initial_eligibility_verification_id
        # once reading from new data model enabled in e9y

        reimbursement_method = _get_reimbursement_method(
            reimbursement_organization_settings_id,
            post_request.primary_expense_type,
            post_request.is_inside_the_usa,
        )

        eligibility_verification_2_id: Optional[int] = None
        eligibility_member_2_id: Optional[int] = None
        eligibility_member_2_version: Optional[int] = None

        if verification.eligibility_member_id:
            eligibility_member_2_id = verification.eligibility_member_2_id
            eligibility_member_2_version = verification.eligibility_member_2_version
        else:
            eligibility_verification_2_id = verification.verification_2_id
        primary_expense_type = post_request.primary_expense_type

        # 1. WQS calls the wqs mono E/P to create a wallet using a POST

        # 2. The wallet status can be any one of the Wallet States including Qualified

        # 3. Currently in production, when wqs deems the wallet as qualified, this wallet is saved as QUALIFIED without
        # alegeus setup or historic spend adjustment. This is incorrect and can give the user access to funds that they
        # should not have.

        # 4. However, in this flow:
        #    - The wallet cannot be fully qualified until the wallet is setup in Alegeus and historical adjustments are
        #    applied
        #    - The member is waiting for a response from the WQS about the status of their application in real time
        #    (webpage shows a spinner)
        #    - Alegeus is slower than a particularly slow glacier

        # 5. To resolve this:
        #    - When the WQS sends a QUALIFIED wallet message, the mono e.p will instead override this to create a
        #    PENDING wallet
        #    - An RQ job will then be spun off to create the various IDs for the wallet & perform the Alegeus operations
        #    - The mono e.p will fib to the WQS and claim that a qualified wallet has been created
        #    - The user will see a message saying that the wallet is in the process of setup
        #      (text update done by wei)

        # 6. The override and the fib are a consequence of running out of time to update the WQS back end at this time.
        # We will revisit in future.

        if post_request.state != WalletState.QUALIFIED:
            state, note = (
                post_request.state,
                f"{WALLET_QUALIFICATION_SERVICE_TAG}. State:{post_request.state}; ",
            )
            override_flag = False
        else:
            state, note = (
                WalletState.PENDING,
                f"{WALLET_QUALIFICATION_SERVICE_TAG}; QUALIFIED state overridden to PENDING; ",
            )
            override_flag = True
        log.info(
            "POST - WQS Auto config",
            user_id=str(self.user.id),
            reimbursement_method=reimbursement_method and reimbursement_method.value,
            primary_expense_type=primary_expense_type and primary_expense_type.value,
            post_request_state=post_request.state,
            state=str(state),
            note=note,
        )

        new_wallet = ReimbursementWallet(
            member=self.user,
            reimbursement_organization_settings_id=reimbursement_organization_settings_id,
            state=state,
            reimbursement_method=reimbursement_method,
            primary_expense_type=primary_expense_type,
            # we write either initial_eligibility_member_id or initial_eligibility_verification_id
            initial_eligibility_member_id=verification.eligibility_member_id,  # type: ignore[union-attr] # Item "None" of "Optional[EligibilityVerification]" has no attribute "eligibility_member_id"
            initial_eligibility_verification_id=(
                None
                if verification.eligibility_member_id  # type: ignore[union-attr] # Item "None" of "Optional[EligibilityVerification]" has no attribute "eligibility_member_id"
                else verification.verification_id
            ),  # type: ignore[union-attr] # Item "None" of "Optional[EligibilityVerification]" has no attribute "verification_id"
            initial_eligibility_member_2_id=eligibility_member_2_id,
            initial_eligibility_member_2_version=eligibility_member_2_version,
            initial_eligibility_verification_2_id=eligibility_verification_2_id,
            note=note,
        )
        reimbursement_wallet_user = ReimbursementWalletUsers(
            reimbursement_wallet_id=new_wallet.id,
            user_id=self.user.id,
            type=post_request.wallet_user_type,
            status=post_request.wallet_user_status,
        )

        try:
            log.info(
                "Creating new wallet for user",
                user_id=f'"{self.user.id}"',
                wallet_user_status=str(post_request.wallet_user_status),
                wallet_user_type=str(post_request.wallet_user_type),
                state=str(state),
            )
            db.session.add(new_wallet)
            log.info(
                "Created new reimbursement wallet",
                user_id=f'"{self.user.id}"',
                wallet_id=f'"{new_wallet.id}"',
            )
            db.session.add(reimbursement_wallet_user)

            authorized_dependent = _add_wallet_authorized_user(
                dependent_first_name_from_request=post_request.dependent_first_name,
                dependent_last_name_from_request=post_request.dependent_last_name,
                user=self.user,
                wallet=new_wallet,
                user_type=post_request.wallet_user_type,
            )
            if (
                authorized_dependent is not None
                and post_request.wallet_user_type == WalletUserType.DEPENDENT
                and reimbursement_wallet_user.type == WalletUserType.DEPENDENT
                and reimbursement_wallet_user.alegeus_dependent_id is None
            ):
                # https://mavenclinic.atlassian.net/browse/PAY-6292
                # avoid trying to create two alegeus dependents for one user when a dependent creates the wallet.
                reimbursement_wallet_user.alegeus_dependent_id = (
                    authorized_dependent.alegeus_dependent_id
                )
                db.session.add(reimbursement_wallet_user)
            db.session.commit()
        except Exception as error:
            log.error(
                "Could not create wallet for user.",
                traceback=format_exc(),
                user_id=f"{self.user.id}",
                error=str(error),
            )
            abort("500", message=f"Could not create wallet {error}")
        else:
            get_or_create_rwu_channel(reimbursement_wallet_user)

            # now spin off the asynch job to do stuff only if WQS tried to qualify a wallet
            if override_flag and new_wallet.state == WalletState.PENDING:
                log.info(
                    "WQS: Spinning off RQ job to try to the qualify the wallet.",
                    wallet_id=str(new_wallet.id),
                )
                stats.increment(
                    metric_name="wallet.resources.wqs_wallet.WQSWalletResource.post_launch_rq_for_qualification",
                    pod_name=stats.PodNames.BENEFITS_EXP,
                )
                handle_qualification_of_wallet_created_by_wqs.delay(
                    wallet_id=new_wallet.id
                )
            else:
                log.info(
                    "WQS: RQ job for wallet was not spun off.",
                    wallet_id=str(new_wallet.id),
                    wallet_state=str(new_wallet.state),
                )
            if post_request.state == WalletState.PENDING:
                # has to be called after the wallet is persisted to the DB so that wallet fields used by zendesk library
                # are fully populated
                _create_zendesk_ticket(new_wallet, reimbursement_wallet_user)

        # Fib to the WQS if the wallet was overridden to  PENDING. Qualification happens post Alegeus in RQ
        reported_state = (
            WalletState.QUALIFIED
            if (override_flag and new_wallet.state == WalletState.PENDING)
            else new_wallet.state
        )

        return (
            WQSWalletPOSTResponse(
                wallet_id=str(new_wallet.id),
                wallet_user_status=reimbursement_wallet_user.status.value,
                state=reported_state,
                wallet_user_type=reimbursement_wallet_user.type.value,
                reimbursement_method=str(new_wallet.reimbursement_method)
                if new_wallet.reimbursement_method is not None
                else None,
                primary_expense_type=str(new_wallet.primary_expense_type)
                if new_wallet.primary_expense_type is not None
                else None,
                is_inside_the_usa=post_request.is_inside_the_usa,
            ),
            201,
        )


class WQSWalletPutResource(InternalServiceResource):
    def put(self, wallet_id: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """Update an existing wallet."""
        put_request = WQSWalletPUTRequest.from_request(
            request.json if request.is_json else {}
        )
        wallet_and_rwu: WalletAndRWU = (
            ReimbursementWalletRepository().get_wallet_and_rwu(
                wallet_id=int(wallet_id),
                user_id=self.user.id,
            )
        )
        wallet = wallet_and_rwu.wallet
        rwu = wallet_and_rwu.rwu
        if not wallet:
            log.info(
                "Unable to find wallet",
                user_id=str(self.user.id),
                wallet_id=wallet_id,
            )
            return {}, 404
        # First check if this is possible via the Share a Wallet workflow:
        invitation = WalletUserInviteRepository().get_latest_unclaimed_invite(
            self.user.id
        )
        result = check_invitation(self.user, "", invitation)
        if result is None:
            # This means that we have a valid invitation to use.
            # Do NOT configure the wallet.
            if wallet.state != WalletState.QUALIFIED:
                log.error(
                    "User should not be able to apply to a non-QUALIFIED wallet",
                    invitation_id=str(invitation.id),
                    wallet_id=str(wallet.id),
                    user_id=str(self.user.id),
                )
            elif not wallet.is_shareable:
                log.error(
                    "User should not be able to apply to a non-shareable wallet",
                    invitation_id=str(invitation.id),
                    wallet_id=str(wallet.id),
                    user_id=str(self.user.id),
                )
                return {}, 400
            else:
                # Add or create the RWU.
                if rwu is None:
                    rwu = ReimbursementWalletUsers(
                        reimbursement_wallet_id=invitation.reimbursement_wallet_id,
                        user_id=self.user.id,
                        type=put_request.wallet_user_type,
                        status=put_request.wallet_user_status,
                    )
                    if put_request.wallet_user_type == WalletUserType.DEPENDENT:
                        # If we have a dependent, then we need an alegeus_dependent_id
                        rwu.alegeus_dependent_id = secrets.token_hex(15)
                else:
                    # THE WQS makes sure that people who are reapplying
                    # only submit the PENDING or DENIED WalletUserStatus.
                    if put_request.wallet_user_status == WalletUserStatus.REVOKED:
                        log.error(
                            "Cannot change existing RWU to ACTIVE or REVOKED via the WQS.",
                            user_id=str(self.user.id),
                            wallet_user_status=put_request.wallet_user_status.strip().upper(),
                        )
                        return {}, 400
                    if rwu.status != WalletUserStatus.DENIED:
                        log.error(
                            "Cannot change existing RWU that is not DENIED.",
                            user_id=str(self.user.id),
                            current_wallet_user_status=rwu.status.value,  # type: ignore
                        )
                        return {}, 400

                    rwu.type = put_request.wallet_user_type
                    rwu.status = put_request.wallet_user_status
                db.session.add(rwu)
                db.session.commit()
                get_or_create_rwu_channel(rwu)
                if (
                    put_request.wallet_user_status == WalletUserStatus.PENDING
                    and rwu.zendesk_ticket_id is None
                ):
                    _create_zendesk_ticket(wallet, rwu)
                # Do we add authorized users?
                if rwu.status != WalletUserStatus.DENIED:
                    # The user gets to reapply if they got denied.
                    mark_invitation_as_claimed(invitation)  # type: ignore
                return (
                    WQSWalletPUTResponse(
                        wallet_id=str(wallet_id),
                        state=wallet.state.value,
                        wallet_user_status=rwu.status.value,  # type: ignore
                        wallet_user_type=rwu.type.value,  # type: ignore
                        reimbursement_method=None,
                        primary_expense_type=None,
                        is_inside_the_usa=None,
                    ),
                    200,
                )
        if put_request.state not in PUT_ACCEPTABLE_WALLET_STATES:
            log.info(
                f"Unable to perform update because the requested wallet state is not in {PUT_ACCEPTABLE_WALLET_STATES}",
                user_id=str(self.user.id),
                wallet_id=wallet_id,
                state=put_request.state.value,
                wallet_user_status=put_request.wallet_user_status.value,
            )
            return {}, 400
        rwu.status = put_request.wallet_user_status
        rwu.type = put_request.wallet_user_type
        wallet.state = put_request.state
        primary_expense_type = put_request.primary_expense_type
        wallet.primary_expense_type = primary_expense_type

        reimbursement_method = _get_reimbursement_method(
            wallet.reimbursement_organization_settings_id,
            put_request.primary_expense_type,
            put_request.is_inside_the_usa,
        )

        wallet.reimbursement_method = reimbursement_method

        log.info(
            "PUT - WQS Auto config",
            user_id=str(self.user.id),
            reimbursement_method=reimbursement_method and reimbursement_method.value,
            primary_expense_type=primary_expense_type and primary_expense_type.value,
        )

        db.session.add_all([rwu, wallet])

        _add_wallet_authorized_user(
            dependent_first_name_from_request=put_request.dependent_first_name,
            dependent_last_name_from_request=put_request.dependent_last_name,
            user=self.user,
            wallet=wallet,
            user_type=put_request.wallet_user_type,
        )

        db.session.commit()
        return (
            WQSWalletPUTResponse(
                wallet_id=str(wallet_id),
                state=wallet.state.value,
                wallet_user_status=rwu.status.value,
                wallet_user_type=rwu.type.value,
                reimbursement_method=str(wallet.reimbursement_method)
                if wallet.reimbursement_method is not None
                else None,
                primary_expense_type=str(wallet.primary_expense_type)
                if wallet.primary_expense_type is not None
                else None,
                is_inside_the_usa=put_request.is_inside_the_usa,
            ),
            200,
        )


def _add_wallet_authorized_user(
    dependent_first_name_from_request: Optional[str],
    dependent_last_name_from_request: Optional[str],
    user: User,
    wallet: ReimbursementWallet,
    user_type: WalletUserType,
) -> Optional[OrganizationEmployeeDependent]:

    if user_type == WalletUserType.EMPLOYEE:
        # When the request is from an employee with a partner, need to add
        # the partner to the OrganizationEmployeeDependent table
        if (
            dependent_first_name_from_request is not None
            and dependent_last_name_from_request is not None
        ):
            log.info(
                "[Add wallet authorized user]The request is from an employee with a partner",
                user_id=user.id,
            )

            return _add_wallet_authorized_user_impl(
                dependent_first_name=cast(str, dependent_first_name_from_request),
                dependent_last_name=cast(str, dependent_last_name_from_request),
                user_id=user.id,
                wallet=wallet,
            )
        else:
            # When the request is from an employee without a partner, no need to add
            # the partner to the OrganizationEmployeeDependent table
            log.info(
                "[Add wallet authorized user]The request is from an employee without a partner",
                user_id=user.id,
            )
            return None
    else:
        # The request is from a partner.
        # Need to add the partner to the OrganizationEmployeeDependent table
        log.info(
            "[Add wallet authorized user]The request is from a partner", user_id=user.id
        )

        return _add_wallet_authorized_user_impl(
            dependent_first_name=cast(str, user.first_name),
            dependent_last_name=cast(str, user.last_name),
            user_id=user.id,
            wallet=wallet,
        )


def _add_wallet_authorized_user_impl(
    dependent_first_name: str,
    dependent_last_name: str,
    user_id: int,
    wallet: ReimbursementWallet,
) -> Optional[OrganizationEmployeeDependent]:

    possible_existing_dependent: Optional[OrganizationEmployeeDependent] = (
        (db.session.query(OrganizationEmployeeDependent))
        .filter(
            OrganizationEmployeeDependent.reimbursement_wallet_id == wallet.id,
            OrganizationEmployeeDependent.first_name == dependent_first_name,
            OrganizationEmployeeDependent.last_name == dependent_last_name,
        )
        .scalar()
    )

    if possible_existing_dependent is not None:
        log.info(
            "[Add wallet authorized user]The dependent is already exists. Updating the wallet authorized user",
            user_id=user_id,
            wallet_id=wallet.id,
        )
        possible_existing_dependent.first_name = dependent_first_name
        possible_existing_dependent.last_name = dependent_last_name
        possible_existing_dependent.reimbursement_wallet = wallet

        db.session.add(possible_existing_dependent)
        log.info(
            "[Add wallet authorized user]Updated the authorized user to wallet",
            user_id=user_id,
            wallet_id=wallet.id,
        )
        return possible_existing_dependent
    else:
        log.info(
            "[Add wallet authorized user]The dependent does not exist. Creating the wallet authorized user",
            user_id=user_id,
            wallet_id=wallet.id,
        )
        dependent = OrganizationEmployeeDependent(
            first_name=dependent_first_name,
            last_name=dependent_last_name,
            reimbursement_wallet=wallet,
            alegeus_dependent_id=secrets.token_hex(15),
        )
        db.session.add(dependent)
        log.info(
            "[Add wallet authorized user]Created the authorized user to wallet",
            user_id=user_id,
            wallet_id=wallet.id,
        )
        return dependent


class WQSWalletPOSTResponse(TypedDict):

    wallet_id: str
    wallet_user_status: str
    state: str
    wallet_user_type: str
    reimbursement_method: Optional[str]
    primary_expense_type: Optional[str]
    is_inside_the_usa: Optional[bool]


class WQSWalletPUTResponse(TypedDict):

    state: str
    wallet_id: str
    wallet_user_status: str
    wallet_user_type: str
    reimbursement_method: Optional[str]
    primary_expense_type: Optional[str]
    is_inside_the_usa: Optional[bool]


def _get_reimbursement_method(
    reimbursement_organization_settings_id: int,
    primary_expense_type: Optional[ReimbursementRequestExpenseTypes],
    is_inside_the_usa: Optional[bool],
) -> Optional[ReimbursementMethod]:
    if primary_expense_type is None:
        return None

    if is_inside_the_usa is False:
        return ReimbursementMethod.PAYROLL

    # Look up the (reimbursement_organization_settings_id, primary_expense_type) combination
    # in the reimbursement_organization_settings_expense_types table and get the resulting
    # reimbursement_method, which you should overwrite on the reimbursement_wallet.
    return (
        db.session.query(ReimbursementOrgSettingsExpenseType.reimbursement_method)
        .filter(
            ReimbursementOrgSettingsExpenseType.reimbursement_organization_settings_id
            == reimbursement_organization_settings_id,
            ReimbursementOrgSettingsExpenseType.expense_type == primary_expense_type,
        )
        .scalar()
    )


def _create_zendesk_ticket(
    wallet: ReimbursementWallet, reimbursement_wallet_user: ReimbursementWalletUsers
) -> None:
    """
    Create the zendesk ticket and stamp it on the reimbursement_wallet_user. Does not commit an expects the caller to
    commit
    :param wallet: The wallet that failed qualification
    :param reason: The reason the wallet failed qualification
    """
    try:
        content = "Created in PENDING state by wallet qualification service (did not auto-qualify)."
        ticket_id = open_zendesk_ticket(
            reimbursement_wallet_user,
            content=content,
            called_by=WQS_MONO_RESOURCE,
            additional_tags=[WALLET_APPLICATION_MANUAL_REVIEW_TAG],
        )
        db.session.commit()
        log.info(
            "Unable to Qualify wallet. Zendesk ticket created.",
            wallet_id=str(wallet.id),
            ticket_id=str(ticket_id),
            additional_tags=[WALLET_APPLICATION_MANUAL_REVIEW_TAG],
            content=content,
            called_by=WQS_MONO_RESOURCE,
            user_id=str(reimbursement_wallet_user.user_id),
            reimbursement_wallet_user_id=str(reimbursement_wallet_user.id),
        )
    except Exception as e:
        log.error(
            "Unable to send Zendesk ticket",
            wallet_id=str(wallet.id),
            wallet_state=str(wallet.state),
            error=e,
            traceback=traceback.format_exc(),
        )
