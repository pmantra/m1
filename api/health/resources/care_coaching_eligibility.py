from __future__ import annotations

from dataclasses import asdict, dataclass

from common.services.api import AuthenticatedResource
from health.services.care_coaching_eligibility_service import (
    CareCoachingEligibilityService,
)
from providers.service.provider import ProviderService


@dataclass
class CareCoachingEligibilityResponse:
    is_eligible_for_care_coaching: bool
    is_member_matched_to_coach_for_active_track: bool


class CareCoachingEligibilityResource(AuthenticatedResource):
    def __init__(self) -> None:
        super().__init__()
        self.care_coaching_eligibility_service = CareCoachingEligibilityService()
        self.provider_service = ProviderService()

    def get(self) -> dict:
        return asdict(
            CareCoachingEligibilityResponse(
                is_eligible_for_care_coaching=self.care_coaching_eligibility_service.is_user_eligible_for_care_coaching(
                    self.user
                ),
                is_member_matched_to_coach_for_active_track=self.provider_service.is_member_matched_to_coach_for_active_track(
                    self.user
                ),
            )
        )
