from __future__ import annotations

import datetime
from typing import List

import ddtrace.ext
import sqlalchemy.orm
from sqlalchemy import func

from authn.models.user import User
from health.models.health_profile import HealthProfile
from models.profiles import MemberProfile
from storage import connection
from utils.log import logger
from wallet.models.member_benefit import MemberBenefit
from wallet.models.models import MemberBenefitProfile
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers

log = logger(__name__)
trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)


class MemberBenefitRepository:
    def __init__(self, session: sqlalchemy.orm.scoping.ScopedSession = None):  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        self.session = session or connection.db.session

    @trace_wrapper
    def add(self, user_id: int) -> str:
        query = f"SELECT add_benefit_id_for_member({user_id});"
        return self.session.scalar(query)

    @trace_wrapper
    def get_by_user_id(self, user_id: int) -> MemberBenefit:
        return self.session.query(MemberBenefit).filter_by(user_id=user_id).one()

    @trace_wrapper
    def get_by_benefit_id(self, benefit_id: str) -> MemberBenefit:
        return self.session.query(MemberBenefit).filter_by(benefit_id=benefit_id).one()

    @trace_wrapper
    def get_by_wallet_id(self, wallet_id: int) -> List[MemberBenefit]:
        return (
            self.session.query(MemberBenefit)
            .join(
                ReimbursementWalletUsers,
                ReimbursementWalletUsers.user_id == MemberBenefit.user_id,
            )
            .join(
                ReimbursementWallet,
                ReimbursementWallet.id
                == ReimbursementWalletUsers.reimbursement_wallet_id,
            )
            .filter(ReimbursementWallet.id == wallet_id)
            .all()
        )

    @trace_wrapper
    def get_member_benefit_id(self, user_id: int) -> str | None:
        """
        Returns a member-level benefit ID if it is found, else None
        """
        query = """
            SELECT benefit_id
            FROM member_benefit
            WHERE user_id = :user_id
        """

        benefit_id: str | None = self.session.scalar(query, {"user_id": user_id})

        return benefit_id

    @trace_wrapper
    def search_by_member_benefit_id(
        self, last_name: str, date_of_birth: datetime.date, benefit_id: str
    ) -> MemberBenefitProfile | None:
        user_id_sub_select = self.session.query(MemberBenefit.user_id).filter(
            func.lower(MemberBenefit.benefit_id) == func.lower(benefit_id),
        )

        res = (
            self.session.query(
                HealthProfile,
                User.id.label("user_id"),
                User.first_name.label("first_name"),
                User.last_name.label("last_name"),
                User.email.label("email"),
                MemberBenefit.benefit_id.label("benefit_id"),  # type: ignore[attr-defined] # "str" has no attribute "label"
                MemberProfile.phone_number.label("phone_number"),
            )
            .join(HealthProfile, HealthProfile.user_id == User.id)
            .join(MemberBenefit, MemberBenefit.user_id == User.id)
            .join(MemberProfile, MemberProfile.user_id == User.id)
            .filter(User.id == user_id_sub_select)
            .one_or_none()
        )

        if not res:
            log.info(
                "[member level lookup] not found",
                benefit_id=benefit_id,
                not_found_reason="benefit_id_mismatch",
            )
            return None

        health_profile: HealthProfile = res[0]
        dob_matches: bool = date_of_birth == health_profile.birthday
        name_matches: bool = last_name.lower() == res.last_name.lower()

        if dob_matches is False and name_matches is False:
            log.info(
                "[member level lookup] not found",
                benefit_id=benefit_id,
                user_id=res.user_id,
                not_found_reason="dob_and_name_mismatch",
            )
            return None
        elif dob_matches is False:
            log.info(
                "[member level lookup] not found",
                benefit_id=benefit_id,
                user_id=res.user_id,
                not_found_reason="dob_mismatch",
            )
            return None
        elif name_matches is False:
            log.info(
                "[member level lookup] not found",
                benefit_id=benefit_id,
                user_id=res.user_id,
                not_found_reason="name_mismatch",
            )
            return None

        log.info(
            "[member level lookup] member found",
            benefit_id=benefit_id,
            user_id=res.user_id,
        )

        return MemberBenefitProfile(
            first_name=res.first_name,
            last_name=res.last_name,
            user_id=res.user_id,
            benefit_id=res.benefit_id,
            date_of_birth=health_profile.birthday,
            phone=res.phone_number,
            email=res.email,
        )
