from appointments.models.cancellation_policy import CancellationPolicy
from appointments.schemas.appointments import CancellationPoliciesSchema
from common.services.api import AuthenticatedResource


class CancellationPoliciesResource(AuthenticatedResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        policies = CancellationPolicy.query.all()

        schema = CancellationPoliciesSchema()
        return schema.dump({"data": policies}).data
