import contextlib
import copy
import cProfile
import io
import json
import os
import pathlib
import pstats
import re
from pathlib import Path
from typing import Iterable, Union

from flask_sqlalchemy import SQLAlchemy
from pymysql.constants import CLIENT
from sqlalchemy import text
from sqlalchemy.engine import create_engine, url
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Query
from sqlalchemy.sql import ClauseElement
from sqlalchemy.sql.base import Executable
from sqlalchemy.sql.elements import (  # type: ignore[attr-defined] # Module "sqlalchemy.sql.elements" has no attribute "_literal_as_text"
    _literal_as_text,
)

import configuration
from storage.testing import TestingSQLAlchemy
from utils.log import logger

log = logger(__name__)


def setup_dbs():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    print("==========++++++++++ Setting up databases      +++++++++++++++==========")
    flask_config = configuration.api_config_to_flask_config(
        configuration.get_api_config()
    )
    for value in flask_config.SQLALCHEMY_BINDS.values():
        create_db(value, recreate=False)

    print("==========++++++++++ Database setup: Complete! +++++++++++++++==========")


def setup_test_dbs(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    *, ident: str = "name", recreate: bool = False, echo=print, **kwargs: str
) -> None:
    """
    This creates databases with a `test-` prefix from each DSN value in SQLALCHEMY_BINDS
    And binds the new values back to SQLALCHEMY_BINDS for the global app context
    ---
    This also accepts optional kwargs to override the value in SQLALCHEMY_BINDS
    with a custom one. This allows the setup to support custom sqlite databases, for example.
    """

    echo("==========++++++++++ Setting up test databases      ++++++++++==========")
    test_dsns = generate_test_dsns(ident=ident, **kwargs)  # type: ignore[arg-type] # Argument 2 to "generate_test_dsns" has incompatible type "**Dict[str, str]"; expected "URL"
    if recreate:
        for value in test_dsns.values():
            create_db(value, recreate=recreate)
    bind_db_source_names(ident=ident, **test_dsns)
    echo("==========++++++++++ Test database setup: Complete! ++++++++++==========")


def generate_test_dsns(*, ident: str = "main", **kwargs: url.URL) -> dict:
    """
    Returns a dict with keys matching those found in SQLALCHEMY_BINDS
    and URL values for new test database URLs (`test-` prefixed)
    or for any custom URLS passed in through kwargs
    --
    The starting DSN in SQLALCHEMY_BINDS should specify a database name,
    ie 'maven' in: "mysql+pymysql://root:root@mysql/maven"
    to be transformed into 'test-maven'.
    Otherwise this will create a database simply named 'test'
    """
    test_dsns = {}
    config = configuration.get_api_config()
    flask_config = configuration.api_config_to_flask_config(config)
    for key, value in flask_config.SQLALCHEMY_BINDS.items():
        binding = kwargs[key] if key in kwargs else value
        copied: url.URL = copy.deepcopy(binding)
        database_name = f"test-{get_db_num(ident)}"
        if copied.database != "":
            database_name = (
                copied.database
                if copied.database.startswith(database_name)
                else f"{database_name}-{copied.database}"
            )
        copied.database = database_name
        test_dsns[key] = copied

    return test_dsns


def create_db(dsn: url.URL, recreate: bool = False) -> url.URL:
    """
    Uses a valid SqlAlchemy.engine.url.URL object
    to connect to the db and create or ensure existence of a database with the name specified (test-maven).
    This url will need to be able to establish a valid connection
    with a proper username/password and host
    ---
    If "recreate" is set to True, it will drop the database if it exists before creating.
    """

    if "sqlite" in dsn.drivername:
        # For sqlite, the DB file gets automatically created in create_engine
        create_engine(dsn)
    else:
        # Creates a base db connection url from the test DSN
        base_url: url.URL = copy.deepcopy(dsn)
        base_url.database = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
        e = create_engine(
            # pymysql upgrade backward compatibility
            base_url,
            connect_args={
                "binary_prefix": True,
                "client_flag": CLIENT.MULTI_STATEMENTS | CLIENT.FOUND_ROWS,
            },
        )
        e.scalar("select 1;")
        if recreate:
            e.execute(
                text(
                    f"drop database if exists `{dsn.database}`; "
                    f"create database if not exists `{dsn.database}`;"
                )
            )
        else:
            e.execute(text(f"create database if not exists `{dsn.database}`;"))

    return dsn


