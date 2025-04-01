from __future__ import annotations

import datetime
import math

from flask import abort, request
from maven.feature_flags import bool_variation

from common.services.api import AuthenticatedResource
from cost_breakdown.models.cost_breakdown import CostBreakdown
from direct_payment.billing import models as billing_models
from direct_payment.payments.constants import CaptionLabels, subtitles
from direct_payment.payments.models import PaginationInfo, PaymentRecord
from direct_payment.payments.payments_helper import PaymentsHelper
from storage.connection import db
from utils.launchdarkly import user_context
from utils.log import logger
from wallet.resources.common import WalletResourceMixin

log = logger(__name__)


class PaymentHistoryResource(AuthenticatedResource, WalletResourceMixin):
    PAGINATION_LIMIT = 30
    PAGINATION_BASE_LINK = "/direct_payment/payments/reimbursement_wallet"
    PAGINATION_PARAM_NAME = "page"

    @staticmethod
    def _deserialize_records(
        records: list[PaymentRecord], use_refunds_refinement: bool = False
    ) -> list[dict]:
        result = []
        for record in records:
            computed_display_date = get_display_date(record)
            response_data = {
                "label": record.label,
                "treatment_procedure_id": str(record.treatment_procedure_id),
                "payment_status": (
                    "PAID"
                    if record.payment_status == "CANCELLED"
                    else record.payment_status
                ),
                "bill_uuid": str(record.bill_uuid) if record.bill_uuid else None,
                "payment_method_type": record.payment_method_type.value,
                "payment_method_display_label": record.payment_method_display_label,
                "member_responsibility": record.member_responsibility,
                "total_cost": record.total_cost,
                "cost_responsibility_type": record.cost_responsibility_type,
                "created_at": record.created_at.isoformat(),
                # due_at will be deprecated in V2+ and replaced by subtitle_label
                "due_at": record.due_at.isoformat() if record.due_at else None,
                # completed_at will be deprecated in V2+ and replaced by subtitle_label
                "completed_at": (
                    record.completed_at.isoformat() if record.completed_at else None
                ),
                # display_date will be deprecated in V2+ and replaced by subtitle_label
                "display_date": record.display_date,
                "subtitle_label": get_subtitle_label(computed_display_date, record),  # type: ignore[arg-type] # Argument 1 to "get_subtitle_label" has incompatible type "Optional[str]"; expected "str"
            }
            if use_refunds_refinement:
                caption_label = get_caption_label(
                    record.payment_status, record.cost_responsibility_type
                )
                response_data["caption_label"] = caption_label
            result.append(response_data)
        return result

    def _deserialize(
        self,
        upcoming: list[PaymentRecord],
        history: list[PaymentRecord],
        pagination_data: PaginationInfo,
        use_refunds_refinement: bool = False,
    ) -> dict:
        return {
            "upcoming": self._deserialize_records(upcoming, use_refunds_refinement),
            "history": {
                "links": {
                    "next": pagination_data.next_link,
                    "prev": pagination_data.prev_link,
                },
                "count": pagination_data.count,
                "num_pages": pagination_data.num_pages,
                "results": self._deserialize_records(history, use_refunds_refinement),
            },
        }

    def get(self, wallet_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        wallet = self._wallet_or_404(self.user, wallet_id)
        payments_helper = PaymentsHelper(db.session)
        use_refunds_refinement = bool_variation(
            "refund-refinement-phase-2",
            user_context(self.user),
            default=False,
        )

        # PART 0: Pagination calculations
        pagination_count = (
            payments_helper.billing_service.get_count_bills_by_payor_with_historic(
                payor_type=billing_models.PayorType.MEMBER,
                payor_id=wallet.id,
            )
        )
        page_number = int(request.args.get(self.PAGINATION_PARAM_NAME, 1))
        pagination_data = self._pagination_handler(
            page_number=page_number,
            pagination_count=pagination_count,
            wallet_id=wallet.id,
        )

        # PART 1: Get all data
        bills = payments_helper.billing_service.get_bills_by_payor_with_historic(
            payor_type=billing_models.PayorType.MEMBER,
            payor_id=wallet.id,
            historic_limit=pagination_data.limit,
            historic_offset=pagination_data.offset,
        )
        bill_procedure_ids = {
            b.procedure_id for b in bills
        }  # using a set to dedupe ids
        procedures = payments_helper.treatment_procedure_repo.get_wallet_payment_history_procedures(
            wallet_id=wallet.id, ids=list(bill_procedure_ids)
        )
        # Using a direct query since there doesn't seem to be a repository
        cost_breakdowns = CostBreakdown.query.filter(
            CostBreakdown.id.in_({bill.cost_breakdown_id for bill in bills})
        ).all()

        # PART 2: use the data
        # Build the mappings from all queried data.
        procedure_map = {procedure.id: procedure for procedure in procedures}
        cost_breakdown_map = {
            cost_breakdown.id: cost_breakdown for cost_breakdown in cost_breakdowns
        }

        all_upcoming_records = payments_helper.return_upcoming_records(
            bills=bills,
            bill_procedure_ids=bill_procedure_ids,
            procedure_map=procedure_map,
            cost_breakdown_map=cost_breakdown_map,
            allow_voided_payment_status=payments_helper.show_payment_status_voided(
                request_headers=request.headers,  # type: ignore[arg-type] # Argument "request_header" to "show_payment_status_voided" of "PaymentsHelper" has incompatible type "EnvironHeaders"; expected "dict[Any, Any]"
                use_refunds_refinement=use_refunds_refinement,
            ),
        )
        historic_records = payments_helper.return_historic_records(
            bills=bills,
            procedure_map=procedure_map,
            cost_breakdown_map=cost_breakdown_map,
            allow_voided_payment_status=payments_helper.show_payment_status_voided(
                request_headers=request.headers,  # type: ignore[arg-type] # Argument "request_header" to "show_payment_status_voided" of "PaymentsHelper" has incompatible type "EnvironHeaders"; expected "dict[Any, Any]"
                use_refunds_refinement=use_refunds_refinement,
            ),
        )

        log.info(
            "PH: returning payments upcoming and history:",
            input_wallet_id=str(wallet_id),
            input_page_number=page_number,
            bill_uuids_upcoming=[str(u.bill_uuid) for u in all_upcoming_records],
            bill_uuids_historic=[str(h.bill_uuid) for h in historic_records],
            page_number=page_number,
            pagination_next=pagination_data.next_link,
            pagination_prev=pagination_data.prev_link,
            pagination_count=pagination_data.count,
            pagination_num_pages=pagination_data.num_pages,
            pagination_limit=pagination_data.limit,
            pagination_offset=pagination_data.offset,
        )

        return self._deserialize(
            upcoming=all_upcoming_records,
            history=historic_records,
            pagination_data=pagination_data,
            use_refunds_refinement=use_refunds_refinement,
        )

    def _pagination_handler(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, page_number: int, pagination_count: int, wallet_id: int
    ):
        if page_number < 1:
            abort(422, "Invalid pagination request.")

        # offset
        offset = self.PAGINATION_LIMIT * (page_number - 1)

        # page count
        num_pages = math.floor(pagination_count / self.PAGINATION_LIMIT)
        if pagination_count % self.PAGINATION_LIMIT > 0:
            num_pages += 1

        # page links
        next_link = None
        prev_link = None
        if num_pages > page_number:
            next_link = f"{self.PAGINATION_BASE_LINK}/{wallet_id}?{self.PAGINATION_PARAM_NAME}={page_number+1}"
        if page_number > 1:
            prev_link = f"{self.PAGINATION_BASE_LINK}/{wallet_id}?{self.PAGINATION_PARAM_NAME}={page_number-1}"

        return PaginationInfo(
            next_link=next_link,
            prev_link=prev_link,
            num_pages=num_pages,
            count=pagination_count,
            limit=self.PAGINATION_LIMIT,
            offset=offset,
        )


def get_display_date(record: PaymentRecord) -> str | None:
    if record.display_date == "created_at":
        return get_date_str(record.created_at)
    if record.display_date == "due_at":
        return get_date_str(record.due_at) if record.due_at else None
    if record.display_date == "completed_at":
        return get_date_str(record.completed_at) if record.completed_at else None
    log.warn(
        "Bad record display date",
        treatment_procedure_id=str(record.treatment_procedure_id),
        bill_uuid=str(record.bill_uuid),
    )
    return ""


def get_date_str(datetime_obj: datetime.datetime) -> str:
    month = datetime_obj.strftime("%b")
    return f"{month} {datetime_obj.day}, {datetime_obj.year}"


def get_subtitle_label(computed_display_date: str, record: PaymentRecord) -> str:
    if record.payment_status == "PAID":
        if record.cost_responsibility_type in ("shared", "member_only"):
            subtitle = subtitles.get(record.payment_status)
        else:
            subtitle = subtitles.get("PAID_NO_MEMBER_COST")
    else:
        subtitle = subtitles.get(record.payment_status)
    if not subtitle:
        log.warn(
            "Bad record payment status",
            treatment_procedure_id=str(record.treatment_procedure_id),
            bill_uuid=str(record.bill_uuid),
        )
        return ""
    return subtitle.format(
        computed_display_date=computed_display_date,
        payment_method_display_label=record.payment_method_display_label,
    )


def get_caption_label(payment_status: str, cost_responsibility_type: str) -> str | None:
    """
    Returns the caption label for the payment record.
    This is shown below the subtitle if it is a string.
    It is not shown if it is null.
    """
    if payment_status == "PAID":
        if cost_responsibility_type == "member_only":
            return None
        elif cost_responsibility_type == "no_member":
            return CaptionLabels.FULL_COST_COVERED.value
        elif cost_responsibility_type == "shared":
            return CaptionLabels.REMAINING_COST_COVERED.value
    return None
