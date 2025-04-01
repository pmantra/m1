import datetime
from datetime import date

import factory
from factory.alchemy import SQLAlchemyModelFactory

from conftest import BaseMeta
from cost_breakdown.constants import AmountType, ClaimType
from cost_breakdown.models.cost_breakdown import (
    CostBreakdown,
    CostBreakdownIrsMinimumDeductible,
    ReimbursementRequestToCostBreakdown,
)
from cost_breakdown.models.rte import RTETransaction


class RTETransactionFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = RTETransaction

    member_health_plan_id = factory.Faker("random_int", min=1)
    response_code = 200
    request = {}
    response = {}


class CostBreakdownIrsMinimumDeductibleFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = CostBreakdownIrsMinimumDeductible

    year = date.today().year


class CostBreakdownFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = CostBreakdown

    treatment_procedure_uuid = factory.Faker("uuid4")
    total_member_responsibility = 0
    total_employer_responsibility = 0
    beginning_wallet_balance = 0
    ending_wallet_balance = 0
    amount_type = AmountType.INDIVIDUAL
    created_at = datetime.datetime.now()
    wallet_id = 1
    is_unlimited = False


class ReimbursementRequestToCostBreakdownFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = ReimbursementRequestToCostBreakdown

    claim_type = ClaimType.EMPLOYER
