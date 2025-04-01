from __future__ import annotations

import datetime
from typing import Any, List, Optional, Tuple, TypedDict

import pycountry
import sqlalchemy
from flask_babel import gettext

from authn.models.user import User
from cost_breakdown.models.cost_breakdown import CostBreakdown
from storage.connection import db
from utils.braze_events import reimbursement_request_created_new
from utils.log import logger
from wallet.models.constants import (
    BenefitTypes,
    MemberType,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestSourceUploadSource,
    ReimbursementRequestState,
)
from wallet.models.currency import Money
from wallet.models.models import ReimbursementPostRequest
from wallet.models.reimbursement import (
    ReimbursementRequest,
    ReimbursementRequestCategory,
    WalletExpenseSubtype,
)
from wallet.models.reimbursement_request_source import (
    ReimbursementRequestSource,
    ReimbursementRequestSourceRequests,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.repository.currency_fx_rate import CurrencyFxRateRepository
from wallet.repository.reimbursement_request import ReimbursementRequestRepository
from wallet.repository.reimbursement_wallet import ReimbursementWalletRepository
from wallet.services.currency import CurrencyService
from wallet.services.reimbursement_benefits import get_member_type_details_from_wallet
from wallet.services.reimbursement_wallet_messaging import (
    add_reimbursement_request_comment,
)
from wallet.utils.admin_helpers import FlashMessage, FlashMessageCategory

log = logger(__name__)


USD_ONLY_RESPONSE: list[dict] = [{"currency_code": "USD", "minor_unit": 2}]

COMPLETED_REIMBURSEMENT_REQUEST_STATES = {
    ReimbursementRequestState.REIMBURSED,
    ReimbursementRequestState.REFUNDED,
    ReimbursementRequestState.RESOLVED,
}

REJECTED_REIMBURSEMENT_REQUEST_STATES = {
    ReimbursementRequestState.DENIED,
    ReimbursementRequestState.FAILED,
    ReimbursementRequestState.INELIGIBLE_EXPENSE,
}


class ItemDict(TypedDict):
    label: str
    cost: str


class ReimbursementBreakdown(TypedDict):
    title: str
    total_cost: str
    items: List[ItemDict]


class MemberResponsibilityBreakdown(TypedDict):
    title: str
    total_cost: str
    items: List[ItemDict]


class CreditsDetails(TypedDict):
    credits_used_formatted: str
    credits_used: int


class RefundExplanation(TypedDict):
    label: str
    content: List[str]


class CostBreakdownDetails(TypedDict):
    reimbursement_breakdown: Optional[ReimbursementBreakdown]
    member_responsibility_breakdown: Optional[MemberResponsibilityBreakdown]
    credits_details: Optional[CreditsDetails]
    refund_explanation: Optional[RefundExplanation]


class ReimbursementRequestSourceType(TypedDict):
    type: str
    source_id: str
    content_type: str
    source_url: Optional[str]
    inline_url: Optional[str]
    created_at: str
    file_name: str


class ReimbursementRequestWithCostBreakdownDetails(TypedDict):
    id: str
    label: str
    service_provider: str
    amount: int
    cost_breakdown_details: CostBreakdownDetails
    state: str
    state_description: str
    sources: List[ReimbursementRequestSourceType]
    created_at: str
    service_start_date: str
    service_end_date: Optional[str]
    service_start_date_formatted: str
    created_at_date_formatted: str
    original_claim_amount: str


def create_appeal(
    original_reimbursement_request: ReimbursementRequest,
) -> Tuple[List[FlashMessage], bool, Optional[int]]:
    messages = []

    if original_reimbursement_request.state != ReimbursementRequestState.DENIED:
        messages.append(
            FlashMessage(
                message="Cannot appeal a non-denied reimbursement request.",
                category=FlashMessageCategory.ERROR,
            )
        )
        return messages, False, None

    if original_reimbursement_request.appeal_of is not None:
        messages.append(
            FlashMessage(
                message="Cannot appeal a reimbursement request that is an appeal.",
                category=FlashMessageCategory.ERROR,
            )
        )
        return messages, False, None

    if original_reimbursement_request.appeal is not None:
        messages.append(
            FlashMessage(
                message="Cannot re-appeal a reimbursement request.",
                category=FlashMessageCategory.ERROR,
            )
        )
        return messages, False, None

    try:
        # copy all columns except PK
        table = original_reimbursement_request.__table__
        non_pk_columns = [k for k in table.columns.keys() if k not in table.primary_key]
        data = {c: getattr(original_reimbursement_request, c) for c in non_pk_columns}
        appeal_reimbursement_request = ReimbursementRequest(**data)
        # overwrite some columns
        appeal_reimbursement_request.created_at = datetime.datetime.utcnow()
        appeal_reimbursement_request.state = ReimbursementRequestState.NEW
        appeal_reimbursement_request.appeal_of = original_reimbursement_request.id
        # set any previously auto processed back to manual flow
        appeal_reimbursement_request.auto_processed = None
        db.session.add(appeal_reimbursement_request)
        db.session.flush()
    except Exception as e:
        log.exception("create_appeal error duplicating reimbursement request", error=e)
        messages.append(
            FlashMessage(
                message="Unable to create Reimbursement Request record.",
                category=FlashMessageCategory.ERROR,
            )
        )
        db.session.rollback()
        return messages, False, None

    try:
        for source in original_reimbursement_request.sources:
            reimbursement_request_source_request = ReimbursementRequestSourceRequests(
                reimbursement_request_id=appeal_reimbursement_request.id,
                source=source,
            )
            db.session.add(reimbursement_request_source_request)
    except Exception as e:
        log.exception(
            "create_appeal error duplicating reimbursement request sources", error=e
        )
        messages.append(
            FlashMessage(
                message="Unable to assign sources to new Reimbursement Request record.",
                category=FlashMessageCategory.ERROR,
            )
        )
        db.session.rollback()
        return messages, False, None

    db.session.commit()
    messages.append(
        FlashMessage(
            message="Successfully created reimbursement request for appeal.",
            category=FlashMessageCategory.SUCCESS,
        )
    )
    return messages, True, appeal_reimbursement_request.id


class ReimbursementRequestService:
    def __init__(self, session: sqlalchemy.orm.scoping.ScopedSession = None):
        self.reimbursement_wallets: ReimbursementWalletRepository = (
            ReimbursementWalletRepository(session=session or db.session)
        )
        self.reimbursement_requests: ReimbursementRequestRepository = (
            ReimbursementRequestRepository(session=session or db.session)
        )
        self.fx_rate: CurrencyFxRateRepository = CurrencyFxRateRepository(
            session=session or db.session
        )
        self.currency_service = CurrencyService()

    def create_reimbursement_request(
        self,
        data: ReimbursementPostRequest,
        submitter_user: User,
        upload_source: Optional[ReimbursementRequestSourceUploadSource] = None,
    ) -> ReimbursementRequest:
        submitter_user_id = submitter_user.id
        wallet: ReimbursementWallet = self.reimbursement_wallets.get_by_id(
            int(data.wallet_id)
        )

        if not wallet:
            log.error(
                "Wallet could not be found when creating reimbursement request",
                wallet_id=str(data.wallet_id),
            )
            raise Exception(f"Wallet could not be found for {data.wallet_id}")

        # This is extracted so we don't pre-maturely flush the WIP `new_reimbursement_request`
        allowed_category_ids = frozenset(
            c.reimbursement_request_category_id
            for c in wallet.get_or_create_wallet_allowed_categories
        )

        with db.session.no_autoflush:
            new_reimbursement_request = (
                self.get_reimbursement_request_from_post_request(data)
            )

            submitter = self.reimbursement_wallets.get_active_user_in_wallet(
                submitter_user_id, new_reimbursement_request.wallet.id
            )

            # map source objects by provided source ids
            self.__validate_reimbursement_request_sources(
                sources=data.sources,
                wallet_id=new_reimbursement_request.wallet.id,
            )
            new_reimbursement_request.sources = [
                ReimbursementRequestSource(
                    user_asset_id=source["source_id"],
                    reimbursement_wallet_id=new_reimbursement_request.wallet.id,
                    document_mapping_uuid=data.document_mapping_uuid,
                    upload_source=upload_source,
                )
                for source in data.sources
            ]

            # determine user member status
            new_reimbursement_request.person_receiving_service_member_status = (
                self.reimbursement_wallets.get_wallet_user_member_status(
                    new_reimbursement_request.person_receiving_service_id,
                    new_reimbursement_request.wallet.id,
                )
            )

            # Use expense type to set category_id and taxation_status
            new_reimbursement_request.set_expense_type_configuration_attributes(
                allowed_category_ids=allowed_category_ids,
                user_id=submitter_user_id,
                infertility_dx=data.infertility_dx,
            )

            # Add currency specific amount columns to the request
            transaction: Money = self.currency_service.to_money(
                amount=new_reimbursement_request.transaction_amount,
                currency_code=new_reimbursement_request.transaction_currency_code,
            )
            self.currency_service.process_reimbursement_request(
                transaction=transaction, request=new_reimbursement_request
            )

            # validate and create the reimbursement request
            self.__validate_reimbursement_request(new_reimbursement_request, submitter)

            # comment on wallet zendesk ticket with the latest reimbursement request info
            add_reimbursement_request_comment(new_reimbursement_request, submitter)

        # persist the request
        self.reimbursement_requests.create_reimbursement_request(
            new_reimbursement_request
        )

        log.info(
            "Created new reimbursement",
            id=str(new_reimbursement_request.id),
            submitter_user_id=str(submitter_user_id),
            label=new_reimbursement_request.label,
            description=new_reimbursement_request.description,
            organization_id=str(
                new_reimbursement_request.wallet.reimbursement_organization_settings.organization_id
            ),
            benefit_amount=new_reimbursement_request.amount,
            benefit_currency_code=str(new_reimbursement_request.benefit_currency_code),
            transaction_amount=new_reimbursement_request.transaction_amount,
            transaction_currency_code=str(
                new_reimbursement_request.transaction_currency_code
            ),
            wallet_id=str(new_reimbursement_request.reimbursement_wallet_id),
        )

        if self.is_cost_share_breakdown_applicable(wallet):
            try:
                reimbursement_request_created_new(
                    wallet=wallet, member_type=MemberType.MAVEN_GOLD
                )
            except Exception as e:
                log.exception(
                    "Failed to send braze event for new reimbursement request",
                    error=e,
                    reimbursement_request_id=new_reimbursement_request.id,
                    submitter_user_id=submitter_user_id,
                )

        return new_reimbursement_request

    def __validate_reimbursement_request_sources(
        self, sources: List[dict], wallet_id: int
    ) -> None:
        asset_ids = {source["source_id"] for source in sources}
        duplicate_asset_id_count = (
            db.session.query(ReimbursementRequestSource.user_asset_id)
            .filter(
                ReimbursementRequestSource.user_asset_id.in_(asset_ids),
                ReimbursementRequestSource.reimbursement_wallet_id == wallet_id,
            )
            .count()
        )
        if duplicate_asset_id_count > 0:
            raise ValueError(
                f"{duplicate_asset_id_count} of these documents are already uploaded to this account"
            )

    def __validate_reimbursement_request(
        self,
        reimbursement_request: ReimbursementRequest,
        submitter: ReimbursementWalletUsers,
    ) -> None:
        # person receiving service should be part of the wallet
        if not reimbursement_request.person_receiving_service_member_status:
            log.info(
                "Reimbursement Request Validation: Invalid Person Receiving Service",
                reimbursement_wallet_id=reimbursement_request.wallet.id,
                person_receiving_service_id=reimbursement_request.person_receiving_service_id,
                person_receiving_service_member_status=reimbursement_request.person_receiving_service_member_status,
            )
            raise ValueError(
                f"User [{reimbursement_request.person_receiving_service}] is not associated with the wallet"
            )

        # amount must be greater than $ and less than $100K in USD
        if (
            reimbursement_request.usd_amount <= 0
            or reimbursement_request.usd_amount > 10000000
        ):
            log.info(
                "Reimbursement Request Validation: Invalid Amount",
                reimbursement_wallet_id=reimbursement_request.wallet.id,
                usd_amount=reimbursement_request.usd_amount,
            )
            raise ValueError("Amount must be between $0 and $100,000 in USD")

        # number of sources/attachments must be between 1 and 20
        if (
            len(reimbursement_request.sources) < 1
            or len(reimbursement_request.sources) > 20
        ):
            log.info(
                "Reimbursement Request Validation: Invalid Sources count",
                reimbursement_wallet_id=reimbursement_request.wallet.id,
                sources_count=len(reimbursement_request.sources),
            )
            raise ValueError("Attachment size must be between 1 and 20")

        # service date cannot be in the future
        if reimbursement_request.service_start_date > datetime.datetime.today().date():
            log.info(
                "Reimbursement Request Validation: Future date",
                reimbursement_wallet_id=reimbursement_request.wallet.id,
                service_start_date=reimbursement_request.service_start_date,
            )
            raise ValueError("Service date is in the future")

        # submitter must be part of the reimbursement wallet
        if not submitter:
            log.info(
                "Reimbursement Request Validation: Submitter not active",
                reimbursement_wallet_id=reimbursement_request.wallet.id,
            )
            raise ValueError("Submitter is not an active user on the wallet")

        if reimbursement_request.expense_type:
            try:
                ReimbursementRequestExpenseTypes(
                    _parse_expense_type(reimbursement_request.expense_type)
                )
            except ValueError:
                log.info(
                    "Reimbursement Request Validation: Invalid Expense Type",
                    reimbursement_wallet_id=reimbursement_request.wallet.id,
                    expense_type=reimbursement_request.expense_type,
                )
                raise ValueError("Valid Expense Type must be provided")

        if (
            not reimbursement_request.expense_type
            and not reimbursement_request.category
        ):
            log.info(
                "Reimbursement Request Validation: Missing Expense Type and Category",
                reimbursement_wallet_id=reimbursement_request.wallet.id,
            )
            raise ValueError("Missing Expense type and category ID")

        if (
            not reimbursement_request.expense_type
            and reimbursement_request.wallet_expense_subtype
        ):
            log.info(
                "Reimbursement Request Validation: Expense Subtype requires Expense Type",
                reimbursement_wallet_id=reimbursement_request.wallet.id,
                wallet_expense_subtype_id=reimbursement_request.wallet_expense_subtype.id,
            )
            raise ValueError("Expense Subtype requires a valid Expense Type")

        if (
            reimbursement_request.wallet_expense_subtype
            and reimbursement_request.expense_type
            != reimbursement_request.wallet_expense_subtype.expense_type.value  # type: ignore[attr-defined] # "str" has no attribute "value"
        ):
            log.info(
                "Reimbursement Request Validation: Expense Subtype not valid for Expense Type",
                reimbursement_wallet_id=reimbursement_request.wallet.id,
                expense_type=reimbursement_request.expense_type,
                wallet_expense_subtype_id=reimbursement_request.wallet_expense_subtype.id,
            )
            raise ValueError("Expense Subtype is not valid for this Expense Type")

    @staticmethod
    def get_reimbursement_request_from_post_request(
        data: ReimbursementPostRequest,
    ) -> ReimbursementRequest:
        category = None
        wallet = None
        expense_subtype = None
        if data.category_id is not None:
            category = db.session.query(ReimbursementRequestCategory).get(
                data.category_id
            )
        if data.wallet_id is not None:
            wallet = db.session.query(ReimbursementWallet).get(data.wallet_id)
        expense_type = _parse_expense_type(data.expense_type)

        # If expense_subtype_id is sent, this is a new client. Don't use the passed description.
        if isinstance(data.expense_subtype_id, str):
            # empty subtype aka "Other"
            if data.expense_subtype_id == "":
                expense_subtype = None
            else:
                expense_subtype = db.session.query(WalletExpenseSubtype).get(
                    data.expense_subtype_id
                )
            label = ReimbursementRequest.AUTO_LABEL_FLAG
            description = ""
        # If expense_subtype_id is not sent, this is an old client. Save the passed description as label & description.
        else:
            label = data.description
            description = data.description

        new_reimbursement_request = ReimbursementRequest(
            label=label,
            description=description,
            service_provider=data.service_provider,
            transaction_amount=data.amount,
            transaction_currency_code=data.currency_code,
            person_receiving_service=data.person_receiving_service_name,
            person_receiving_service_id=data.person_receiving_service_id,
            category=category,
            wallet=wallet,
            service_start_date=datetime.datetime.strptime(
                data.service_start_date, "%Y-%m-%d"
            ).date(),
            expense_type=expense_type,
            original_expense_type=expense_type,
            wallet_expense_subtype=expense_subtype,
            original_wallet_expense_subtype=expense_subtype,
        )

        return new_reimbursement_request

    def get_reimbursement_requests_for_wallet(
        self, wallet: ReimbursementWallet, category: str | None = None
    ) -> List[ReimbursementRequest]:
        reimbursement_requests: List[
            ReimbursementRequest
        ] = self.reimbursement_requests.get_reimbursement_requests_for_wallet(
            wallet_id=wallet.id, category=category
        )

        if self.is_cost_share_breakdown_applicable(wallet=wallet):
            return self.add_cost_share_details(reimbursement_requests)
        else:
            return reimbursement_requests

    def get_available_currencies(self) -> list[dict]:
        currency_and_minor_units: list[
            dict
        ] = self.fx_rate.get_available_currency_and_minor_units()

        for currency in currency_and_minor_units:
            currency_code: str = currency["currency_code"]

            try:
                currency_obj = pycountry.currencies.get(alpha_3=currency_code)
            except Exception as e:
                currency_obj = None
                log.exception(
                    "Error encountered while looking up currency with pycountry", exc=e
                )

            if currency_obj and currency_obj.name:
                currency["display_name"] = currency_obj.name
            else:
                log.warning(
                    "Currency not found, defaulting to currency code",
                    currency_code=currency_code,
                )
                currency["display_name"] = currency_code

        # Sort by display_name in alphabetical order
        currency_and_minor_units.sort(key=lambda c: c["display_name"])

        return currency_and_minor_units

    def get_reimbursement_requests_for_wallet_rr_block(
        self, wallet_id: int, category_labels: List[str]
    ) -> List[ReimbursementRequest]:
        return (
            self.reimbursement_requests.get_reimbursement_requests_for_wallet_rr_block(
                wallet_id=wallet_id, category_labels=category_labels
            )
        )

    def get_reimbursement_request_by_id(
        self, reimbursement_request_id: int
    ) -> ReimbursementRequest | None:
        return self.reimbursement_requests.get_reimbursement_request_by_id(
            reimbursement_request_id=reimbursement_request_id
        )

    def get_latest_cost_breakdowns_by_reimbursement_request(
        self,
        reimbursement_requests: List[ReimbursementRequest],
    ) -> dict[int, CostBreakdown]:
        cost_breakdowns = (
            self.reimbursement_requests.get_cost_breakdowns_for_reimbursement_requests(
                reimbursement_requests=reimbursement_requests
            )
        )
        latest_cost_breakdowns_by_rr = {}
        for cb in cost_breakdowns:
            if cb.reimbursement_request_id not in latest_cost_breakdowns_by_rr:
                latest_cost_breakdowns_by_rr[cb.reimbursement_request_id] = cb
        return latest_cost_breakdowns_by_rr

    def get_latest_cost_breakdowns(
        self,
        reimbursement_requests: List[ReimbursementRequest],
    ) -> List[CostBreakdown]:
        latest_cost_breakdowns_by_rr = (
            self.get_latest_cost_breakdowns_by_reimbursement_request(
                reimbursement_requests=reimbursement_requests
            )
        )
        cost_breakdowns = []
        for rr in reimbursement_requests:
            latest_cost_breakdown = latest_cost_breakdowns_by_rr.get(rr.id)
            if latest_cost_breakdown:
                cost_breakdowns.append(latest_cost_breakdown)
        return cost_breakdowns

    @staticmethod
    def is_cost_share_breakdown_applicable(wallet: ReimbursementWallet) -> bool:
        member_type: MemberType = get_member_type_details_from_wallet(
            wallet
        ).member_type
        return (
            member_type == MemberType.MAVEN_GOLD
            and wallet.reimbursement_organization_settings.deductible_accumulation_enabled
        )

    def add_cost_share_details(
        self,
        reimbursement_requests: List[ReimbursementRequest],
    ) -> List[Any]:
        cost_breakdowns = self.get_latest_cost_breakdowns_by_reimbursement_request(
            reimbursement_requests
        )

        for rr in reimbursement_requests:
            rr.cost_share_details = {
                "original_claim_amount": None,
                "reimbursement_amount": None,
                "reimbursement_expected_message": None,
            }
            latest_cb = cost_breakdowns.get(rr.id)

            # The reimbursement request will have a cost breakdown in the future
            if not latest_cb and rr.state in [
                ReimbursementRequestState.NEW,
                ReimbursementRequestState.PENDING,
                ReimbursementRequestState.APPROVED,
                ReimbursementRequestState.NEEDS_RECEIPT,
                ReimbursementRequestState.RECEIPT_SUBMITTED,
                ReimbursementRequestState.INSUFFICIENT_RECEIPT,
                ReimbursementRequestState.PENDING_MEMBER_INPUT,
            ]:
                formatted_original_claim_amount_obj = (
                    self.currency_service.format_amount_obj(rr.amount)
                )
                rr.cost_share_details[
                    "original_claim_amount"
                ] = formatted_original_claim_amount_obj.get("formatted_amount")
                rr.cost_share_details["reimbursement_expected_message"] = gettext(
                    "reimbursement_request_cost_share_details_reimbursement_expected_message"
                )
            elif latest_cb:
                total_responsibility = sum(
                    (
                        latest_cb.total_employer_responsibility,
                        latest_cb.total_member_responsibility,
                    )
                )
                formatted_original_claim_amount_obj = (
                    self.currency_service.format_amount_obj(total_responsibility)
                )

                # reimbursement amount should be 0 if the request is rejected
                formatted_expected_reimbursement_amount_obj = (
                    self.currency_service.format_amount_obj(
                        latest_cb.total_employer_responsibility
                        if rr.state not in REJECTED_REIMBURSEMENT_REQUEST_STATES
                        else 0
                    )
                )
                rr.cost_share_details[
                    "original_claim_amount"
                ] = formatted_original_claim_amount_obj.get("formatted_amount")
                rr.cost_share_details[
                    "reimbursement_amount"
                ] = formatted_expected_reimbursement_amount_obj.get("formatted_amount")

            if all(value is None for value in rr.cost_share_details.values()):
                rr.cost_share_details = None

        return reimbursement_requests

    def get_reimbursement_request_with_cost_breakdown_details(
        self, reimbursement_request: ReimbursementRequest
    ) -> ReimbursementRequestWithCostBreakdownDetails:
        cb_list = self.get_latest_cost_breakdowns(
            reimbursement_requests=[reimbursement_request]
        )

        #  There should be exactly one cost breakdown in the list.
        cost_breakdown = cb_list[0] if cb_list else None

        original_rr_amount = (
            sum(
                [
                    cost_breakdown.total_member_responsibility,
                    cost_breakdown.total_employer_responsibility,
                ]
            )
            if cost_breakdown
            else reimbursement_request.amount
        )

        reimbursement_breakdown_obj = self._create_reimbursement_breakdown_obj(
            reimbursement_request, cost_breakdown
        )

        member_responsibility_breakdown_obj = (
            self._create_member_responsibility_breakdown_obj(cost_breakdown)
        )

        benefit_type = reimbursement_request.wallet.category_benefit_type(
            request_category_id=reimbursement_request.reimbursement_request_category_id
        )
        is_cycle_based_wallet = benefit_type == BenefitTypes.CYCLE

        credits_details_obj = self._create_credits_details_obj(
            bool(cost_breakdown), is_cycle_based_wallet, reimbursement_request
        )

        refund_explanation_obj = self._create_refund_explanation_obj(
            cost_breakdown, original_rr_amount
        )

        cost_breakdown_details_obj = CostBreakdownDetails(
            reimbursement_breakdown=reimbursement_breakdown_obj,
            member_responsibility_breakdown=member_responsibility_breakdown_obj,
            credits_details=credits_details_obj,
            refund_explanation=refund_explanation_obj,
        )

        state: ReimbursementRequestState = reimbursement_request.state

        reimbursement_request_with_details = ReimbursementRequestWithCostBreakdownDetails(
            id=str(reimbursement_request.id),
            label=reimbursement_request.formatted_label,
            service_provider=reimbursement_request.service_provider,
            amount=reimbursement_request.amount,
            cost_breakdown_details=cost_breakdown_details_obj,
            state=state.value,
            state_description=reimbursement_request.state_description,
            sources=[
                {
                    "type": source.type,
                    "source_id": str(source.source_id),
                    "content_type": source.user_asset.content_type,
                    "source_url": self._get_source_url(source),
                    "inline_url": self._get_inline_url(source),
                    "created_at": source.created_at.isoformat(),
                    "file_name": source.user_asset.file_name,
                }
                for source in (reimbursement_request.sources or [])
            ],
            created_at=reimbursement_request.created_at.isoformat(),
            service_start_date=reimbursement_request.service_start_date.isoformat(),
            service_end_date=reimbursement_request.service_end_date.isoformat()
            if reimbursement_request.service_end_date
            else None,
            service_start_date_formatted=reimbursement_request.service_start_date.strftime(
                "%B %d, %Y"
            ),
            created_at_date_formatted=reimbursement_request.created_at.strftime(
                "%B %d, %Y"
            ),
            original_claim_amount=self._get_formatted_amount(original_rr_amount),
        )

        return reimbursement_request_with_details

    def _create_reimbursement_breakdown_obj(
        self,
        reimbursement_request: ReimbursementRequest,
        cost_breakdown: Optional[CostBreakdown],
    ) -> Optional[ReimbursementBreakdown]:
        is_reimbursement_completed = (
            reimbursement_request.state in COMPLETED_REIMBURSEMENT_REQUEST_STATES
        )
        is_reimbursement_rejected = (
            reimbursement_request.state in REJECTED_REIMBURSEMENT_REQUEST_STATES
        )

        reimbursement_text = gettext(
            "reimbursement_request_details_reimbursement_breakdown_reimbursement"
        )
        reimbursement_expected_text = gettext(
            "reimbursement_request_details_reimbursement_breakdown_reimbursement_expected"
        )
        maven_benefit_text = gettext(
            "reimbursement_request_details_reimbursement_breakdown_maven_benefit"
        )

        reimbursement_amount = (
            self._get_formatted_amount(cost_breakdown.total_employer_responsibility)
            if cost_breakdown
            else self._get_formatted_amount(reimbursement_request.amount)
        )

        reimbursement_breakdown_obj = None
        if is_reimbursement_rejected:
            zero_amount_formatted = self._get_formatted_amount(0)
            reimbursement_breakdown_obj = ReimbursementBreakdown(
                title=reimbursement_text,
                total_cost=zero_amount_formatted,
                items=[
                    {
                        "label": maven_benefit_text,
                        "cost": zero_amount_formatted,
                    }
                ],
            )
        elif is_reimbursement_completed or cost_breakdown:
            title = (
                reimbursement_text
                if is_reimbursement_completed
                else reimbursement_expected_text
            )
            items = [
                {
                    "label": maven_benefit_text,
                    "cost": reimbursement_amount,
                }
            ]
            if (
                cost_breakdown is not None
                and cost_breakdown.hra_applied is not None
                and cost_breakdown.hra_applied > 0
            ):
                items.append(
                    {
                        "label": gettext(
                            "reimbursement_request_details_reimbursement_breakdown_hra_credit"
                        ),
                        "cost": self._get_formatted_amount(cost_breakdown.hra_applied),
                    }
                )
            reimbursement_breakdown_obj = ReimbursementBreakdown(
                title=title,
                total_cost=reimbursement_amount,
                items=items,  # type: ignore[typeddict-item] #  Incompatible types (expression has type "list[dict[str, Any]]", TypedDict item "items" has type "list[ItemDict]")
            )

        return reimbursement_breakdown_obj

    def _create_member_responsibility_breakdown_obj(
        self, cost_breakdown: Optional[CostBreakdown]
    ) -> Optional[MemberResponsibilityBreakdown]:
        member_responsibility_breakdown_obj = None
        if cost_breakdown:
            items = [
                {
                    "label": gettext(
                        "reimbursement_request_details_member_responsibility_breakdown_deductible"
                    ),
                    "cost": self._get_formatted_amount(cost_breakdown.deductible),
                },
                {
                    "label": gettext(
                        "reimbursement_request_details_member_responsibility_breakdown_coinsurance"
                    ),
                    "cost": self._get_formatted_amount(cost_breakdown.coinsurance),
                },
                {
                    "label": gettext(
                        "reimbursement_request_details_member_responsibility_breakdown_copay"
                    ),
                    "cost": self._get_formatted_amount(cost_breakdown.copay),
                },
                {
                    "label": gettext(
                        "reimbursement_request_details_member_responsibility_breakdown_not_covered"
                    ),
                    "cost": self._get_formatted_amount(cost_breakdown.overage_amount),
                },
            ]
            if (
                cost_breakdown.hra_applied is not None
                and cost_breakdown.hra_applied > 0
            ):
                items.append(
                    {
                        "label": gettext(
                            "reimbursement_request_details_member_responsibility_breakdown_hra_applied"
                        ),
                        "cost": self._get_formatted_amount(-cost_breakdown.hra_applied),
                    }
                )
            member_responsibility_breakdown_obj = MemberResponsibilityBreakdown(
                title=gettext(
                    "reimbursement_request_details_member_responsibility_breakdown_your_responsibility"
                ),
                total_cost=self._get_formatted_amount(
                    cost_breakdown.total_member_responsibility
                ),
                items=items,  # type: ignore[typeddict-item] #  Incompatible types (expression has type "list[dict[str, Any]]", TypedDict item "items" has type "list[ItemDict]")
            )
        return member_responsibility_breakdown_obj

    def _create_credits_details_obj(
        self,
        has_cost_breakdown: bool,
        is_cycle_based_wallet: bool,
        reimbursement_request: ReimbursementRequest,
    ) -> Optional[CreditsDetails]:
        credits_details_obj = None
        if has_cost_breakdown and is_cycle_based_wallet:
            credits = reimbursement_request.cost_credit
            if credits is not None:
                credits_singular_text = gettext(
                    "reimbursement_request_details_credits_details_singular_text"
                )
                credits_plural_text = gettext(
                    "reimbursement_request_details_member_credits_details_plural_text"
                )
                credits_details_obj = CreditsDetails(
                    credits_used_formatted=(
                        f"{credits} {credits_singular_text}"
                        if credits == 1
                        else f"{credits} {credits_plural_text}"
                    ),
                    credits_used=credits,
                )
        return credits_details_obj

    def _create_refund_explanation_obj(
        self,
        cost_breakdown: Optional[CostBreakdown],
        original_rr_amount: int,
    ) -> Optional[RefundExplanation]:
        refund_explanation_obj = None
        if (
            cost_breakdown
            and cost_breakdown.total_employer_responsibility < original_rr_amount
        ):
            refund_explanation_obj = RefundExplanation(
                label=gettext("reimbursement_request_details_refund_explanation_label"),
                content=[
                    gettext(
                        "reimbursement_request_details_refund_explanation_content_0"
                    ),
                    gettext(
                        "reimbursement_request_details_refund_explanation_content_1"
                    ),
                ],
            )
        return refund_explanation_obj

    def _get_formatted_amount(
        self, amount: int, currency_code: Optional[str] = None
    ) -> str:
        formatted_obj = self.currency_service.format_amount_obj(amount, currency_code)
        return formatted_obj.get("formatted_amount", "")

    # Originally from ReimbursementRequestSourceSchema in api/wallet/schemas/reimbursement.py
    def _get_source_url(
        self, reimbursement_request_source: ReimbursementRequestSource | None
    ) -> None | str:
        if reimbursement_request_source is None:
            return None

        try:
            return reimbursement_request_source.user_asset.direct_download_url()
        except Exception as e:
            log.exception(
                "Unexpected error generating reimbursement request asset source url",
                exception=e,
            )
            return None

    # Originally from ReimbursementRequestSourceSchema in api/wallet/schemas/reimbursement.py
    def _get_inline_url(
        self, reimbursement_request_source: ReimbursementRequestSource | None
    ) -> None | str:
        if reimbursement_request_source is None:
            return None

        try:
            return reimbursement_request_source.user_asset.direct_download_url(
                inline=True
            )
        except Exception as e:
            log.exception(
                "Unexpected error generating reimbursement request asset inline url",
                exception=e,
            )
            return None

    def get_expense_subtype(
        self, expense_type: ReimbursementRequestExpenseTypes, code: str
    ) -> WalletExpenseSubtype | None:
        return self.reimbursement_requests.get_expense_subtype(
            expense_type=expense_type, code=code
        )


def _parse_expense_type(expense_type: str | None = None) -> str | None:
    if not expense_type:
        return None

    parsed_expense_type = expense_type.upper().replace(" ", "_")
    return parsed_expense_type
