from incentives.resources.incentive import UserIncentiveResource


def add_routes(api):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    api.add_resource(UserIncentiveResource, "/v1/users/<int:user_id>/incentive")
    return api
