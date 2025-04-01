from __future__ import annotations

import sqlalchemy as sa
from maven import feature_flags

from payer_accumulator.accumulation_data_sourcer import (
    AccumulationDataSourcer,
    ProcedureToAccumulationData,
)
from payer_accumulator.common import PayerName
from utils.log import logger
from wallet.models.reimbursement_organization_settings import (
    EmployerHealthPlan,
    ReimbursementOrganizationSettings,
)
from wallet.models.reimbursement_wallet import MemberHealthPlan
from wallet.repository.health_plan import (
    HEALTH_PLAN_YOY_FLAG,
    OLD_BEHAVIOR,
    HealthPlanRepository,
)

log = logger(__name__)


class AccumulationDataSourcerESI(AccumulationDataSourcer):
    def __init__(self, session: sa.orm.Session = None):  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "Session")
        super().__init__(payer_name=PayerName.ESI, session=session)

    # instance level cache of _accumulation_employer_health_plans
    _cached_accumulation_employer_health_plans: list[EmployerHealthPlan] | None = None

    @property
    def _accumulation_employer_health_plans(self) -> list[EmployerHealthPlan]:
        if self._cached_accumulation_employer_health_plans:
            return self._cached_accumulation_employer_health_plans

        self._cached_accumulation_employer_health_plans = (
            self.session.query(EmployerHealthPlan)  # type: ignore[union-attr] # Item "None" of "Optional[Session]" has no attribute "query"
            .join(
                ReimbursementOrganizationSettings,
                ReimbursementOrganizationSettings.id
                == EmployerHealthPlan.reimbursement_org_settings_id,
            )
            .filter(
                sa.and_(
                    EmployerHealthPlan.rx_integrated == sa.false(),
                    ReimbursementOrganizationSettings.deductible_accumulation_enabled
                    == sa.true(),
                )
            )
            .all()
        )
        return self._cached_accumulation_employer_health_plans  # type: ignore[return-value] # Incompatible return value type (got "Optional[List[EmployerHealthPlan]]", expected "List[EmployerHealthPlan]")

    def _get_medical_and_rx_accumulation_wallet_ids(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        rx_wallet_ids = []
        for plan in self._accumulation_employer_health_plans:
            if (
                feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
                != OLD_BEHAVIOR
            ):
                wallet_ids = (
                    self.health_plan_repo.get_all_wallet_ids_for_an_employer_plan(
                        employer_plan_id=plan.id
                    )
                )
                if not wallet_ids:
                    log.info(f"No wallets for employer_health_plan with id {plan.id}")
                else:
                    rx_wallet_ids.extend(wallet_ids)
            else:
                wallet_ids = (
                    MemberHealthPlan.query.with_entities(  # noqa
                        MemberHealthPlan.reimbursement_wallet_id
                    )
                    .filter_by(employer_health_plan_id=plan.id)
                    .all()
                )
                if not wallet_ids:
                    log.info(f"No wallets for employer_health_plan with id {plan.id}")
                else:
                    rx_wallet_ids.extend(
                        wallet_id.reimbursement_wallet_id for wallet_id in wallet_ids  # type: ignore[attr-defined]
                    )
        return None, rx_wallet_ids

    def _mapping_is_this_payer(
        self,
        health_plan_repo: HealthPlanRepository,  # noqa
        procedure_data: ProcedureToAccumulationData,
    ) -> bool:
        # Now that health plans are per-time period,
        # it's possible for a wallet to appear in multiple data sourcing runs
        # We only want to insert procedures associated with the right payer per-sourcing run.
        employer_health_plan = (
            health_plan_repo.get_employer_plan_by_wallet_and_member_id(
                wallet_id=procedure_data.wallet_id,
                member_id=procedure_data.member_id,
                effective_date=procedure_data.start_date,
            )
        )
        # HOWEVER, for ESI, procedures will always be associated with the wrong payer.
        # Therefore we only check that the current EHP has the right rx integrated condition.
        return bool(
            employer_health_plan and employer_health_plan.rx_integrated is False
        )
