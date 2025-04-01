from __future__ import annotations

from typing import Union

import ddtrace.ext
import sqlalchemy.orm

from storage import connection
from storage.connector import RoutingSession
from utils.log import logger
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.models.reimbursement_wallet_credit import ReimbursementCycleCredits
from wallet.models.reimbursement_wallet_credit_transaction import (
    ReimbursementCycleMemberCreditTransaction,
)

log = logger(__name__)
trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)


class CycleCreditsRepository:
    def __init__(
        self,
        session: Union[
            sqlalchemy.orm.scoping.ScopedSession, RoutingSession, None
        ] = None,
    ):
        self.session = session or connection.db.session

    def get_credit_transactions_for_reimbursement(
        self, reimbursement_request_id: int, cycle_credit_id: int | None = None
    ) -> list[ReimbursementCycleMemberCreditTransaction]:
        query = self.session.query(ReimbursementCycleMemberCreditTransaction).filter(
            ReimbursementCycleMemberCreditTransaction.reimbursement_request_id
            == reimbursement_request_id
        )

        if cycle_credit_id is not None:
            query = query.filter(
                ReimbursementCycleMemberCreditTransaction.reimbursement_cycle_credits_id
                == cycle_credit_id
            )

        return query.all()

    def get_cycle_credit(
        self, reimbursement_wallet_id: int, category_association_id: int
    ) -> ReimbursementCycleCredits | None:
        query = self.session.query(ReimbursementCycleCredits).filter(
            ReimbursementCycleCredits.reimbursement_wallet_id
            == reimbursement_wallet_id,
            ReimbursementCycleCredits.reimbursement_organization_settings_allowed_category_id
            == category_association_id,
        )

        return query.one_or_none()

    def get_cycle_credit_by_category(
        self, reimbursement_wallet_id: int, category_id: int
    ) -> ReimbursementCycleCredits | None:
        query = (
            self.session.query(ReimbursementCycleCredits)
            .join(
                ReimbursementOrgSettingCategoryAssociation,
                ReimbursementOrgSettingCategoryAssociation.id
                == ReimbursementCycleCredits.reimbursement_organization_settings_allowed_category_id,
            )
            .filter(
                ReimbursementCycleCredits.reimbursement_wallet_id
                == reimbursement_wallet_id,
                ReimbursementOrgSettingCategoryAssociation.reimbursement_request_category_id
                == category_id,
            )
        )

        return query.one_or_none()
