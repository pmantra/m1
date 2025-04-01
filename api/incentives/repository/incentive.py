import ddtrace

from incentives.models.incentive import (
    Incentive,
    IncentiveOrganization,
    IncentiveOrganizationCountry,
)
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class IncentiveRepository:
    @ddtrace.tracer.wrap()
    def get(self, *, id: int) -> Incentive:
        incentive = db.session.query(Incentive).get(id)
        return incentive

    def get_incentive_by_name(self, name) -> Incentive:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        return db.session.query(Incentive).filter(Incentive.name == name).first()

    @ddtrace.tracer.wrap()
    def get_by_params(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        user_id,
        country_code,
        organization_id,
        incentivized_action,
        track,
    ):
        """
        Return user's active incentive given params
        """
        # Query IncentiveOrganization for given params
        user_incentives = (
            db.session.query(IncentiveOrganization.incentive_id)
            .filter(
                IncentiveOrganization.organization_id == organization_id,
                IncentiveOrganization.action == incentivized_action,
                IncentiveOrganization.track_name == track,
                IncentiveOrganization.active == True,
            )
            .join(
                IncentiveOrganizationCountry,
                IncentiveOrganization.id
                == IncentiveOrganizationCountry.incentive_organization_id,
            )
            .filter(IncentiveOrganizationCountry.country_code == country_code)
            .order_by(IncentiveOrganization.created_at.desc())
            .all()
        )

        if len(user_incentives) > 1:
            # DD log monitor: https://app.datadoghq.com/monitors/133785960
            log.warning(
                "More than one active incentive configured for user",
                user_id=user_id,
                country_code=country_code,
                organization_id=organization_id,
                incentivized_action=incentivized_action,
                track=track,
                incentives=[ui[0] for ui in user_incentives],
            )
        incentive_id = user_incentives[0][0] if user_incentives else None

        if not incentive_id:
            log.info(
                "No incentive found for user",
                user_id=user_id,
                country_code=country_code,
                organization_id=organization_id,
                incentivized_action=incentivized_action,
                track=track,
            )
            return None
        log.info(
            "Incentive found for user",
            incentive_id=incentive_id,
            user_id=user_id,
            country_code=country_code,
            organization_id=organization_id,
            incentivized_action=incentivized_action,
            track=track,
        )

        # Get incentive object given incentive_id
        incentive = db.session.query(Incentive).get(incentive_id)

        return incentive
