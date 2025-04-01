import os
from typing import Optional

from sqlalchemy.engine import url

from utils.database import construct_dsn
from utils.log import logger

log = logger(__name__)

_base_dev_db_params = {
    "drivername": "mysql+pymysql",
    "username": "root",
    "password": "root",
    "host": "mysql",
    "port": None,
}


def create_sqlalchemy_binds() -> dict:
    _default_db_url = apply_dsn_namespacing(
        url.make_url(
            os.environ.get(
                "DEFAULT_DB_URL",
                construct_dsn(**_base_dev_db_params, database="maven"),  # type: ignore[arg-type] # Argument 2 to "get" of "Mapping" has incompatible type "URL"; expected "Union[str, bytes]" #type: ignore[arg-type] # Argument 1 to "construct_dsn" has incompatible type "**Dict[str, Optional[str]]"; expected "str" #type: ignore[arg-type] # Argument 1 to "construct_dsn" has incompatible type "**Dict[str, Optional[str]]"; expected "Optional[int]" #type: ignore[arg-type] # Argument 1 to "construct_dsn" has incompatible type "**Dict[str, Optional[str]]"; expected "Optional[Dict[Any, Any]]"
            )
        )
    )

    _replica1_db_url = apply_dsn_namespacing(
        url.make_url(os.environ.get("REPLICA1_DB_URL"))  # type: ignore[arg-type] # Argument 1 to "make_url" has incompatible type "Optional[str]"; expected "Union[str, bytes]"
    )

    if not _replica1_db_url:
        log.debug(
            "No replica1 db url found. Using the default DB for replica usage instead."
        )
        _replica1_db_url = _default_db_url

    return {
        "default": _default_db_url,
        "replica1": _replica1_db_url,
    }


def apply_dsn_namespacing(dsn: Optional[url.URL]) -> url.URL:
    if dsn:
        dsn.database = apply_app_environment_namespace(dsn.database)
    return dsn  # type: ignore[return-value] # Incompatible return value type (got "Optional[URL]", expected "URL")


def apply_app_environment_namespace(identifier: str) -> str:
    """
    Applies standard formatting for adding a multi-tenant namespace to an identifier string
    when in the presence of an APP_ENVIRONMENT_NAMESPACE env variable
    """

    if not identifier:
        raise ValueError("No identifier provided for namespacing.")

    namespace = os.environ.get("APP_ENVIRONMENT_NAMESPACE")

    if namespace:
        return f"{namespace}__{identifier}"
    return identifier
