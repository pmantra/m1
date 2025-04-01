from .advocate_assignment import AdvocateAssignmentResource
from .care_advocate import (
    CareAdvocatesAssignResource,
    CareAdvocatesPooledAvailabilityResource,
    CareAdvocatesSearchResource,
)


def add_routes(api):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    api.add_resource(CareAdvocatesSearchResource, "/v1/care_advocates/search")
    api.add_resource(
        CareAdvocatesPooledAvailabilityResource,
        "/v1/care_advocates/pooled_availability",
    )
    api.add_resource(CareAdvocatesAssignResource, "/v1/care_advocates/assign")
    api.add_resource(
        AdvocateAssignmentResource, "/v1/advocate-assignment/reassign/<int:user_id>"
    )
    return api
