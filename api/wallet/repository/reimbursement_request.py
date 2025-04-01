from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import List, Union

import ddtrace.ext
import sqlalchemy.orm
from sqlalchemy import and_, desc, or_

from cost_breakdown.constants import ClaimType
from cost_breakdown.models.cost_breakdown import (
    CostBreakdown,
    ReimbursementRequestToCostBreakdown,
)
from storage import connection
from storage.connector import RoutingSession
from utils.log import logger
from wallet.models.constants import (
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
    ReimbursementRequestType,
)
from wallet.models.reimbursement import (
    ReimbursementRequest,
    ReimbursementRequestCategory,
    WalletExpenseSubtype,
)

log = logger(__name__)
trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)


class ReimbursementRequestRepository:
    def __init__(
        self,
        session: Union[
            sqlalchemy.orm.scoping.ScopedSession, RoutingSession, None
        ] = None,
    ):
        self.session = session or connection.db.session

    @trace_wrapper
    def create_reimbursement_request(
        self, new_reimbursement_request: ReimbursementRequest
    ) -> None:
        self.session.add(new_reimbursement_request)
        self.session.commit()
        log.info(
            f"Created new reimbursement request [{new_reimbursement_request.id}]",
            wallet_id=new_reimbursement_request.reimbursement_wallet_id,
        )

    @trace_wrapper
    def get_reimbursement_request_by_id(
        self, reimbursement_request_id: int
    ) -> ReimbursementRequest | None:
        base_query = self.session.query(ReimbursementRequest).filter(
            ReimbursementRequest.id == reimbursement_request_id
        )
        return base_query.one_or_none()

    @trace_wrapper
    def get_all_reimbursement_requests_for_wallet_and_category(
        self, wallet_id: int, category_id: int
    ) -> list[ReimbursementRequest]:
        query = self.session.query(ReimbursementRequest).filter(
            ReimbursementRequest.reimbursement_wallet_id == wallet_id,
            ReimbursementRequest.reimbursement_request_category_id == category_id,
        )

        return query.all()

    @trace_wrapper
    def get_reimbursement_requests_for_wallet(
        self, wallet_id: int, category: str | None = None
    ) -> List[ReimbursementRequest]:
        base_query = (
            self.session.query(ReimbursementRequest)
            .filter(
                ReimbursementRequest.reimbursement_wallet_id == wallet_id,
                ReimbursementRequest.reimbursement_type
                != ReimbursementRequestType.DIRECT_BILLING,
                or_(
                    ReimbursementRequest.state.in_(
                        {
                            ReimbursementRequestState.PENDING,
                            ReimbursementRequestState.APPROVED,
                            ReimbursementRequestState.REIMBURSED,
                            ReimbursementRequestState.DENIED,
                            ReimbursementRequestState.NEEDS_RECEIPT,
                            ReimbursementRequestState.RECEIPT_SUBMITTED,
                            ReimbursementRequestState.INSUFFICIENT_RECEIPT,
                            ReimbursementRequestState.INELIGIBLE_EXPENSE,
                            ReimbursementRequestState.RESOLVED,
                            ReimbursementRequestState.REFUNDED,
                        }
                    ),
                    and_(
                        ReimbursementRequest.state == ReimbursementRequestState.NEW,
                        ReimbursementRequest.created_at
                        >= datetime.now(timezone.utc) - timedelta(days=60),
                    ),
                ),
            )
            .order_by(desc(ReimbursementRequest.created_at))
        )

        if category:
            base_query = base_query.join(
                ReimbursementRequestCategory,
                ReimbursementRequestCategory.id
                == ReimbursementRequest.reimbursement_request_category_id,
            ).filter(ReimbursementRequestCategory.label == category)

        return base_query.all()

    @trace_wrapper
    def wallet_has_unresolved_reimbursements(self, wallet_id: int) -> bool:
        """
        Return a boolean if a wallet has reimbursements in a non-terminal state

        Args:
            wallet_id int: The ReimbursementWallet.id

        Returns: bool
        """
        query = self.session.query(ReimbursementRequest).filter(
            ReimbursementRequest.reimbursement_wallet_id == wallet_id,
            ~ReimbursementRequest.state.in_(
                {
                    ReimbursementRequestState.APPROVED,
                    ReimbursementRequestState.REIMBURSED,
                    ReimbursementRequestState.DENIED,
                    ReimbursementRequestState.FAILED,
                }
            ),
        )

        return query.first() is not None

    @trace_wrapper
    def get_employer_cb_mapping(
        self, reimbursement_request_id: int
    ) -> ReimbursementRequestToCostBreakdown | None:
        """Get the related employer ReimbursementRequestToCostBreakdown if it exists"""
        query = self.session.query(ReimbursementRequestToCostBreakdown).filter(
            ReimbursementRequestToCostBreakdown.reimbursement_request_id
            == reimbursement_request_id,
            ReimbursementRequestToCostBreakdown.claim_type == ClaimType.EMPLOYER,
        )
        return query.one_or_none()

    @trace_wrapper
    def get_num_credits_by_cost_breakdown_id(
        self, cost_breakdown_id: int
    ) -> int | None:
        """Returns the number of credits spent for a given cost_breakdown."""
        return self.session.execute(
            """
            SELECT rcmct.amount
            FROM reimbursement_cycle_member_credit_transactions rcmct
            JOIN reimbursement_request_to_cost_breakdown rrtcb ON rcmct.reimbursement_request_id = rrtcb.reimbursement_request_id
            WHERE rrtcb.cost_breakdown_id = :cost_breakdown_id;
            """,
            {"cost_breakdown_id": cost_breakdown_id},
        ).scalar()

    @trace_wrapper
    def get_reimbursement_requests_for_wallet_rr_block(
        self, wallet_id: int, category_labels: List[str]
    ) -> List[ReimbursementRequest]:
        base_query = (
            self.session.query(ReimbursementRequest)
            .filter(
                ReimbursementRequest.reimbursement_wallet_id == wallet_id,
                ReimbursementRequest.reimbursement_type
                != ReimbursementRequestType.DIRECT_BILLING,
                or_(
                    ReimbursementRequest.state.in_(
                        {
                            ReimbursementRequestState.PENDING,
                            ReimbursementRequestState.APPROVED,
                            ReimbursementRequestState.NEEDS_RECEIPT,
                            ReimbursementRequestState.RECEIPT_SUBMITTED,
                            ReimbursementRequestState.INSUFFICIENT_RECEIPT,
                        }
                    ),
                    and_(
                        ReimbursementRequest.state == ReimbursementRequestState.NEW,
                        ReimbursementRequest.created_at
                        >= datetime.now(timezone.utc) - timedelta(days=60),
                    ),
                ),
            )
            .join(
                ReimbursementRequestCategory,
                ReimbursementRequestCategory.id
                == ReimbursementRequest.reimbursement_request_category_id,
            )
            .filter(ReimbursementRequestCategory.label.in_(category_labels))
        )
        return base_query.all()

    @trace_wrapper
    def get_cost_breakdowns_for_reimbursement_requests(
        self,
        reimbursement_requests: List[ReimbursementRequest],
    ) -> List[CostBreakdown]:
        reimbursement_request_ids = [rr.id for rr in reimbursement_requests]
        base_query = (
            self.session.query(CostBreakdown)
            .filter(
                CostBreakdown.reimbursement_request_id.in_(reimbursement_request_ids)
            )
            .order_by(
                CostBreakdown.reimbursement_request_id, CostBreakdown.created_at.desc()
            )
        )
        return base_query.all()

    @trace_wrapper
    def get_reimbursed_reimbursements(
        self,
        *,
        wallet_id: int,
        category_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[ReimbursementRequest]:
        """
        Get all reimbursed/approved reimbursement requests for wallet/category combo, with optional date range filter
        Args:
            wallet_id: int: Wallet ID
            category_id: int: Category ID
            start_date: Optional[date]: Inclusive, includes records on start_date
            end_date: Optional[date]: Exclusive, excludes records on end_date

        Returns: list[ReimbursementRequest]

        """
        base_query = (
            self.session.query(ReimbursementRequest)
            .filter(
                ReimbursementRequest.reimbursement_wallet_id == wallet_id,
                ReimbursementRequest.reimbursement_request_category_id == category_id,
                ReimbursementRequest.state.in_(
                    {
                        ReimbursementRequestState.REIMBURSED,
                        ReimbursementRequestState.APPROVED,
                    }
                ),
            )
            .order_by(ReimbursementRequest.created_at.asc())
        )

        if start_date is not None:
            base_query = base_query.filter(
                ReimbursementRequest.created_at >= start_date
            )

        if end_date is not None:
            base_query = base_query.filter(ReimbursementRequest.created_at < end_date)

        return base_query.all()

    @trace_wrapper
    def get_pending_reimbursements(
        self, wallet_id: int, category_id: int
    ) -> list[ReimbursementRequest]:
        query = self.session.query(ReimbursementRequest).filter(
            ReimbursementRequest.reimbursement_wallet_id == wallet_id,
            ReimbursementRequest.reimbursement_request_category_id == category_id,
            ReimbursementRequest.state == ReimbursementRequestState.PENDING,
            ReimbursementRequest.reimbursement_type == ReimbursementRequestType.MANUAL,
        )
        return query.all()

    @trace_wrapper
    def get_expense_subtype(
        self, expense_type: ReimbursementRequestExpenseTypes, code: str
    ) -> WalletExpenseSubtype | None:
        return (
            self.session.query(WalletExpenseSubtype)
            .filter(
                WalletExpenseSubtype.expense_type == expense_type,
                WalletExpenseSubtype.code == code,
            )
            .one_or_none()
        )
