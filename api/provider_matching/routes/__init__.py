from . import care_team_assignment


def add_routes(api):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    api = care_team_assignment.add_routes(api)
    return api
