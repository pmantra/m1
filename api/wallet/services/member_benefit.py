from __future__ import annotations

from utils.log import logger
from wallet.repository.member_benefit import MemberBenefitRepository

log = logger(__name__)


class MemberBenefitService:
    def __init__(self, member_benefit_repo: MemberBenefitRepository | None = None):
        self.member_benefit_repo: MemberBenefitRepository = (
            member_benefit_repo or MemberBenefitRepository()
        )

    def add_for_user(self, user_id: int) -> str:
        try:
            benefit_id = self.member_benefit_repo.add(user_id=user_id)
        except Exception as e:
            log.exception("Exception encountered while generating benefit ID", error=e)
            raise e  # re-raise the exception

        if benefit_id == "-1":
            log.info(
                "Failed to generate new unique benefit ID",
                benefit_id=str(benefit_id),
                user_id=str(user_id),
            )
        else:
            log.info(
                "Successfully generated new unique benefit ID",
                benefit_id=str(benefit_id),
                user_id=str(user_id),
            )

        return benefit_id
