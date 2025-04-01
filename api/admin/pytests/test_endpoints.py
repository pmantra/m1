import re

from admin.factory import create_app as create_admin_app
from pytests.utils.test_service_owner_mapper import TestOwnerMappingsUpToDate
from utils.service_owner_mapper import admin_endpoint_service_ns_mapper


def test_for_unexpected_admin_endpoints():
    def rule_to_endpoint(rule):
        endpoint = str(rule)
        # the service mapper uses (.+?) where the flask routes use named params: correct for this
        endpoint = re.sub(r"\<.*?\>", "(.+?)", endpoint)
        return endpoint

    app = create_admin_app()
    flask_route_set = {rule_to_endpoint(rule) for rule in app.url_map.iter_rules()}
    mapped_endpoints_set = {
        endpoint for endpoint in admin_endpoint_service_ns_mapper.keys()
    }
    admin_known_unmapped_routes_set = (
        TestOwnerMappingsUpToDate.admin_known_unmapped_routes_set
    )

    # find all routes in flask which do not have a service mapped
    unmapped_routes = flask_route_set - mapped_endpoints_set
    unexpected_unmapped_routes = unmapped_routes - admin_known_unmapped_routes_set

    assert unexpected_unmapped_routes == set(), (
        "Please add new routes to utils.service_owner_mapper.endpoint_service_ns_mapper! \n"
        "Please DO NOT add new routes to the unmapped set in TestOwnerMappingsUpToDate! \n"
        f"New routes: {unexpected_unmapped_routes}"
    )
