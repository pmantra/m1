from __future__ import annotations

from traceback import format_exc
from typing import Optional

from flask import request
from flask_babel import gettext
from flask_restful import abort
from sqlalchemy import literal
from sqlalchemy.orm import joinedload

import eligibility
from authn.models.user import User
from common.services.api import PermissionedUserResource
from cost_breakdown.utils.helpers import get_scheduled_tp_and_pending_rr_costs
from direct_payment.payments.estimates_helper import EstimatesHelper
from direct_payment.payments.payment_records_helper import PaymentRecordsHelper
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureStatus,
)
from eligibility import e9y
from storage.connection import db
from tracks import service as tracks_service
from utils.log import logger
from utils.marshmallow_experiment import marshmallow_experiment_enabled
from utils.service_owner_mapper import service_ns_team_mapper
from wallet.models.constants import (
    BenefitTypes,
    WalletState,
    WalletUserMemberStatus,
    WalletUserStatus,
    WalletUserType,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.repository.reimbursement_wallet import ReimbursementWalletRepository
from wallet.resources.common import (
    PaymentBlock,
    ReimbursementRequestBlock,
    TreatmentBlock,
    WalletResourceMixin,
)
from wallet.schemas.constants import TreatmentVariant
from wallet.schemas.reimbursement_wallet import (
    ReimbursementWalletGETResponseSchema,
    ReimbursementWalletPOSTRequest,
    ReimbursementWalletPUTRequestSchema,
    ReimbursementWalletResponseSchema,
)
from wallet.schemas.reimbursement_wallet_v3 import ReimbursementWalletResponseSchemaV3
from wallet.services.currency import CurrencyService
from wallet.services.payments import assign_payments_customer_id_to_wallet_async
from wallet.services.reimbursement_budget_calculator import (
    get_allowed_category_associations_by_wallet,
)
from wallet.services.reimbursement_request import ReimbursementRequestService
from wallet.services.reimbursement_wallet_messaging import (
    get_or_create_rwu_channel,
    open_zendesk_ticket,
)
from wallet.utils.alegeus.enrollments.enroll_wallet import check_hdhp_status
from wallet.utils.pharmacy import get_pharmacy_details_for_wallet

log = logger(__name__)

ReimbursementWalletHDHPStatusMap = {
    None: "NONE",
    True: "MET",
    False: "UNMET",
}


class ReimbursementWalletResource(PermissionedUserResource):
    def __init__(self) -> None:
        self.currency_service = CurrencyService()

    def get(self) -> dict:
        """View all of a user's reimbursement wallets."""
        get_non_member_dependents = (
            request.args.get("get_non_member_dependents", "").strip().lower() == "true"
        )

        wallets_channels_and_zendesk_tickets = (
            db.session.query(
                ReimbursementWallet,
                ReimbursementWalletUsers.channel_id,
                ReimbursementWalletUsers.zendesk_ticket_id,
            )
            .join(
                ReimbursementWalletUsers,
                ReimbursementWalletUsers.reimbursement_wallet_id
                == ReimbursementWallet.id,
            )
            .filter(
                ReimbursementWalletUsers.user_id == self.user.id,
                ReimbursementWalletUsers.status == WalletUserStatus.ACTIVE,
            )
            .options(
                joinedload("reimbursement_organization_settings").joinedload(
                    "allowed_reimbursement_categories"
                )
            )
            .order_by(
                ReimbursementWallet.state.asc()
            )  # TODO: Prioritize qualified wallet if multiple found. Qualified = 1, Expired = 3
            .all()
        )

        wallet_list = [
            add_wallet_response_properties(
                self.currency_service,
                self.user,
                wallet,
                channel_id,
                zendesk_ticket,
                get_non_member_dependents,
            )
            for wallet, channel_id, zendesk_ticket in wallets_channels_and_zendesk_tickets
        ]

        data = {"data": wallet_list}
        schema = ReimbursementWalletGETResponseSchema()
        return schema.dump(data).data

    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Create a new ReimbursementWallet for a user.
        WQSWalletResource is the endpoint used by the Wallet Qualification Service
        to create and modify wallets. It must perform the same checks, so any requirements
        to create a wallet should be duplicated for that endpoint as well.
        """
        post_request = ReimbursementWalletPOSTRequest.from_request(
            request.json if request.is_json else None
        )

        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            "experiment-marshmallow-reimbursement-wallet-resource",
            self.user.esp_id if self.user else None,
            self.user.email if self.user else None,
            default=False,
        )

        track_svc = tracks_service.TrackSelectionService()
        if not track_svc.is_enterprise(user_id=self.user.id):
            abort(403, message="Not Authorized")

        enrolled_org_id = track_svc.get_organization_id_for_user(user_id=self.user.id)
        verification_svc: eligibility.EnterpriseVerificationService = (
            eligibility.get_verification_service()
        )
        verification: Optional[
            e9y.EligibilityVerification
        ] = verification_svc.get_verification_for_user_and_org(
            user_id=self.user.id, organization_id=enrolled_org_id
        )

        if not verification:
            abort(403, message="Not Authorized for Wallet")

        reimbursement_organization_settings_id = int(
            post_request.reimbursement_organization_settings_id
        )
        organization_id = (
            db.session.query(ReimbursementOrganizationSettings.organization_id)
            .filter(
                ReimbursementOrganizationSettings.id
                == reimbursement_organization_settings_id
            )
            .scalar()
        )
        if organization_id is None or organization_id != verification.organization_id:  # type: ignore[union-attr] # Item "None" of "Optional[EligibilityVerification]" has no attribute "organization_id"
            abort(403, message="Not Authorized for that Wallet Organization")

        # Check whether a wallet already exists.
        existing_wallet_info = (
            db.session.query(
                ReimbursementWallet,
                ReimbursementWalletUsers.channel_id,
                ReimbursementWalletUsers.zendesk_ticket_id,
            )
            .join(
                ReimbursementWalletUsers,
                ReimbursementWalletUsers.reimbursement_wallet_id
                == ReimbursementWallet.id,
            )
            .filter(
                ReimbursementWalletUsers.user_id == self.user.id,
                ReimbursementWallet.reimbursement_organization_settings_id
                == reimbursement_organization_settings_id,
            )
            .all()
        )
        is_whitelisted_for_survey_automation = True
        if is_whitelisted_for_survey_automation:
            # If the organization uses survey automation, then we want
            # to avoid sending a 409 when the wallet already exists
            if existing_wallet_info and existing_wallet_info[0]:
                # If we return a 409 error, then this will cause many client devices
                # that use out-of-date releases to display errors when it shouldn't
                # be considered an error. This is mainly an issue in the Automatic
                # Wallet Qualification workflows.
                existing_wallet, channel_id, zendesk_ticket_id = existing_wallet_info[0]

                # During the transition period from using the SurveyMonkey
                # surveys to using the Wallet Qualification Service's
                # automated surveys, client devices will still make a
                # POST call to create a new wallet EVEN though the POST call
                # is already being made from the WQS backend. If we return a 409
                # because the wallet already exists, then the devices will show
                # an error notification, which we would like to avoid. Hence, we
                # will return a 200 even though no new wallet was created.
                log.warn(
                    "Whitelisted for survey automation and user tried to create duplicate wallet",
                    user_id=self.user.id,
                )
                data = {
                    "data": add_wallet_response_properties(
                        self.currency_service,
                        self.user,
                        existing_wallet,
                        channel_id,
                        zendesk_ticket_id,
                    )
                }
                schema = (
                    ReimbursementWalletResponseSchemaV3()  # type: ignore[arg-type]
                    if experiment_enabled
                    else ReimbursementWalletResponseSchema()
                )
                return (
                    schema.dump(data) if experiment_enabled else schema.dump(data).data  # type: ignore[attr-defined]
                )
        else:
            if existing_wallet_info and existing_wallet_info[0]:
                # Existing behavior for organizations not using
                # WQS and the user already has a wallet.
                log.warn("User tried to create duplicate wallet", user_id=self.user.id)
                abort(409, message="A wallet already exists for this user")

        eligibility_verification_2_id: Optional[int] = None
        eligibility_member_2_id: Optional[int] = None
        eligibility_member_2_version: Optional[int] = None

        if verification.eligibility_member_id:
            eligibility_member_2_id = verification.eligibility_member_2_id
            eligibility_member_2_version = verification.eligibility_member_2_version
        else:
            eligibility_verification_2_id = verification.verification_2_id

        # Todo: get initial_eligibility_verification_id
        #  once reading from new data model enabled in e9y
        new_wallet = ReimbursementWallet(
            member=self.user,
            reimbursement_organization_settings_id=reimbursement_organization_settings_id,
            state=post_request.initial_wallet_state,
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
        )

        if self.user.is_employee_with_maven_benefit:
            user_type = WalletUserType.EMPLOYEE
        else:
            user_type = WalletUserType.DEPENDENT
        reimbursement_wallet_user = ReimbursementWalletUsers(
            reimbursement_wallet_id=new_wallet.id,
            user_id=self.user.id,
            type=user_type,
            status=WalletUserStatus.ACTIVE,
        )

        try:
            log.info("Creating new wallet for user")
            db.session.add(new_wallet)
            log.info(
                "Created new reimbursement wallet",
                user_id=str(self.user.id),
                wallet_id=f'"{new_wallet.id}"',
            )
            db.session.add(reimbursement_wallet_user)
            db.session.commit()
        except Exception as error:
            log.error(
                "Could not create wallet.",
                traceback=format_exc(),
                user_id=str(self.user.id),
                error=error,
            )
            abort("500", message=f"Could not create wallet {error}")
        else:
            channel = get_or_create_rwu_channel(reimbursement_wallet_user)
            zendesk_ticket_id = open_zendesk_ticket(reimbursement_wallet_user)

        data = {
            "data": add_wallet_response_properties(
                self.currency_service,
                self.user,
                new_wallet,
                channel.id,
                zendesk_ticket_id,
            )
        }
        schema = (
            ReimbursementWalletResponseSchemaV3()  # ignore: type[attr-defined]
            if experiment_enabled
            else ReimbursementWalletResponseSchema()
        )
        return schema.dump(data) if experiment_enabled else schema.dump(data).data  # type: ignore[attr-defined]


class ReimbursementWalletsResource(PermissionedUserResource, WalletResourceMixin):
    def __init__(self) -> None:
        self.currency_service = CurrencyService()

    def put(self, wallet_id: int) -> dict:
        """Update an existing reimbursement wallet's state or settings."""
        schema = ReimbursementWalletPUTRequestSchema()
        args = schema.load(request.json if request.is_json else None).data

        wallet = self._wallet_or_404(self.user, wallet_id)
        try:
            reimbursement_org_settings_id: Optional[int] = args.get(
                "reimbursement_organization_settings_id"
            )

            if reimbursement_org_settings_id is not None:
                # Attempting to move a wallet from one setting to another,
                # in an organization with multiple settings.
                if (
                    reimbursement_org_settings_id
                    != wallet.reimbursement_organization_settings_id
                ):
                    new_settings = ReimbursementOrganizationSettings.query.filter(
                        ReimbursementOrganizationSettings.id
                        == args.get("reimbursement_organization_settings_id")
                    ).one_or_none()
                    if not new_settings:
                        abort(
                            404, message="ReimbursementOrganizationSettings not found."
                        )
                    if (
                        new_settings.organization
                        is not wallet.reimbursement_organization_settings.organization
                    ):
                        abort(
                            400,
                            message="Cannot move a wallet from one organization to another.",
                        )

                    # settings can differ in categories --
                    # validate the end state of existing requests
                    if len(wallet.reimbursement_requests) > 0:
                        old_allowed_categories = (
                            wallet.get_or_create_wallet_allowed_categories
                        )
                        old_categories = {
                            allowed.reimbursement_request_category
                            for allowed in old_allowed_categories
                        }
                        new_categories = {
                            allowed.reimbursement_request_category
                            for allowed in new_settings.allowed_reimbursement_categories
                        }
                        if not old_categories.issubset(new_categories):
                            abort(
                                400,
                                message="Cannot make changes to a wallet "
                                "that would invalidate existing category settings. "
                                "New categories must be a superset of old categories.",
                            )
                    wallet.reimbursement_organization_settings = new_settings

            if args.get("state") is not None:
                old_state = wallet.state
                new_state = WalletState[args.get("state")]
                if old_state != new_state and new_state == WalletState.PENDING:
                    wallet.state = new_state

            db.session.add(wallet)
            db.session.commit()
        except ValueError as e:
            abort(400, data=None, errors=[{"field": None, "message": str(e)}])
        channel_id, zendesk_ticket_id = (
            db.session.query(
                ReimbursementWalletUsers.channel_id,
                ReimbursementWalletUsers.zendesk_ticket_id,
            )
            .filter(
                ReimbursementWalletUsers.reimbursement_wallet_id == wallet_id,
                ReimbursementWalletUsers.user_id == self.user.id,
                ReimbursementWalletUsers.status == WalletUserStatus.ACTIVE,
            )
            .one()
        )
        data = {
            "data": add_wallet_response_properties(
                self.currency_service, self.user, wallet, channel_id, zendesk_ticket_id
            )
        }
        schema = ReimbursementWalletResponseSchema()
        return schema.dump(data).data


def add_wallet_response_properties(
    currency_service: CurrencyService,
    user: User,
    wallet: ReimbursementWallet,
    channel_id: int | None,
    zendesk_ticket_id: int | None,
    get_non_member_dependents: bool = False,
) -> ReimbursementWallet:
    """
    Add additional properties for resource responses using ReimbursementWalletSchema
    """
    # We are unfortunately abusing the underlying __dict__ of a class,
    # adding properties to the ReimbursementWallet object that aren't on the table.
    # We then dump the __dict__ into json.
    wallet.channel_id = channel_id
    wallet.zendesk_ticket_id = zendesk_ticket_id

    # Payments Customer ID is on the wallet object and doesn't need to be added here, but should
    # be checked here to allow creation if it doesn't exist
    if (
        wallet.state == WalletState.QUALIFIED
        and not wallet.payments_customer_id
        and wallet.reimbursement_organization_settings.direct_payment_enabled
    ):
        service_ns_tag = "wallet"
        team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
        assign_payments_customer_id_to_wallet_async.delay(
            wallet.id, service_ns=service_ns_tag, team_ns=team_ns_tag
        )

    hdhp_status = check_hdhp_status(wallet)

    allowed_reimbursements = 0
    allowed_categories = wallet.get_or_create_wallet_allowed_categories
    for category in allowed_categories:
        if category.reimbursement_request_category_maximum:
            allowed_reimbursements += category.reimbursement_request_category_maximum
            category.reimbursement_request_category_maximum_amount = (
                currency_service.format_amount_obj(
                    amount=category.reimbursement_request_category_maximum,
                    currency_code=category.currency_code,
                )
            )
        if category.benefit_type == BenefitTypes.CYCLE:
            total_credits, remaining_credits, _ = wallet.get_direct_payment_balances()
            scheduled_and_pending_credits = get_scheduled_tp_and_pending_rr_costs(
                wallet, remaining_credits
            )
            category.credit_maximum = total_credits
            category.credits_remaining = (
                remaining_credits - scheduled_and_pending_credits
            )
    wallet.reimbursement_organization_settings.reimbursement_request_maximum = (
        allowed_reimbursements
    )
    (
        first_name,
        last_name,
        date_of_birth,
    ) = wallet.get_first_name_last_name_and_dob()
    wallet.employee = {
        "first_name": first_name,
        "last_name": last_name,
    }

    # This could technically cause an issue if there are multiple dependents with the
    # exact same first and last names, but this should be superficial and temporary.

    if get_non_member_dependents:
        # this query sorts the users coming back by NON_MEMBERS first, so as we build the map below
        # the member user would take precedence if there are any conflicts for users with the same name
        db_result = ReimbursementWalletRepository().get_users_in_wallet(wallet.id)
    else:
        employee_and_dependents = (WalletUserType.DEPENDENT, WalletUserType.EMPLOYEE)
        db_result = (
            db.session.query(
                User.id,
                User.first_name,
                User.last_name,
                ReimbursementWalletUsers.type,
                literal(WalletUserMemberStatus.MEMBER),
            )
            .join(ReimbursementWalletUsers, User.id == ReimbursementWalletUsers.user_id)
            .filter(
                ReimbursementWalletUsers.reimbursement_wallet_id == wallet.id,
                ReimbursementWalletUsers.type.in_(employee_and_dependents),
                ReimbursementWalletUsers.status == WalletUserStatus.ACTIVE,
            )
            .all()
        )

    # convert to a dict first with [last_name,first_name] as the key to dedup users with the same names
    reimbursement_wallet_user_info = {
        f"{entry.last_name},{entry.first_name}": entry for entry in db_result
    }.values()

    wallet.members = []
    wallet.dependents = []
    wallet.household = []
    for (
        id,
        first_name,
        last_name,
        user_type,
        membership_status,
    ) in reimbursement_wallet_user_info:
        user_info = {"id": id, "first_name": first_name, "last_name": last_name}

        wallet.household.append(user_info)

        if user_type == WalletUserType.EMPLOYEE:
            wallet.members.append(user_info)

        elif user_type == WalletUserType.DEPENDENT:
            wallet.dependents.append(user_info)

            if membership_status == WalletUserMemberStatus.MEMBER:
                wallet.members.append(user_info)

    try:
        payment_records_helper = PaymentRecordsHelper()
        upcoming_payments_result = (
            payment_records_helper.get_upcoming_payments_for_reimbursement_wallet(
                wallet
            )
        )
        if (
            not upcoming_payments_result
            or not upcoming_payments_result.upcoming_payments_and_summary
        ):
            wallet.upcoming_payments = None
            wallet.payment_block = None
        elif not upcoming_payments_result.upcoming_payments_and_summary.payments:
            wallet.upcoming_payments = None
            wallet.payment_block = PaymentBlock(
                variant=upcoming_payments_result.client_layout.value,
                show_benefit_amount=upcoming_payments_result.show_benefit_amount,
                num_errors=upcoming_payments_result.num_errors,
            )
        else:
            upcoming_payments = upcoming_payments_result.upcoming_payments_and_summary
            wallet.upcoming_payments = upcoming_payments
            wallet.payment_block = PaymentBlock(
                variant=upcoming_payments_result.client_layout.value,
                show_benefit_amount=upcoming_payments_result.show_benefit_amount,
                num_errors=upcoming_payments_result.num_errors,
            )
    except Exception as exc:
        log.error(
            "Exception while retrieving upcoming payment records",
            error=str(exc),
            traceback=format_exc(),
        )
    try:
        estimates_helper = EstimatesHelper()
        estimates_summary_result = estimates_helper.get_estimates_summary_by_wallet(
            wallet_id=wallet.id
        )
        wallet.estimate_block = (
            estimates_summary_result if estimates_summary_result else None
        )
    except Exception as exc:
        log.error(
            "Exception while retrieving upcoming estimates summary",
            error=str(exc),
            traceback=format_exc(),
        )

    if wallet.reimbursement_organization_settings.direct_payment_enabled:
        scheduled_tps = (
            TreatmentProcedure.query.filter(
                TreatmentProcedure.reimbursement_wallet_id == wallet.id,
                TreatmentProcedure.status == TreatmentProcedureStatus.SCHEDULED,
            )
            .order_by(TreatmentProcedure.start_date, TreatmentProcedure.created_at)
            .all()
        )
        if scheduled_tps:
            wallet.treatment_block = TreatmentBlock(
                variant=TreatmentVariant.IN_TREATMENT.value,
                clinic=scheduled_tps[0].fertility_clinic.name,
                clinic_location=scheduled_tps[0].fertility_clinic_location.name,
            )
        else:
            wallet.treatment_block = TreatmentBlock(variant=TreatmentVariant.NONE.value)

    # reimbursement request block
    reimbursement_request_service = ReimbursementRequestService()
    is_cost_share_breakdown_applicable = (
        reimbursement_request_service.is_cost_share_breakdown_applicable(wallet=wallet)
    )

    if is_cost_share_breakdown_applicable:
        wallet_category_associations = get_allowed_category_associations_by_wallet(
            wallet=wallet
        )
        wallet_category_labels = [
            category.label for category in wallet_category_associations
        ]

        reimbursement_requests = reimbursement_request_service.get_reimbursement_requests_for_wallet_rr_block(
            wallet_id=wallet.id, category_labels=wallet_category_labels
        )

        if len(reimbursement_requests) > 0:
            cost_breakdowns = reimbursement_request_service.get_latest_cost_breakdowns_by_reimbursement_request(
                reimbursement_requests
            )

            is_cost_breakdown_available_for_each_reimbursement_request = len(
                reimbursement_requests
            ) == len(cost_breakdowns)

            has_single_reimbursement_request = len(reimbursement_requests) == 1

            # assumes the currency code is the same across allowed categories
            rr_currency_code = reimbursement_requests[0].benefit_currency_code

            original_claim_amount_total = 0
            for rr in reimbursement_requests:
                cb = cost_breakdowns.get(rr.id)
                if cb:
                    original_claim_for_rr = (
                        cb.total_employer_responsibility
                        + cb.total_member_responsibility
                    )
                    original_claim_amount_total += original_claim_for_rr
                else:
                    original_claim_amount_total += rr.amount

            formatted_original_claim_amount_obj = currency_service.format_amount_obj(
                amount=original_claim_amount_total,
                currency_code=rr_currency_code,
            )

            original_claim_text = gettext("reimbursement_request_original_claim")

            if is_cost_breakdown_available_for_each_reimbursement_request:
                # assumes the currency code is the same across allowed categories
                cost_breakdowns_list = cost_breakdowns.values()
                expected_reimbursement_amount_total = original_claim_amount_total - sum(
                    cb.total_member_responsibility for cb in cost_breakdowns_list
                )
                formatted_expected_reimbursement_amount_obj = (
                    currency_service.format_amount_obj(
                        amount=expected_reimbursement_amount_total,
                        currency_code=rr_currency_code,
                    )
                )

                if has_single_reimbursement_request:
                    reimbursement_request = reimbursement_requests[0]
                    wallet.reimbursement_request_block = ReimbursementRequestBlock(
                        title=reimbursement_request.formatted_label,
                        total=len(reimbursement_requests),
                        reimbursement_text=gettext(
                            "reimbursement_request_estimated_return"
                        ),
                        expected_reimbursement_amount=formatted_expected_reimbursement_amount_obj.get(
                            "formatted_amount"
                        ),
                        original_claim_text=original_claim_text,
                        original_claim_amount=formatted_original_claim_amount_obj.get(
                            "formatted_amount"
                        ),
                        reimbursement_request_uuid=str(reimbursement_request.id),
                        details_text=None,
                        has_cost_breakdown_available=True,
                    )
                else:
                    expected_total_reimbursement_text = gettext(
                        "reimbursement_request_expected_total_reimbursement"
                    )
                    wallet.reimbursement_request_block = ReimbursementRequestBlock(
                        title=None,
                        total=len(reimbursement_requests),
                        reimbursement_text=expected_total_reimbursement_text,
                        expected_reimbursement_amount=formatted_expected_reimbursement_amount_obj.get(
                            "formatted_amount"
                        ),
                        original_claim_text=gettext(
                            "reimbursement_request_original_claims_total"
                        ),
                        original_claim_amount=formatted_original_claim_amount_obj.get(
                            "formatted_amount"
                        ),
                        reimbursement_request_uuid=None,
                        details_text=None,
                        has_cost_breakdown_available=True,
                    )
            else:
                if has_single_reimbursement_request:
                    reimbursement_request = reimbursement_requests[0]
                    wallet.reimbursement_request_block = ReimbursementRequestBlock(
                        title=reimbursement_request.formatted_label,
                        total=len(reimbursement_requests),
                        reimbursement_text=None,
                        expected_reimbursement_amount=None,
                        original_claim_text=original_claim_text,
                        original_claim_amount=formatted_original_claim_amount_obj.get(
                            "formatted_amount"
                        ),
                        reimbursement_request_uuid=str(reimbursement_request.id),
                        details_text=gettext(
                            "reimbursement_request_member_responsibility_will_be_deducted_message"
                        ),
                        has_cost_breakdown_available=False,
                    )
                else:
                    claims_processing_text = gettext(
                        "reimbursement_request_claims_processing"
                    )
                    wallet.reimbursement_request_block = ReimbursementRequestBlock(
                        title=f"{len(reimbursement_requests)} {claims_processing_text}",
                        total=len(reimbursement_requests),
                        reimbursement_text=None,
                        expected_reimbursement_amount=None,
                        original_claim_text=None,
                        original_claim_amount=None,
                        reimbursement_request_uuid=None,
                        details_text=gettext(
                            "reimbursement_request_view_all_claims_details_message"
                        ),
                        has_cost_breakdown_available=False,
                    )

    wallet.hdhp_status = ReimbursementWalletHDHPStatusMap[hdhp_status]
    wallet.debit_banner = wallet.get_debit_banner(hdhp_status)
    wallet.pharmacy = get_pharmacy_details_for_wallet(member=user, wallet=wallet)
    return wallet
