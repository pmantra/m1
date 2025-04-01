import sys
from dataclasses import dataclass
from typing import Callable, Generic, List, Optional, TypeVar, Union

import ddtrace

from authn.models.user import User
from health.services.member_health_cohorts_service import MemberHealthCohortsService
from utils.log import logger

T = TypeVar("T", Optional[str], Optional[bool])

log = logger(__name__)


@dataclass
class Cohort(Generic[T]):
    key: str
    function: Callable[[], T]
    default: T


class PersonalizationCohortsService:
    def __init__(self, user: User):
        self.user = user
        self.member_health_cohort_service = MemberHealthCohortsService(user)
        self.cohorts: List[Union[Cohort[Optional[str]], Cohort[Optional[bool]]]] = [
            Cohort(
                key="sex_at_birth",
                function=lambda: self.member_health_cohort_service.sex_at_birth,
                default=None,
            ),
            Cohort[Optional[bool]](
                key="targeted_for_cycle_tracking",
                function=self.member_health_cohort_service.is_targeted_for_cycle_tracking,
                default=None,
            ),
            Cohort[Optional[bool]](
                key="targeted_for_ovulation_tracking",
                function=self.member_health_cohort_service.is_targeted_for_ovulation_tracking,
                default=None,
            ),
            Cohort[Optional[bool]](
                key="targeted_for_ovulation_medication",
                function=self.member_health_cohort_service.is_targeted_for_ovulation_medication,
                default=None,
            ),
        ]

    def get_all(self) -> dict[str, Union[str, bool, None]]:
        results: dict[str, Union[str, bool, None]] = {}
        for cohort in self.cohorts:
            with ddtrace.tracer.trace(
                "personalization.services.cohorts.get"
            ) as cohort_span:
                cohort_span.set_tag("cohort", cohort.key)
                try:
                    results[cohort.key] = cohort.function()
                except Exception:
                    results[cohort.key] = cohort.default
                    log.warning(
                        "Exception getting cohort value, using default instead",
                        cohort=cohort.key,
                        exc_info=True,
                    )
                    cohort_span.set_exc_info(*sys.exc_info())

        return results