def bind_db_source_names(*, ident: str = "main", **kwargs: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Binds the kwargs' key / value pairs to the global context of SQLALCHEMY_BINDS
    Each value should be a valid Data Source Name (DSN) like: mysql+pymysql://root:root@mysql/maven
    ---
    A key of 'default' is required.
    """
    assert "default" in kwargs, "A binding for 'default' must be passed in."
    env = {f"{bind}_db_url".upper(): str(value) for bind, value in kwargs.items()}
    redis_db = get_db_num(ident=ident)
    old_url = configuration.get_common_config().redis_url
    new_url = old_url.replace("/0", f"/{redis_db}")
    env["redis_url"] = new_url
    os.environ.update(env)
    configuration.refresh_configuration()


def get_db_num(ident: str) -> int:
    db = 0
    if ident and (match := re.match(r"^.*(?P<num>[0-9]+)$", ident)):
        db = int(match.group("num"))

    return db


def _destroy_schema(database: SQLAlchemy, bind_key: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.warning("Dropping tables for binding %r.", bind_key)
    engine = database.get_engine(database.get_app(), bind_key)

    tables = [
        t[0]
        for t in engine.execute(
            """
            SELECT TABLE_NAME
            FROM information_schema.tables
            WHERE table_schema = DATABASE();
            """
        ).fetchall()
    ]
    log.debug("Tables to be dropped: %r", tables)
    if tables:
        drop_sql = (
            # This is a hail-mary destroy everything.
            # We don't care about data integrity.
            "SET foreign_key_checks = 0; "
            f"DROP TABLE IF EXISTS `{'`,`'.join(tables)}`; "
            "SET foreign_key_checks = 1;"
        )
        engine.execute(drop_sql)

    procedures = [
        t[0]
        for t in engine.execute(
            """
            SELECT routine_name
            FROM information_schema.routines
            WHERE routine_type = 'PROCEDURE'
            AND routine_schema = DATABASE();
            """
        ).fetchall()
    ]
    log.debug("Procedures to be dropped: %r", procedures)
    if procedures:
        drop_sql = " ".join(
            f"DROP PROCEDURE IF EXISTS `{procedure}`;" for procedure in procedures
        )
        engine.execute(drop_sql)

    log.debug("Done.")


def _clear_schema(database: SQLAlchemy, bind_key: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.warning("Clearing tables for binding %r.", bind_key)
    engine = database.get_engine(database.get_app(), bind_key)

    tables = [
        t[0]
        for t in engine.execute(
            """
            SELECT TABLE_NAME
            FROM information_schema.tables
            WHERE table_schema = DATABASE();
            """
        ).fetchall()
    ]
    log.debug("Tables to be cleared: %r", tables)
    if tables:
        stmnt = ";".join(f"TRUNCATE TABLE `{t}`" for t in tables)
        # This is a hail-mary destroy everything.
        # We don't care about data integrity.
        clear_sql = f"SET foreign_key_checks = 0; {stmnt}; SET foreign_key_checks = 1;"
        engine.execute(clear_sql)
    else:
        _init_schema(database, bind_key)
    log.debug("Done.")


def _init_schema(database: SQLAlchemy, bind_key: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info("Creating schema for binding %r.", bind_key)
    schema_name = bind_key
    schemas_dir = Path(__file__).parent.parent.resolve() / "schemas" / "dump"
    schema_file = schemas_dir / f"{schema_name}_schema.sql"
    routines_file = schemas_dir / f"{schema_name}_routines.sql"
    engine = database.get_engine(database.get_app(), bind_key)

    if schema_file.exists():
        init_sql = schema_file.read_text()
        engine.execute(init_sql)
    else:
        log.warning(f"!~~~~~~~ {schema_file} not found. Skipping...")

    if routines_file.exists():
        routines = routines_file.read_text()
        statements = [
            s
            for s in re.split(r"(DELIMITER ;{1,2}|;;)", routines)
            if "sql_mode" not in s
            and s not in {";;", "DELIMITER ;;", "\n", "DELIMITER ;"}
        ]
        for statement in statements:
            engine.execute(statement)


def clear_schemas():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app
    from storage.connection import db

    app = create_app()
    with app.app_context():
        if isinstance(db, TestingSQLAlchemy):
            db.disable_pooling()
        for bind_key in app.config["SQLALCHEMY_BINDS"]:
            _clear_schema(db, bind_key)
        db.session.commit()
        db.session.remove()


def init_schemas(including_replica: bool = False):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app
    from storage.connection import db

    app = create_app()
    with app.app_context():
        if isinstance(db, TestingSQLAlchemy):
            db.disable_pooling()
        for bind_key in app.config["SQLALCHEMY_BINDS"]:
            if "replica" in bind_key and not including_replica:
                continue
            _init_schema(db, bind_key)
        db.session.commit()
        db.session.remove()


def destroy_schemas():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from app import create_app
    from storage.connection import db

    app = create_app()
    with app.app_context():
        if isinstance(db, TestingSQLAlchemy):
            db.disable_pooling()
        for bind_key in app.config["SQLALCHEMY_BINDS"]:
            _destroy_schema(db, bind_key)
        db.session.commit()
        db.session.remove()


def reset_schemas():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    setup_dbs()
    destroy_schemas()
    init_schemas()


def reset_test_schemas(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    *, ident: str = "name", recreate: bool = False, echo=print, **kwargs: str
) -> None:
    setup_test_dbs(ident=ident, recreate=recreate, echo=echo, **kwargs)
    destroy_schemas()
    init_schemas()


class Explain(Executable, ClauseElement):
    """An EXPLAIN/ANALYZE clause."""

    def __init__(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        stmt,
        as_json: bool = False,
        watermark: str = "",
    ):
        self.statement = _literal_as_text(stmt)
        self.as_json: bool = as_json
        # helps with INSERT statements
        self.inline = getattr(stmt, "inline", None)
        # used to identify this query if desired
        # if provided will be prepended to the EXPLAIN query as a comment
        self.watermark = "-- " + watermark + "\n" if watermark else ""


@compiles(Explain)
@compiles(Explain, "mysql")
@compiles(Explain, "mysql+pymysql")
def mysql_explain(element, compiler, **kw):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """A compiler for a MySQL EXPLAIN clause."""
    text = element.watermark + "EXPLAIN "
    if element.as_json:
        text += "FORMAT=JSON "
    text += compiler.process(element.statement, **kw)

    # allow EXPLAIN for INSERT/UPDATE/DELETE, turn off
    # compiler flags that would otherwise start treating this
    # like INSERT/UPDATE/DELETE (gets confused with RETURNING
    # or autocloses cursor which we don't want)
    compiler.isinsert = compiler.isupdate = compiler.isdelete = False

    return text


def analyze(
    database: SQLAlchemy,
    query: Query,
    as_json: bool = False,
    watermark: str = "",
) -> Union[Iterable[dict], dict]:
    """Get an analysis of the Query planner's strategy for your query.

    Examples:

        >>> import json
        >>> from storage.connection import db
        >>> from authn.models.user import User
        >>> plan = analyze(db, db.session.query(User).filter_by(id=1), as_json=True)
        >>> print(json.dumps(plan, indent=2))
        {
          "query_block": {
            "select_id": 1,
            "table": {
              "table_name": "user",
              "access_type": "const",
              "possible_keys": [
                "PRIMARY"
              ],
              "key": "PRIMARY",
              "used_key_parts": [
                "id"
              ],
              "key_length": "4",
              "ref": [
                "const"
              ],
              "rows": 1,
              "filtered": 100
            }
          }
        }

    """
    cursor = database.session.execute(
        Explain(query, as_json=as_json, watermark=watermark)
    )
    if as_json:
        data = cursor.fetchone()[0]
        return json.loads(data)
    return [dict(row.items()) for row in cursor.fetchall()]


@contextlib.contextmanager
def profiled(pct: float = 0.10, fpath: str = None):  # type: ignore[no-untyped-def,assignment] # Function is missing a return type annotation #type: ignore[assignment] # Incompatible default for argument "fpath" (default has type "None", argument has type "str")
    """Execute code within the context of a profiler."""
    pr = cProfile.Profile()
    pr.enable()
    yield
    pr.disable()
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
    ps.print_stats(pct)
    print(s.getvalue())
    if fpath:
        if not fpath.endswith(".pstat") or not fpath.endswith(".prof"):
            fpath = f"{fpath.rsplit('.', maxsplit=1)[0]}.pstat"
        resolved = pathlib.Path(fpath).resolve()
        print(f"\n\nSaving stats to: {resolved}")
        ps.dump_stats(str(fpath))
