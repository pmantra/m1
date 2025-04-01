from sqlalchemy.engine import url


def construct_dsn(
    drivername: str,
    username: str,
    password: str,
    host: str,
    port: int = None,  # type: ignore[assignment] # Incompatible default for argument "port" (default has type "None", argument has type "int")
    database: str = None,  # type: ignore[assignment] # Incompatible default for argument "database" (default has type "None", argument has type "str")
    query: dict = None,  # type: ignore[assignment] # Incompatible default for argument "query" (default has type "None", argument has type "Dict[Any, Any]")
) -> url.URL:
    if query is None:
        query = {"charset": "utf8mb4"}
    return url.URL(drivername, username, password, host, port, database, query)
