from common.services.api import AuthenticatedResource
from utils import launchdarkly


class LaunchDarklyContextResource(AuthenticatedResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        context = launchdarkly.context(self.user)
        return context.to_dict()
