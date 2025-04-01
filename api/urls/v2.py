from views.fhir import V2FHIRPatientHealthResource
from views.internal import V2VerticalGroupingsResource
from views.prescription import PharmacySearchResourceV2


def add_routes(api):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    api.add_resource(V2VerticalGroupingsResource, "/v2/_/vertical_groupings")
    api.add_resource(
        V2FHIRPatientHealthResource, "/v2/users/<int:user_id>/patient_health_record"
    )
    api.add_resource(PharmacySearchResourceV2, "/v2/pharmacies/search")

    return api
