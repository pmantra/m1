import flask_restful

from personalization.resources.cohorts import CohortsResource


def add_routes(api: flask_restful.Api) -> flask_restful.Api:
    api.add_resource(CohortsResource, "/v1/-/personalization/cohorts")

    return api
