import functools
import os

import requests

_instance_metadata_project_id_url = (
    "http://metadata.google.internal/computeMetadata/v1/project/project-id"
)


# N.B. - This function will be called frequently so we memoize the results.
@functools.lru_cache(maxsize=1)
def get_project_id() -> str:
    response = requests.get(
        _instance_metadata_project_id_url, headers={"Metadata-Flavor": "Google"}
    )
    response.raise_for_status()

    return response.text


# `get_project_id()` is cached, but exceptions are heavy. let's only do this once.
@functools.lru_cache(maxsize=1)
def safe_get_project_id(default: str = "") -> str:
    if os.environ.get("NODE_NAME") == "m01":
        return "local-development"
    elif os.environ.get("NODE_NAME") == "gitlab-saas":
        return "gitlab-saas"
    else:
        try:
            # Ask google for project metadata if deployed remotely.
            return get_project_id()
        except requests.RequestException:
            # The metadata request connected, but otherwise failed.
            return default
