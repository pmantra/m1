import pathlib
from glob import glob

from utils.log import logger

log = logger(__name__)


def load_queries_from_directory(directory_path: str) -> dict[str, list[str]]:
    """
    Load SQL queries from api/{directory_path}.

    The function returns a dictionary where keys are filenames without extensions
    and values are lists of SQL queries.

    Raises: FileNotFoundError: when the provided directory path is invalid.
    """
    query_directory_path = f"{pathlib.Path(__file__).parents[2]}/{directory_path}"
    query_files = glob(f"{query_directory_path}/*.sql")

    if not query_files:
        raise FileNotFoundError(f"No SQL files found in {query_directory_path}")

    queries = {}
    for query_file_path in query_files:
        file_name = pathlib.Path(query_file_path).stem
        with open(query_file_path, "r") as query_file:
            file_content = query_file.read()
        # remove the empty item at the end of the list after split by ;
        queries[file_name] = file_content.split(";")[:-1]

    return queries
