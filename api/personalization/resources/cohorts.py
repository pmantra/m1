from typing import Union

from common.services.api import AuthenticatedResource
from personalization.services.cohorts import PersonalizationCohortsService


class CohortsResource(AuthenticatedResource):
    def get(self) -> dict[str, dict[str, Union[str, bool, None]]]:
        personalization_cohorts_service = PersonalizationCohortsService(self.user)
        return {"personalization_cohorts": personalization_cohorts_service.get_all()}
