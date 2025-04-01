from __future__ import annotations

import dataclasses
import datetime
import traceback
from decimal import ROUND_DOWN, Decimal
from typing import List, Optional

from maven.feature_flags import bool_variation
from sqlalchemy import exc
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

from common import stats
from cost_breakdown.constants import ClaimType
from cost_breakdown.models.cost_breakdown import CostBreakdown
from payer_accumulator.accumulation_mapping_service import AccumulationMappingService
from payer_accumulator.models.payer_accumulation_reporting import (  # noqa: F401
    PayerAccumulationReports,
)
from storage.connection import db
from utils.log import logger
from utils.payments import convert_dollars_to_cents
from wallet import alegeus_api
from wallet.alegeus_api import (
    format_date_from_string_to_datetime,
    is_request_successful,
)
from wallet.models.constants import (
    AlegeusAccountType,
    AlegeusClaimStatus,
    BenefitTypes,
    ReimbursementRequestAutoProcessing,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    ReimbursementRequestType,
)
from wallet.models.reimbursement import (
    ReimbursementAccount,
    ReimbursementClaim,
    ReimbursementPlan,
    ReimbursementRequest,
    ReimbursementRequestCategory,
    ReimbursementRequestCategoryExpenseTypes,
    WalletExpenseSubtype,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.repository.cycle_credits import CycleCreditsRepository
from wallet.services.currency import CurrencyService
from wallet.utils.alegeus.claims.create import create_direct_payment_claim_in_alegeus
from wallet.utils.common import (
    create_refund_reimbursement_request,
    increment_reimbursement_request_field_update,
)
from wallet.utils.events import send_reimbursement_request_state_event
from wallet.utils.payment_ops import (
    SyncAccountSccPaymentOpsZendeskTicket,
    SyncCreditPaymentOpsZendeskTicket,
)

log = logger(__name__)

metric_prefix = "api.wallet.utils.alegeus.claims.sync"
REIMBURSEMENTS_MANUAL_DEDUCT_CREDITS_FLAG = (
    "enable-reimbursement-request-manual-deduct-credits"
)


@dataclasses.dataclass
class WalletClaims:
    __slots__ = ("wallet", "claims")
    wallet: ReimbursementWallet
    claims: List[ReimbursementClaim]


@dataclasses.dataclass
class AlegeusClaim:
    __slots__ = (
        "tracking_number",
        "status",
        "amount",
        "claim_key",
        "account_type_code",
        "flex_account_key",
        "service_category_code",
        "service_start_date",
    )
    tracking_number: str
    status: str
    amount: Optional[Decimal]
    claim_key: Optional[int]
    account_type_code: Optional[str]
    flex_account_key: Optional[int]
    service_category_code: Optional[str]
    service_start_date: Optional[datetime.datetime]


# Used when a duplicate subtype code means we have to choose which type to apply it to
PRIORITIZED_EXPENSE_TYPES = [
    ReimbursementRequestExpenseTypes.FERTILITY,
    ReimbursementRequestExpenseTypes.PRESERVATION,
]


def sync_pending_claims(wallets_to_claims: List[WalletClaims], timeout: int = 2):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Syncs Statuses and Amounts for ReimbursementRequests and ReimbursementClaims that have not yet been reimbursed.
    This includes ReimbursementRequests with 'state' as: PENDING, APPROVED, DENIED
    and excludes those with 'state' as: NEW, FAILED, REIMBURSED

    Additionally, these ReimbursementRequests have already been submitted to Alegeus
    and have a ReimbursementClaim linked to them.
    """

    def tag_successful(
        successful: bool,
        reimbursement_claim_status: Optional[str] = None,
        reimbursement_request_state: Optional[ReimbursementRequestState] = None,
        error_cause: Optional[str] = None,
    ) -> None:
        metric_name = f"{metric_prefix}.sync_pending_claims"
        if successful:
            tags = ["sync_complete:true"]
            tags.append(f"reimbursement_claim_status:{reimbursement_claim_status}")
            tags.append(
                f"reimbursement_request_state:{reimbursement_request_state and reimbursement_request_state.name}"
            )
        else:
            tags = ["sync_complete:false", "error:true", f"error_cause:{error_cause}"]
            metric_name += ".error"
        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.PAYMENTS_POD,
            tags=tags,
        )

    log.info(
        f"Sync in progress for {len(wallets_to_claims)} wallets with pending claims"
    )

    api = alegeus_api.AlegeusApi()

    # Collection of updated ReimbursementRequests that need events triggered
    reimbursement_requests_to_event = []

    cycle_repository = CycleCreditsRepository(session=db.session)
    deduct_manual_credits_enabled = bool_variation(
        REIMBURSEMENTS_MANUAL_DEDUCT_CREDITS_FLAG, default=False
    )

    for wallet_with_claims in wallets_to_claims:
        wallet: ReimbursementWallet = wallet_with_claims.wallet
        pending_claims: List[ReimbursementClaim] = wallet_with_claims.claims

        try:
            response = api.get_employee_activity(wallet, timeout=timeout)

            if is_request_successful(response) and response.json() is not None:

                for claim in pending_claims:
                    request: ReimbursementRequest = claim.reimbursement_request

                    old_claim_status = claim.status
                    old_request_state = request.state

                    old_claim_amount = claim.amount
                    old_request_amount = request.amount

                    old_request_category = request.category
                    old_request_expense_type = request.expense_type
                    old_request_expense_subtype = request.wallet_expense_subtype

                    old_request_service_start_date = request.service_start_date

                    old_claim_key = claim.alegeus_claim_key

                    alegeus_claim = _get_alegeus_claim_from_response(
                        response.json(),
                        claim.alegeus_claim_id,  # type: ignore[arg-type] # Argument 2 to "_get_alegeus_claim_from_response" has incompatible type "Optional[str]"; expected "str"
                    )
                    try:
                        if not alegeus_claim:
                            request.state = ReimbursementRequestState.NEW  # type: ignore[assignment] # Incompatible types in assignment (expression has type "ReimbursementRequestState", variable has type "str")
                            # Need to add the request before deleting the claim for session reasons
                            log.info(
                                "Updating a Reimbursement Request from Alegeus, without a claim.",
                                reimbursement_request_id=str(request.id),
                                old_request_state=old_request_state,
                                new_request_state=request.state,
                                old_request_amount=old_request_amount,
                                new_request_amount=request.amount,
                            )
                            db.session.add(request)
                            log.info(
                                "Deleting a Reimbursement Claim that does not exist in Alegeus",
                                claim_id=str(claim.id),
                                reimbursement_request_id=str(request.id),
                            )
                            db.session.query(ReimbursementClaim).filter(
                                ReimbursementClaim.id == claim.id
                            ).delete(synchronize_session="fetch")
                        else:
                            # If this is an auto-processed claim and only a DTR exists there is no need to update the
                            # RR because it could have multiple claims per RR and we only want to sync with the HRA
                            if (
                                alegeus_claim.account_type_code
                                == AlegeusAccountType.DTR.value
                                and request.auto_processed
                                == ReimbursementRequestAutoProcessing.RX
                            ):
                                continue

                            old_state = request.state

                            # Reimbursement Request state is updated here.
                            _sync_claim_and_request(request, claim, alegeus_claim)

                            # Approved mmb manual reimbursement requests are pushed to payer accumulation
                            if old_state != request.state:
                                reimbursement_requests_to_event.append(request)

                                if deduct_manual_credits_enabled:
                                    if _should_deduct_credits(request):
                                        cycle_credits = cycle_repository.get_cycle_credit_by_category(
                                            request.reimbursement_wallet_id,
                                            request.reimbursement_request_category_id,
                                        )
                                        # If there are failures, log+alert, don't raise. The claim has synced, and we
                                        # don't want to lose that.
                                        if not cycle_credits:
                                            log.error(
                                                "Failed to deduct credits: Cycle credits not found for Wallet+Category",
                                                reimbursement_request_id=str(
                                                    request.id
                                                ),
                                                reimbursement_request_category_id=str(
                                                    request.reimbursement_request_category_id
                                                ),
                                            )
                                            ticket = SyncCreditPaymentOpsZendeskTicket(
                                                user=wallet.reimbursement_wallet_users[
                                                    0
                                                ].member,  # for lack of a RR user, send the first wallet user
                                                wallet_id=wallet.id,
                                                reimbursement_request_id=request.id,
                                                reason="Cycle Credits not found for Wallet+Category",
                                            )
                                            ticket.update_zendesk()

                                        else:
                                            try:
                                                cycle_credits.deduct_credits_for_manual_reimbursement(
                                                    request
                                                )
                                            except Exception as e:
                                                log.error(
                                                    "Failed to deduct credits: Error editing balance",
                                                    reimbursement_request_id=str(
                                                        request.id
                                                    ),
                                                    reimbursement_request_category_id=str(
                                                        request.reimbursement_request_category_id
                                                    ),
                                                    reimbursement_cycle_credits_id=str(
                                                        cycle_credits.id
                                                    ),
                                                    error=e,
                                                )
                                                ticket = SyncCreditPaymentOpsZendeskTicket(
                                                    user=wallet.reimbursement_wallet_users[
                                                        0
                                                    ].member,  # for lack of a RR user, send the first wallet user
                                                    wallet_id=wallet.id,
                                                    reimbursement_request_id=request.id,
                                                    reason="Error storing credit deduction",
                                                )
                                                ticket.update_zendesk()

                                try:
                                    mapping_svc = AccumulationMappingService(
                                        session=db.session
                                    )
                                    if mapping_svc.reimbursement_request_is_valid_for_accumulation(
                                        request
                                    ):
                                        # this mimics accumulation file generator get_cost_breakdown
                                        # this should be refactored as shared code.
                                        cost_breakdown = (
                                            CostBreakdown.query.filter(
                                                CostBreakdown.reimbursement_request_id
                                                == request.id
                                            )
                                            .order_by(CostBreakdown.created_at.desc())
                                            .first()
                                        )
                                        if (
                                            cost_breakdown.hra_applied is not None
                                            and cost_breakdown.hra_applied > 0
                                            and request.state
                                            == ReimbursementRequestState.APPROVED
                                        ):
                                            _add_back_hra_to_alegeus_wallet_balance(
                                                reimbursement_request=request,
                                                hra_applied=cost_breakdown.hra_applied,
                                            )
                                        mapping = mapping_svc.accumulate_reimbursement_request_post_approval(
                                            reimbursement_request=request,
                                            cost_breakdown=cost_breakdown,
                                        )
                                        db.session.add(mapping)
                                except Exception as e:
                                    # We do not want mapping to break the alegeus sync.
                                    log.error(
                                        "Did not mark Reimbursement Request for accumulation.",
                                        reimbursement_request_id=str(request.id),
                                        error_message=str(e),
                                        traceback=traceback.format_exc(),
                                    )

                            log.info(
                                "Updating a Reimbursement Request from Alegeus.",
                                reimbursement_request_id=str(request.id),
                                old_request_category=old_request_category,
                                new_request_category=request.category,
                                old_request_state=old_request_state,
                                new_request_state=request.state,
                                old_request_amount=old_request_amount,
                                new_request_amount=request.amount,
                                old_request_expense_type=old_request_expense_type,
                                new_request_expense_type=request.expense_type,
                                old_request_expense_subtype=old_request_expense_subtype,
                                new_request_expense_subtype=request.wallet_expense_subtype,
                                old_request_service_start_date=old_request_service_start_date,
                                new_request_service_start_date=request.service_start_date,
                            )
                            log.info(
                                "Updating a Reimbursement Claim from Alegeus.",
                                reimbursement_claim_id=str(claim.id),
                                old_claim_status=old_claim_status,
                                new_claim_status=claim.status,
                                old_claim_amount=old_claim_amount,
                                new_claim_amount=claim.amount,
                                old_claim_key=old_claim_key,
                                new_claim_key=claim.alegeus_claim_key,
                            )

                            if old_request_category != request.category:
                                increment_reimbursement_request_field_update(
                                    field="category", source="alegeus"
                                )
                            if old_request_expense_type != request.expense_type:
                                increment_reimbursement_request_field_update(
                                    field="expense_type",
                                    source="alegeus",
                                    old_value=old_request_expense_type.value  # type: ignore[attr-defined] # "str" has no attribute "value"
                                    if old_request_expense_type
                                    else None,
                                    new_value=request.expense_type.value  # type: ignore[attr-defined] # "str" has no attribute "value"
                                    if request.expense_type
                                    else None,
                                )
                            if (
                                old_request_expense_subtype
                                != request.wallet_expense_subtype
                            ):
                                increment_reimbursement_request_field_update(
                                    field="wallet_expense_subtype",
                                    source="alegeus",
                                    old_value=old_request_expense_subtype.code
                                    if old_request_expense_subtype
                                    else None,
                                    new_value=request.wallet_expense_subtype.code
                                    if request.wallet_expense_subtype
                                    else None,
                                )

                            db.session.add(request)
                            db.session.add(claim)
                        db.session.commit()
                        tag_successful(
                            successful=True,
                            reimbursement_claim_status=claim.status,  # type: ignore[arg-type] # Argument "reimbursement_claim_status" to "tag_successful" has incompatible type "Optional[str]"; expected "str"
                            reimbursement_request_state=request.state,  # type: ignore[arg-type] # Argument "reimbursement_request_state" to "tag_successful" has incompatible type "str"; expected "Optional[ReimbursementRequestState]"
                        )
                    except exc.SQLAlchemyError as sqlalchemy_error:
                        log.exception(
                            "SQLAlchemy error: Unable to delete a claim and update a reimbursement request for the given wallet. Rolling back.",
                            wallet_id=str(wallet.id),
                            error=sqlalchemy_error.__class__.__name__,
                            exception=sqlalchemy_error,
                        )
                        tag_successful(
                            successful=False, error_cause="sql_alchemy_error"
                        )
                        db.session.rollback()
                    except Exception as e:
                        log.exception(
                            "Unable to delete a claim and update a reimbursement request for the given wallet. Rolling back.",
                            wallet_id=str(wallet.id),
                            error=e,
                        )
                        tag_successful(successful=False, error_cause="unexpected_error")
                        db.session.rollback()
            else:
                log.error(
                    "Unable to sync claims for the given wallet, Alegeus request failed.",
                    wallet_id=str(wallet.id),
                )
                tag_successful(successful=False, error_cause="alegeus_request_failed")

        except Exception as e:
            log.exception(f"Unable to sync claims for wallet_id: {wallet.id}", error=e)
            tag_successful(successful=False, error_cause="unexpected_error")

    # Send events. Do this after the above loop to ensure that we don't send an event
    # if an error prevents the state change from committing.
    for reimbursement_request in reimbursement_requests_to_event:
        send_reimbursement_request_state_event(reimbursement_request)


def _sync_claim_and_request(
    request: ReimbursementRequest,
    claim: ReimbursementClaim,
    alegeus_claim: AlegeusClaim,
) -> None:
    alegeus_claim_status = alegeus_claim.status
    claim_status = claim.status and claim.status.upper()

    new_request_state = _map_reimbursement_request_state_from_claim(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "ReimbursementRequestState", variable has type "str")
        alegeus_claim, request.state  # type: ignore[arg-type] # Argument 2 to "_map_reimbursement_request_state_from_claim" has incompatible type "str"; expected "ReimbursementRequestState"
    )
    if alegeus_claim_status in [e.value for e in AlegeusClaimStatus] and (
        claim_status != alegeus_claim_status
        or claim.amount != alegeus_claim.amount
        or claim.alegeus_claim_key != alegeus_claim.claim_key
        or request.state != new_request_state
        or (
            alegeus_claim.service_start_date
            and request.service_start_date != alegeus_claim.service_start_date
        )
    ):
        claim.status = alegeus_claim.status
        request.state = new_request_state

        # Update service date if provided by Alegeus
        if alegeus_claim.service_start_date:
            request.service_start_date = alegeus_claim.service_start_date

        if alegeus_claim.amount:
            claim.amount = alegeus_claim.amount  # type: ignore[assignment] # Incompatible types in assignment (expression has type "float", variable has type "Optional[Decimal]")
            currency_service = CurrencyService()
            adjusted_usd_amount: int = convert_dollars_to_cents(claim.amount)
            currency_service.process_reimbursement_request_adjustment(
                request=request, adjusted_usd_amount=adjusted_usd_amount
            )

        if alegeus_claim.claim_key:
            claim.alegeus_claim_key = alegeus_claim.claim_key

        ### Start Updates to Category, Expense Type (ET), and/or Expense Subtype (EST) (aka SCC)

        # Alegeus only sends the SCC code back after adjudication, even if submitted. Only consider updated if not null.
        updated_scc_returned = alegeus_claim.service_category_code and (
            not request.wallet_expense_subtype
            or alegeus_claim.service_category_code
            != request.wallet_expense_subtype.code
        )
        is_dtr = alegeus_claim.account_type_code == AlegeusAccountType.DTR.value

        # Initialize this from the current category. Update as needed and use for subsequent logic.
        # Don't update the RR until the end to avoid changing values in alerting cases.
        ending_request_category = request.category

        ## Category Updates ##
        # Key should be integer from Alegeus, but stored as string in DB, so force to string for comparisons.
        # Flex Account Key will be 0 until after adjudication, -1 for some rejections.
        # DTR accounts don't link to a category.
        if (
            alegeus_claim.flex_account_key
            and str(alegeus_claim.flex_account_key) != "0"
            and str(alegeus_claim.flex_account_key) != "-1"
            and not is_dtr
        ):
            # Need to query for existing account before we can compare
            try:
                existing_account = ReimbursementAccount.query.filter_by(
                    wallet=request.wallet,
                    plan=request.category.reimbursement_plan,
                ).one()
            except (MultipleResultsFound, NoResultFound, AttributeError) as e:
                log.exception(
                    "Failed to load existing ReimbursementAccount for Reimbursement Request",
                    wallet_id=str(request.wallet.id),
                    category_id=str(request.category.id),
                    reimbursement_plan_id=str(request.category.reimbursement_plan.id)
                    if request.category.reimbursement_plan
                    else None,
                    reimbursement_request_id=str(request.id),
                    error=e,
                )
                notify_payment_ops_of_account_scc_sync_issue(
                    reason="Could not load existing Reimbursement Account to compare with account key returned from Alegeus",
                    reimbursement_request=request,
                    reimbursement_claim=claim,
                )
                return

            # Claim adjudicated into account for a different category?
            if str(alegeus_claim.flex_account_key) != str(
                existing_account.alegeus_flex_account_key
            ):
                try:
                    new_category = (
                        db.session.query(ReimbursementRequestCategory)
                        .join(
                            ReimbursementPlan,
                            ReimbursementRequestCategory.reimbursement_plan_id
                            == ReimbursementPlan.id,
                        )
                        .join(
                            ReimbursementAccount,
                            ReimbursementAccount.reimbursement_plan_id
                            == ReimbursementPlan.id,
                        )
                        .filter(
                            ReimbursementAccount.reimbursement_wallet_id
                            == request.wallet.id,
                            ReimbursementAccount.alegeus_flex_account_key
                            == alegeus_claim.flex_account_key,
                        )
                        .one()
                    )
                except (MultipleResultsFound, NoResultFound) as e:
                    log.exception(
                        "Failed to load updated Category by Account Key",
                        wallet_id=str(request.wallet.id),
                        alegeus_flex_account_key=alegeus_claim.flex_account_key,
                        error=e,
                    )
                    notify_payment_ops_of_account_scc_sync_issue(
                        reason="Could not find Reimbursement Account+Plan+Category with account key returned from Alegeus",
                        reimbursement_request=request,
                        reimbursement_claim=claim,
                        data={
                            "Alegeus Account Key": alegeus_claim.flex_account_key,
                        },
                    )
                    return

                if new_category not in [
                    ac.reimbursement_request_category
                    for ac in request.wallet.get_wallet_allowed_categories
                ]:
                    log.warning(
                        "Updated Category not allowed on Wallet",
                        wallet_id=str(request.wallet.id),
                        reimbursement_request_id=str(request.id),
                        existing_account_id=str(existing_account.id),
                        new_category_id=str(new_category.id),
                        claim_account_key=alegeus_claim.flex_account_key,
                    )
                    notify_payment_ops_of_account_scc_sync_issue(
                        reason="Updated Category not allowed on Wallet",
                        reimbursement_request=request,
                        reimbursement_claim=claim,
                        data={
                            "Alegeus Account Key": alegeus_claim.flex_account_key,
                            "Updated Reimbursement Category ID": str(new_category.id),
                        },
                    )

                    return

                # Category change w/o ET or EST change may cause mismatch
                if not updated_scc_returned and request.expense_type not in [
                    et.expense_type for et in new_category.category_expense_types
                ]:
                    log.warning(
                        "Expense Type not available in Updated Category",
                        wallet_id=str(request.wallet.id),
                        reimbursement_request_id=str(request.id),
                        old_category_id=str(request.category.id),
                        new_category_id=str(new_category.id),
                        claim_account_key=alegeus_claim.flex_account_key,
                        expense_type=request.expense_type.value,
                    )
                    notify_payment_ops_of_account_scc_sync_issue(
                        reason="Unchanged Expense Type not available in Updated Category",
                        reimbursement_request=request,
                        reimbursement_claim=claim,
                        data={
                            "Alegeus Account Key": alegeus_claim.flex_account_key,
                            "Updated Reimbursement Category ID": str(new_category.id),
                            "Expense Type": request.expense_type.value,
                        },
                    )
                    return

                ending_request_category = new_category

        ## Expense Type and Subtype Updates ##
        if updated_scc_returned:
            new_subtype = None
            possible_new_subtypes = (
                db.session.query(WalletExpenseSubtype)
                .join(
                    ReimbursementRequestCategoryExpenseTypes,
                    ReimbursementRequestCategoryExpenseTypes.expense_type
                    == WalletExpenseSubtype.expense_type,
                )
                .filter(
                    WalletExpenseSubtype.code == alegeus_claim.service_category_code,
                    ReimbursementRequestCategoryExpenseTypes.reimbursement_request_category_id
                    == ending_request_category.id,
                )
                .all()
            )

            if len(possible_new_subtypes) == 0:
                log.warning(
                    "Updated Expense Subtype not available in Category",
                    wallet_id=str(request.wallet.id),
                    reimbursement_request_id=str(request.id),
                    category_id=str(ending_request_category.id),
                    scc=alegeus_claim.service_category_code,
                )
                notify_payment_ops_of_account_scc_sync_issue(
                    reason="Updated SCC not available in Category",
                    reimbursement_request=request,
                    reimbursement_claim=claim,
                    data={
                        "Reimbursement Category ID": str(ending_request_category.id),
                        "SCC": alegeus_claim.service_category_code,
                    },
                )
                return
            elif len(possible_new_subtypes) > 1:
                # does one match the type already on the request?
                new_subtype = next(
                    (
                        st
                        for st in possible_new_subtypes
                        if st.expense_type == request.expense_type
                    ),
                    None,
                )
                if not new_subtype:
                    # or one of the prioritized expense types?
                    for pst in PRIORITIZED_EXPENSE_TYPES:
                        new_subtype = next(
                            (
                                st
                                for st in possible_new_subtypes
                                if st.expense_type == pst
                            ),
                            None,
                        )
                        if new_subtype:
                            break
                if not new_subtype:
                    log.warning(
                        "Failed to determine Expense Type & Subtype",
                        wallet_id=str(request.wallet.id),
                        reimbursement_request_id=str(request.id),
                        category_id=str(ending_request_category.id),
                        scc=alegeus_claim.service_category_code,
                    )
                    notify_payment_ops_of_account_scc_sync_issue(
                        reason="Could not determine Expense Type for Duplicate SCC",
                        reimbursement_request=request,
                        reimbursement_claim=claim,
                        data={
                            "Reimbursement Category ID": str(
                                ending_request_category.id
                            ),
                            "SCC": alegeus_claim.service_category_code,
                        },
                    )
                    return
            else:
                new_subtype = possible_new_subtypes[0]

            request.wallet_expense_subtype = new_subtype
            if request.expense_type != new_subtype.expense_type:
                request.expense_type = new_subtype.expense_type

        # finally update the category before the method ends
        request.category = ending_request_category

        ### End Updates to Category, Expense Type (ET), and/or Expense Subtype (EST) (aka SCC)


def _get_alegeus_claim_from_response(alegeus_claims: list, alegeus_claim_id: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    alegeus_claim_id = alegeus_claim_id and alegeus_claim_id.upper()
    alegeus_claim = None
    for ac in alegeus_claims:
        # Parse service date if provided
        service_date = None
        if ac.get("ServiceStartDate"):
            try:
                service_date = format_date_from_string_to_datetime(
                    ac["ServiceStartDate"]
                )
            except (ValueError, AttributeError) as e:
                log.error(
                    "Invalid service date format from Alegeus",
                    service_date=ac["ServiceStartDate"],
                    alegeus_claim_id=alegeus_claim_id,
                    error=str(e),
                )

        # Prepare the amount. Needs to be a decimal to compare with ReimbursementClaim.
        # Drop (don't round) any decimals after 2 places. (Alegeus likes to send six;
        # the extras should all be zero. I mean, are we really reimbursing partial cents?)
        amount = ac.get("AccountsPaidAmount") or ac.get("Amount")
        decimal_amount = (
            Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            if amount
            else Decimal(0)
        )

        candidate_claim = AlegeusClaim(
            tracking_number=ac.get("TrackingNumber", "").upper(),
            status=ac.get("Status", "").upper(),
            claim_key=ac.get("ClaimKey"),
            amount=decimal_amount,
            account_type_code=get_account_type_code(ac),
            flex_account_key=ac.get("FlexAcctKey"),
            service_category_code=ac.get(
                "ServiceCategoryCode"
            ),  # null until approved, even if one was submitted
            service_start_date=service_date,
        )

        if candidate_claim.tracking_number == alegeus_claim_id:
            alegeus_claim = candidate_claim

            status = candidate_claim.status

            # Alegeus can potentially return multiple Claims with the same ID but one is
            #   DENIED and the other is APPROVED. We should just return the non Denied claim if this situation occurs.
            # Additionally, Alegeus can return multiple Claims with the same ID but one is applied towards a DTR / HDHP
            #   For this scenario we should sync with the non DTR Claim
            if (
                status in [e.value for e in AlegeusClaimStatus]
                and status != AlegeusClaimStatus.DENIED.value
                and alegeus_claim.account_type_code != AlegeusAccountType.DTR.value
            ):
                break

    return alegeus_claim


def _map_reimbursement_request_state_from_claim(
    alegeus_claim: AlegeusClaim, old_state: ReimbursementRequestState
) -> ReimbursementRequestState:
    ret = old_state
    status = alegeus_claim.status
    acc_type_code = alegeus_claim.account_type_code

    if status in [
        AlegeusClaimStatus.NEEDS_RECEIPT.value,
        AlegeusClaimStatus.SUBMITTED_UNDER_REVIEW.value,
    ]:
        ret = ReimbursementRequestState.PENDING

    elif status in [AlegeusClaimStatus.DENIED.value]:
        ret = ReimbursementRequestState.DENIED

    elif status in [
        AlegeusClaimStatus.APPROVED.value,
        AlegeusClaimStatus.PARTIALLY_APPROVED.value,
    ]:
        if acc_type_code == AlegeusAccountType.DTR.value:
            ret = ReimbursementRequestState.DENIED
        else:
            ret = ReimbursementRequestState.APPROVED

    elif status in [
        AlegeusClaimStatus.PAID.value,
        AlegeusClaimStatus.CLAIM_ADJUSTED_OVERPAYMENT.value,
        AlegeusClaimStatus.PARTIALLY_PAID.value,
    ]:
        ret = ReimbursementRequestState.REIMBURSED

    return ret


def get_wallet_with_pending_claims(
    wallet: ReimbursementWallet,
) -> Optional[WalletClaims]:
    """
    Returns a WalletClaims consisting of a qualified wallet with a set of ReimbursementClaim IDs (alegeus_claim_id).

    These ReimbursementClaims are directly associated with the requests for reimbursement that have not
    yet been reimbursed.

    This includes ReimbursementRequests with the type which is not DIRECT_BILLING,
    and with 'state' as: PENDING, APPROVED, NEW (if a Claim had already been submitted  but was denied)
    """
    if not wallet.reimbursement_requests:
        return None

    claims = []

    for request in wallet.reimbursement_requests:
        if request.claims and _qualified_reimbursement_to_sync(request):
            claims.extend(request.claims)

    return WalletClaims(wallet=wallet, claims=claims) if claims else None


def get_wallets_with_pending_claims(
    wallets: List[ReimbursementWallet],
) -> List[WalletClaims]:
    """
    Returns a list of WalletClaims consisting of qualified Wallets with
    a set of ReimbursementClaim IDs (alegeus_claim_id).

    These ReimbursementClaims are directly associated with the requests for reimbursement that have not
    yet been reimbursed.

    This includes ReimbursementRequests with the type which is not DIRECT_BILLING,
    and with 'state' as: PENDING, APPROVED, NEW (if a Claim had already been submitted  but was denied)
    """
    res = []

    for wallet in wallets:
        wallet_with_claims = get_wallet_with_pending_claims(wallet)

        if wallet_with_claims:
            res.append(wallet_with_claims)

    return res


def _qualified_reimbursement_to_sync(
    reimbursement_request: ReimbursementRequest,
) -> bool:
    return (
        reimbursement_request.state
        in [
            ReimbursementRequestState.NEW,
            ReimbursementRequestState.PENDING,
            ReimbursementRequestState.APPROVED,
        ]
        and reimbursement_request.reimbursement_type
        != ReimbursementRequestType.DIRECT_BILLING
    )


def get_account_type_code(ac: dict) -> str:
    account_type_code = ac.get("AcctTypeCode", "")
    if account_type_code is None:
        return ""
    return account_type_code.upper()


def _should_deduct_credits(
    reimbursement_request: ReimbursementRequest,
) -> bool:
    is_manual = (
        reimbursement_request.reimbursement_type == ReimbursementRequestType.MANUAL
    )
    benefit_type = reimbursement_request.wallet.category_benefit_type(
        request_category_id=reimbursement_request.reimbursement_request_category_id
    )
    is_cycle = benefit_type == BenefitTypes.CYCLE
    has_credit_cost = (
        reimbursement_request.cost_credit is not None
        and reimbursement_request.cost_credit != 0
    )
    is_approved = reimbursement_request.state == ReimbursementRequestState.APPROVED

    result = is_manual and is_cycle and has_credit_cost and is_approved

    log.info(
        "Should deduct credits for request",
        result=result,
        reimburusement_request_id=str(reimbursement_request.id),
    )

    return result


def _add_back_hra_to_alegeus_wallet_balance(
    reimbursement_request: ReimbursementRequest, hra_applied: int
) -> None:
    try:
        hra_refund_request = create_refund_reimbursement_request(
            original_request=reimbursement_request, refund_amount=hra_applied
        )
        db.session.add(hra_refund_request)
        create_direct_payment_claim_in_alegeus(
            wallet=reimbursement_request.wallet,
            reimbursement_request=hra_refund_request,
            claim_type=ClaimType.EMPLOYER,
        )
    except Exception as e:
        # We do not want add back hra to break the alegeus sync.
        log.error(
            "Unable to submit hra refund request to alegeus.",
            reimbursement_request_id=str(reimbursement_request.id),
            error_message=str(e),
            traceback=traceback.format_exc(),
        )


def notify_payment_ops_of_account_scc_sync_issue(
    reason: str,
    reimbursement_request: ReimbursementRequest,
    reimbursement_claim: ReimbursementClaim,
    data: dict | None = None,
) -> None:
    log.info(
        "Notifying Payment Operations",
        reason=reason,
        reimbursement_request_id=str(reimbursement_request.id),
        reimbursement_claim_id=str(reimbursement_claim.id),
    )

    ticket = SyncAccountSccPaymentOpsZendeskTicket(
        user=reimbursement_request.wallet.reimbursement_wallet_users[
            0
        ].member,  # for lack of a RR user, send the first wallet user
        wallet_id=reimbursement_request.wallet.id,
        reimbursement_request_id=reimbursement_request.id,
        reimbursement_claim_id=reimbursement_claim.id,
        reason=reason,
        data=data,
    )
    ticket.update_zendesk()
