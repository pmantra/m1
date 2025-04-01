import pathlib
from typing import List

from utils.log import logger

log = logger(__name__)


def load_queries_from_file(file_path: str) -> List[str]:
    """
    Load SQL queries from api/{file_path}.

    Make sure to provide the absolute file path after "api/" when
    using this util function.

    Raises: FileNotFoundError: when the provided path is invalid.
    """
    query_file_path = f"{pathlib.Path(__file__).parents[2]}/{file_path}"
    with open(query_file_path, "r") as query_file:
        file_content = query_file.read()
    # remove the empty item at the end of the list after split by ;
    return file_content.split(";")[:-1]
