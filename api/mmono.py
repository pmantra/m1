"""
mmono.py

Helpful commands for using the Maven Monolith flask app.

Usage:
    mmono.py routes
    mmono.py feature <new_feature_name>

Options:
  -h --help     Show this screen.
  routes        Print all routes in the flask app.
  feature       Create the skeleton for a new feature directory.
"""
import os

# This MUST happen before we import any internal modules
#   because of numerous import-time side-effects.
os.environ["DISABLE_TRACING"] = "1"
os.environ["DEV_LOGGING"] = "1"

from docopt import docopt

from app import create_app
from utils.log import logger

log = logger(__name__)


def routes() -> None:
    # Get routes
    app = create_app()
    route_list = []
    for rule in app.url_map.iter_rules():
        for method in rule.methods:
            if method not in ["HEAD", "OPTIONS"]:
                data = [str(rule), rule.endpoint, method]
                route_list.append(data)
    # Alphabetize routes
    route_list = sorted(route_list, key=lambda rule: rule[0])
    # Handle table formatting
    len_url = len(max(route_list, key=lambda route: len(route[0]))[0])
    len_resource = len(max(route_list, key=lambda route: len(route[1]))[1])
    format = "{{0:{len_url}}} | {{1:{len_resource}}} | {{2}}".format(
        len_url=len_url, len_resource=len_resource
    )
    # Print table headers
    print(format.format("URL", "Resource", "Method"))
    print(f"{{:-<{len_url+len_resource+15}}}".format("-"))
    for item in route_list:
        print(format.format(*item))


def new_feature(name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    name = name.lower()
    print(f"Creating new api subdirectory: {name}")
    os.mkdir(name)
    print("Creating __init__.py file...")
    with open(f"{name}/__init__.py", mode="a"):
        pass
    print("Creating feature directories: models, routes, services, tests, utils...")
    os.mkdir(f"{name}/models")
    os.mkdir(f"{name}/routes")
    os.mkdir(f"{name}/services")
    os.mkdir(f"{name}/tests")
    os.mkdir(f"{name}/utils")
    print(f"Done! {name} is ready!")


def main() -> None:
    args = docopt(__doc__)
    if args["routes"]:
        routes()
    elif args["feature"]:
        new_feature(name=args["<new_feature_name>"])
    else:
        log.debug("Command not found.")


if __name__ == "__main__":
    main()
