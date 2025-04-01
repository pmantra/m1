from typing import Any

import requests
from requests import Response

from ci_test.log import err
from ci_test.settings import api_url, gl_headers, project_id


def fetch(path: str) -> Response:
    url = f"{api_url}/projects/{project_id}/{path}"
    err(f"fetching {url}")
    try:
        res = requests.get(url, headers=gl_headers)
        res.raise_for_status()
        return res
    except Exception as e:
        err(f"Error encountered fetching '{url}': {e}")
        raise


def fetch_json(path: str) -> Any:
    res = fetch(path)
    try:
        return res.json()
    except Exception as e:
        err(f"Error encountered parsing json from '{path}': {e}")
        raise
