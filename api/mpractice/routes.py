from mpractice.resource.provider_appointment import (
    ProviderAppointmentResource,
    ProviderAppointmentResourceV2,
)
from mpractice.resource.provider_appointments import (
    ProviderAppointmentsResource,
    ProviderAppointmentsResourceV2,
)


def add_routes(api):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # Clients should not use V1 endpoints going forward.
    api.add_resource(ProviderAppointmentsResource, "/v1/mpractice/appointments")
    api.add_resource(
        ProviderAppointmentResource, "/v1/mpractice/appointment/<int:appointment_id>"
    )

    # V2 endpoints are the same as V1 endpoints.
    # Updating the version number to align with the overall appointment migration plan.
    api.add_resource(ProviderAppointmentsResourceV2, "/v2/mpractice/appointments")
    api.add_resource(
        ProviderAppointmentResourceV2, "/v2/mpractice/appointment/<int:appointment_id>"
    )
    return api
