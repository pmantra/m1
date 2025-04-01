from __future__ import annotations

import datetime
from typing import List, Optional

import sqlalchemy.orm
from maven import feature_flags
from sqlalchemy import distinct
from sqlalchemy.sql import and_, func, or_

from utils.log import logger
from wallet.models.constants import (
    FamilyPlanType,
    MemberHealthPlanPatientRelationship,
    MemberHealthPlanPatientSex,
)
from wallet.models.reimbursement_organization_settings import EmployerHealthPlan
from wallet.models.reimbursement_wallet import MemberHealthPlan

log = logger(__name__)

HEALTH_PLAN_YOY_FLAG = "enable-yoy-member-health-plan-temporality"
OLD_BEHAVIOR = "use_no_api_no_asof_date"  # Queries are made directly from callsites, and no ASOF time is applied. Default value.
LOGGING_BEHAVIOR = "use_api_no_asof_date"  # Queries are made via the new consolidated data access api. ASOF time is passed in as a parameter only for logging.
NEW_BEHAVIOR = "use_api_asof_date"  # Queries are made via the new consolidated data access api. ASOF time is passed in as a parameter and used to pick the correct member health plan


class HealthPlanRepository:
    __slots__ = ["session"]

    def __init__(self, session: sqlalchemy.orm.Session):
        self.session = session

    def get_member_plan(self, *, id: int) -> MemberHealthPlan | None:
        return self.session.query(MemberHealthPlan).get(id)

    def get_employer_plan(self, *, id: int) -> EmployerHealthPlan | None:
        return self.session.query(EmployerHealthPlan).get(id)

    def get_employer_plan_by_member_health_plan_id(
        self, *, id: int
    ) -> EmployerHealthPlan | None:
        return (
            self.session.query(EmployerHealthPlan)
            .join(
                MemberHealthPlan,
                MemberHealthPlan.employer_health_plan_id == EmployerHealthPlan.id,
            )
            .filter(MemberHealthPlan.id == id)
            .one_or_none()
        )

    def get_member_plan_by_wallet_and_member_id(
        self, *, member_id: int, wallet_id: int, effective_date: datetime
    ) -> MemberHealthPlan | None:
        query = self.session.query(MemberHealthPlan).filter(
            MemberHealthPlan.member_id == member_id,
            MemberHealthPlan.reimbursement_wallet_id == wallet_id,
        )
        if (
            feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
            == NEW_BEHAVIOR
        ):
            query = query.filter(
                effective_date >= MemberHealthPlan.plan_start_at,
                or_(
                    effective_date <= MemberHealthPlan.plan_end_at,
                    MemberHealthPlan.plan_end_at.is_(None),
                ),
            )
        else:
            log.info(
                "Member Health Plan Year Over Year Migration",
                query="get_member_plan_by_wallet_and_member_id",
                member_id=str(member_id),
                wallet_id=str(wallet_id),
                effective_date=effective_date,
            )
        return query.one_or_none()

    def get_employer_plan_by_wallet_and_member_id(
        self, *, member_id: int, wallet_id: int, effective_date: datetime
    ) -> EmployerHealthPlan | None:
        query = (
            self.session.query(EmployerHealthPlan)
            .join(
                MemberHealthPlan,
                MemberHealthPlan.employer_health_plan_id == EmployerHealthPlan.id,
            )
            .filter(
                MemberHealthPlan.member_id == member_id,
                MemberHealthPlan.reimbursement_wallet_id == wallet_id,
            )
        )
        if (
            feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
            == NEW_BEHAVIOR
        ):
            query = query.filter(
                effective_date >= MemberHealthPlan.plan_start_at,
                or_(
                    effective_date <= MemberHealthPlan.plan_end_at,
                    MemberHealthPlan.plan_end_at.is_(None),
                ),
            )
        else:
            log.info(
                "Member Health Plan Year Over Year Migration",
                query="get_employer_plan_by_wallet_and_member_id",
                member_id=str(member_id),
                wallet_id=str(wallet_id),
                effective_date=effective_date,
            )
        return query.one_or_none()

    def get_all_plans_for_multiple_dates(
        self, *, member_id: int, wallet_id: int, all_dates: List[datetime]
    ) -> List[MemberHealthPlan]:
        query = (
            self.session.query(MemberHealthPlan)
            .filter(
                MemberHealthPlan.member_id == member_id,
                MemberHealthPlan.reimbursement_wallet_id == wallet_id,
            )
            .order_by(MemberHealthPlan.plan_start_at)
        )
        filter_statement = []
        if (
            feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
            == NEW_BEHAVIOR
        ):
            for date in all_dates:
                filter_statement.append(
                    and_(
                        date >= MemberHealthPlan.plan_start_at,
                        or_(
                            date <= MemberHealthPlan.plan_end_at,
                            MemberHealthPlan.plan_end_at.is_(None),
                        ),
                    )
                )
        else:
            log.info(
                "Member Health Plan Year Over Year Migration",
                query="get_all_plans_for_multiple_dates",
                member_id=str(member_id),
                wallet_id=str(wallet_id),
                effective_date=all_dates,
            )
        return query.filter(or_(*filter_statement)).all()

    def get_all_wallet_ids_for_an_employer_plan(
        self, *, employer_plan_id: int
    ) -> List[int]:
        results = (
            self.session.query(distinct(MemberHealthPlan.reimbursement_wallet_id))
            .join(
                EmployerHealthPlan,
                MemberHealthPlan.employer_health_plan_id == EmployerHealthPlan.id,
            )
            .filter(EmployerHealthPlan.id == employer_plan_id)
            .all()
        )
        # de-tuple-ify since we don't have .scalars in this version of sqlalchemy
        return [row[0] for row in results]

    def get_member_plan_by_demographics(
        self,
        subscriber_last_name: Optional[str] = None,
        *,
        subscriber_id: str,
        patient_first_name: str,
        patient_last_name: str,
        effective_date: datetime,
    ) -> MemberHealthPlan | None:

        query = self.session.query(MemberHealthPlan).filter(
            MemberHealthPlan.subscriber_insurance_id == subscriber_id,
            MemberHealthPlan.patient_first_name == patient_first_name,
            MemberHealthPlan.patient_last_name == patient_last_name,
        )
        if subscriber_last_name:
            query = query.filter(
                MemberHealthPlan.subscriber_last_name == subscriber_last_name
            )
        if (
            feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
            == NEW_BEHAVIOR
        ):
            query = query.filter(
                effective_date >= MemberHealthPlan.plan_start_at,
                or_(
                    effective_date <= MemberHealthPlan.plan_end_at,
                    MemberHealthPlan.plan_end_at.is_(None),
                ),
            )
            return query.one_or_none()
        else:
            log.info(
                "Member Health Plan Year Over Year Migration",
                query="get_member_plan_by_demographics",
                subscriber_id=str(subscriber_id),
                effective_date=effective_date,
            )

            return query.first()

    def get_family_member_plan_effective_date(
        self,
        *,
        subscriber_id: str,
        effective_date: datetime,
    ) -> datetime.datetime | None:

        if (
            feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
            == NEW_BEHAVIOR
        ):
            query = self.session.query(func.min(MemberHealthPlan.plan_start_at)).filter(
                MemberHealthPlan.subscriber_insurance_id == subscriber_id,
                effective_date >= MemberHealthPlan.plan_start_at,
                or_(
                    effective_date <= MemberHealthPlan.plan_end_at,
                    MemberHealthPlan.plan_end_at.is_(None),
                ),
            )
            return query.scalar()
        else:
            log.info(
                "Member Health Plan Year Over Year Migration",
                query="get_family_member_plan_effective_date",
                subscriber_id=str(subscriber_id),
                effective_date=effective_date,
            )
            return None

    def has_valid_member_plan_dates(
        self,
        member_id: int,
        wallet_id: int,
        start_at: datetime.datetime,
        end_at: datetime.datetime,
    ) -> bool:
        # TODO: add relevant index/indices
        sql = """
            SELECT COUNT(*) FROM member_health_plan as mhp
            WHERE (
                # starts within the bounds of an existing plan
                :start_at > mhp.plan_start_at and :start_at < mhp.plan_end_at
            ) OR (
                # ends within the bounds of an existing plan
                :end_at < mhp.plan_end_at and :end_at > mhp.plan_start_at
            ) OR (
                # contains an existing plan within its' timespan
                :start_at <= mhp.plan_start_at and :end_at >= mhp.plan_end_at
            ) OR (
                # starts during an open-ended plan
                :start_at >= mhp.plan_start_at and mhp.plan_end_at is NULL
            )
            AND mhp.plan_start_at IS NOT NULL
            AND mhp.member_id = :member_id AND mhp.reimbursement_wallet_id = :wallet_id
            """
        res = self.session.execute(
            sql,
            {
                "member_id": member_id,
                "wallet_id": wallet_id,
                "start_at": start_at,
                "end_at": end_at,
            },
        ).scalar()
        # any result > 0 means the proposed start and end dates are invalid
        return not bool(res)

    def has_valid_member_plan_start_date(
        self, member_id: int, wallet_id: int, start_at: datetime.datetime
    ) -> bool:
        sql = """
            SELECT COUNT(*) FROM member_health_plan as mhp
            WHERE (
                # cannot have an open-ended plan including a close-ended plan
                :start_at < mhp.plan_start_at and mhp.plan_end_at is NOT NULL
            ) OR (
                # starts within the bounds of an existing plan
                :start_at > mhp.plan_start_at and :start_at < mhp.plan_end_at
            ) OR (
                # An open-ended plan exists -- cannot have two open ended plans
                mhp.plan_end_at is NULL
            ) 
            AND mhp.plan_start_at IS NOT NULL
            AND mhp.member_id = :member_id AND mhp.reimbursement_wallet_id = :wallet_id
            """
        res = self.session.execute(
            sql, {"member_id": member_id, "wallet_id": wallet_id, "start_at": start_at}
        ).scalar()
        # any result > 0 means the proposed start and end dates are invalid
        return not bool(res)

    def has_member_health_plan_by_wallet_and_member_id(
        self, *, member_id: int, wallet_id: int, effective_date: datetime.date
    ) -> bool:
        """
        Convenience method to check if a member health plan exists for the member_id and wallet_id at the effective date
        :param member_id: The member's user id - (table user, field id)
        :param wallet_id: The wallet id.
        :param effective_date: The date at which we are checking for the existence of a member plan
        :return: True if plan found, false otherwise
        """
        return bool(
            self.get_member_plan_by_wallet_and_member_id(
                member_id=member_id,
                wallet_id=wallet_id,
                effective_date=effective_date,
            )
        )

    def create_member_health_plan(
        self,
        employer_health_plan_id: int,
        reimbursement_wallet_id: int,
        member_id: int,
        subscriber_insurance_id: str,
        plan_type: FamilyPlanType,
        is_subscriber: bool,
        subscriber_first_name: str | None,
        subscriber_last_name: str | None,
        subscriber_date_of_birth: datetime.date | None,
        patient_first_name: str | None,
        patient_last_name: str | None,
        patient_date_of_birth: datetime.date | None,
        patient_sex: MemberHealthPlanPatientSex | None,
        patient_relationship: MemberHealthPlanPatientRelationship | None,
        plan_start_at: datetime.datetime | None,
        plan_end_at: datetime.datetime | None,
    ) -> MemberHealthPlan:
        """
        Passthrough function to create a MemberHealthPlan object in memory. This will not commit to the DB.
        The caller must commit by calling health_repository.session.commit().
        """

        member_health_plan = MemberHealthPlan(
            employer_health_plan_id=employer_health_plan_id,
            reimbursement_wallet_id=reimbursement_wallet_id,
            member_id=member_id,
            is_subscriber=is_subscriber,
            subscriber_insurance_id=subscriber_insurance_id,
            subscriber_first_name=subscriber_first_name,
            subscriber_last_name=subscriber_last_name,
            subscriber_date_of_birth=subscriber_date_of_birth,
            patient_first_name=patient_first_name,
            patient_last_name=patient_last_name,
            patient_date_of_birth=patient_date_of_birth,
            patient_sex=patient_sex,
            patient_relationship=patient_relationship,
            plan_start_at=plan_start_at,
            plan_end_at=plan_end_at,
            plan_type=plan_type,
        )
        self.session.add(member_health_plan)

        return member_health_plan

    def get_subscriber_member_health_plan(
        self,
        *,
        subscriber_id: str,
        employer_health_plan_id: int,
        plan_start_at_earliest: datetime,
        plan_end_at_latest: datetime,
    ) -> MemberHealthPlan | None:
        """
        Retrieves the subscriber's health plan record within a specified date range. Only returns plans where
        is_subscriber=True.
        :param subscriber_id: The ID of the subscriber
        :param employer_health_plan_id: The ID of the employer health plan.
        :param plan_start_at_earliest: The earliest possible start date for the plan.
        :param plan_end_at_latest: The latest possible end date for the plan.
        :return: The `MemberHealthPlan` object if found, or `None` if no matching plan is found or the
                feature flag is not set to `NEW_BEHAVIOR`.
        """
        if (
            feature_flags.str_variation(HEALTH_PLAN_YOY_FLAG, default=OLD_BEHAVIOR)
            != NEW_BEHAVIOR
        ):
            log.warning("This method is not supported for OLD_BEHAVIOR.")
            return None

        query = self.session.query(MemberHealthPlan).filter(
            MemberHealthPlan.employer_health_plan_id == employer_health_plan_id,
            MemberHealthPlan.subscriber_insurance_id == subscriber_id,
            MemberHealthPlan.is_subscriber,
            MemberHealthPlan.plan_start_at >= plan_start_at_earliest,
            MemberHealthPlan.plan_end_at <= plan_end_at_latest,
        )
        return query.one_or_none()
