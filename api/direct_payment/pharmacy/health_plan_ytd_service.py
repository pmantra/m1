from typing import List, Optional

import ddtrace
import sqlalchemy

from direct_payment.pharmacy.models.health_plan_ytd_spend import (
    HealthPlanYearToDateSpend,
)
from direct_payment.pharmacy.repository.health_plan_ytd_spend import (
    HealthPlanYearToDateSpendRepository,
)
from direct_payment.pharmacy.repository.util import chunk
from storage.connection import db


class HealthPlanYearToDateSpendService:
    """Service layer for health_plan_year_to_date_spend resource"""

    def __init__(
        self,
        session: sqlalchemy.orm.scoping.ScopedSession = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        health_plan_ytd_repository: HealthPlanYearToDateSpendRepository = None,  # type: ignore[assignment] # Incompatible default for argument "health_plan_ytd_repository" (default has type "None", argument has type "HealthPlanYearToDateSpendRepository")
    ):
        self.session = session or db.session
        self.repository = (
            health_plan_ytd_repository
            or HealthPlanYearToDateSpendRepository(session=session)
        )

    @ddtrace.tracer.wrap()
    def get_all_by_policy(
        self, policy_id: str, year: int
    ) -> List[HealthPlanYearToDateSpend]:
        return self.repository.get_all_by_policy(policy_id=policy_id, year=year)

    @ddtrace.tracer.wrap()
    def get_all_by_member(
        self, policy_id: str, year: int, first_name: str, last_name: str
    ) -> List[HealthPlanYearToDateSpend]:
        return self.repository.get_all_by_member(
            policy_id=policy_id, year=year, first_name=first_name, last_name=last_name
        )

    @ddtrace.tracer.wrap()
    def update(self, records: List[HealthPlanYearToDateSpend]):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Records is a list of records from ESI Ingestion
        """
        batches = chunk(records, 50)
        for batch in batches:
            # business logic
            self.repository.upsert(instances=batch)  # type: ignore[attr-defined] # "HealthPlanYearToDateSpendRepository" has no attribute "upsert"

    @ddtrace.tracer.wrap()
    def create(
        self, instance: HealthPlanYearToDateSpend
    ) -> Optional[HealthPlanYearToDateSpend]:
        return self.repository.create(instance=instance)

    @ddtrace.tracer.wrap()
    def batch_create(self, records: List[HealthPlanYearToDateSpend], batch: int = 50):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Records is a list of records from ESI Ingestion
        """
        batches = chunk(records, batch)
        affected_rows = 0
        for batch in batches:
            # business logic
            affected_rows += self.repository.batch_create(instances=batch)
        return affected_rows
