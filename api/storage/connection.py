from __future__ import annotations

import threading
from contextlib import contextmanager

from sqlalchemy import event, pool
from sqlalchemy.engine import Engine

from storage.connector import RoutingSQLAlchemy
from utils.log import logger

log = logger(__name__)


db = RoutingSQLAlchemy()


@event.listens_for(pool.Pool, "connect")
def set_unicode(dbapi_conn, connection_record):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # keep and testing and see if this is thread-safe
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("SET NAMES 'utf8mb4' COLLATE 'utf8mb4_unicode_ci'")
    except Exception as e:
        log.warning(f"[connection connect] when set_names exception: {e}")


class QueryExecutionPrevented(Exception):
    """Exception raised when query execution is attempted while it's disallowed."""

    pass


# Global flag to control query execution
_local = threading.local()


def should_prevent_queries() -> bool:  # type: ignore[return] # Missing return statement
    getattr(_local, "prevent_queries", False)


@contextmanager
def prevent_queries():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Context manager to prevent SQL executions for all SQLAlchemy engines.
    Use this similarly to an assertion, to ensure that no queries get executed
    in a region where they are not expected. This is mostly useful during development
    but also serves to document the expectation.

    Usage:
    with prevent_queries():
       do_stuff_that_should_not_query()
    """
    # TODO: we should add code that allows query execution (ie does NOT throw an exception)
    # in production. That will make it safer to add this code in more places. For now,
    # we should be extremely sure that code does not query under any circumstances
    # before checking in code that uses this manager. However, it is very useful
    # during development regardless.
    _local.prevent_queries = True

    try:
        yield
    finally:
        _local.prevent_queries = False


@event.listens_for(Engine, "before_execute", retval=True)
def before_execute(conn, clauseelement, multiparams, params):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if should_prevent_queries():
        raise QueryExecutionPrevented(
            "Query execution is prevented within this context."
        )

    return clauseelement, multiparams, params
