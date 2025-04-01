from common.services.api import AuthenticatedResource
from health.models.health_profile import LIFE_STAGES


class LifeStagesResource(AuthenticatedResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return LIFE_STAGES
