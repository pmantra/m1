from __future__ import annotations

import functools
import inspect
from functools import wraps
from typing import Callable

import ddtrace
import flask
from flask_sqlalchemy import SignallingSession, SQLAlchemy
from sqlalchemy import engine, orm, pool
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.local import LocalStack, release_local

from utils.log import logger

log = logger(__name__)

DEFAULT_BIND_KEY = "default"
APP_REPLICA_BIND_KEY = "app_replica"
REPLICA1_BIND_KEY = "replica1"


class RoutingSession(SignallingSession):
    """Overrides standard binding logic to route to a replica or specific db.

    https://docs.sqlalchemy.org/en/13/orm/persistence_techniques.html#partitioning-strategies-e-g-multiple-database-backends-per-session
    https://techspot.zzzeek.org/2012/01/11/django-style-database-routers-in-sqlalchemy/
    """

    def __init__(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        db: RoutingSQLAlchemy,
        autocommit: bool = False,
        autoflush: bool = True,
        **options,
    ):
        super().__init__(db, autocommit=autocommit, autoflush=autoflush, **options)
        self.db: RoutingSQLAlchemy = db
        self._name: str | None = None

    def get_bind(self, mapper=None, clause=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self._name:
            return self.db.get_engine(bind=self._name)
        if self.db.is_from_olap_replica:
            return self.db.get_engine(bind=REPLICA1_BIND_KEY)
        if self.db.is_from_app_replica:
            # TODO: move this up after being stable
            return self.db.get_engine(bind=APP_REPLICA_BIND_KEY)
        return super().get_bind(mapper, clause)

    def using_bind(self, name: str) -> RoutingSession:
        """Manually route the session to a specific database.
        The default behavior is to re-use exiting sessions. If force_create is specified, it will create a new session.
        """
        session = self.db.session
        if name == REPLICA1_BIND_KEY:
            session = self.db.s_replica1
        elif name == APP_REPLICA_BIND_KEY:
            session = self.db.s_app_replica
        sess = session()
        sess._name = name
        return sess


class RoutingSQLAlchemy(SQLAlchemy):
    """
    via https://github.com/mitsuhiko/flask-sqlalchemy/issues/107
    """

    _from_replica_stack = LocalStack()

    def __init__(self) -> None:
        super().__init__()
        # Override db.Table to use the default bind key
        self.Table = _wrap_make_table(self.Table)  # type: ignore[has-type] # Cannot determine type of "Table"

    @property
    def s_app_replica(self) -> scoped_session:
        return BoundScopedSessionProxy(  # type: ignore[return-value] # Incompatible return value type (got "BoundScopedSessionProxy", expected "scoped_session")
            session=self.session, db=self, bind_key=APP_REPLICA_BIND_KEY
        )

    @property
    def s_replica1(self) -> scoped_session:
        return BoundScopedSessionProxy(  # type: ignore[return-value] # Incompatible return value type (got "BoundScopedSessionProxy", expected "scoped_session")
            session=self.session, db=self, bind_key=REPLICA1_BIND_KEY
        )

    def init_app(self, app: flask.Flask):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        super().init_app(app)

        @app.teardown_appcontext
        def teardown_replica_stack(exc):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            release_local(self._from_replica_stack)
            flask.g.pop("from_replica", False)
            return exc

    def create_session(self, options):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return sessionmaker(class_=RoutingSession, db=self, **options)

    def create_engine(self, sa_url, engine_opts):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # HACK to workaround https://github.com/pallets-eco/flask-sqlalchemy/issues/803
        #   Fixed in 3.0.
        if engine_opts.get("poolclass") is pool.NullPool:
            engine_opts.pop("pool_size")
        return super().create_engine(sa_url, engine_opts)

    def get_engine(
        self, app: flask.Flask | None = None, bind: str = DEFAULT_BIND_KEY
    ) -> engine.Engine:
        return super().get_engine(app=app, bind=bind or DEFAULT_BIND_KEY)

    def from_replica(self, f):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """from_replica will force queries to execute against the replica.

        Note that the replica can still be used when not operating inside a
        from_replica context when using the db.s_replica1 scoped session
        directly.

        Examples:
            >>> from authn.models.user import User
            >>> from storage.connection import db
            >>>
            >>> @db.from_replica
            >>> def my_read_only_function():
            >>>     u = User.query.filter_by(id=123).one()
            >>>     print(f"User ${u.username} is currently in ${u.current_member_track.name}.")
        """

        @wraps(f)
        @ddtrace.tracer.wrap()
        def from_replica_wrapper(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            from_replica = flask.g.get("from_replica", False)
            self._from_replica_stack.push(from_replica)
            flask.g.from_replica = True
            try:
                return f(*args, **kwargs)
            finally:
                from_replica = self._from_replica_stack.pop() or False
                flask.g.from_replica = from_replica

        return from_replica_wrapper

    def from_app_replica(self, f):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """from_app_replica will force queries to execute against the app(OLTP) replica.

        Note that the replica can still be used when not operating inside a
        from_app_replica context when using the db.s_app_relica scoped session
        directly.

        Examples:
            >>> from authn.models.user import User
            >>> from storage.connection import db
            >>>
            >>> @db.from_app_replica
            >>> def my_read_only_function():
            >>>     u = User.query.filter_by(id=123).one()
            >>>     print(f"User ${u.username} is currently in ${u.current_member_track.name}.")
        """

        @wraps(f)
        def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            # keep the legacy replica logic as it is
            from_replica = flask.g.get("from_replica", False)
            self._from_replica_stack.push(from_replica)
            flask.g.from_replica = False
            try:
                if flask.g and hasattr(flask.g, "request_stat_doc"):
                    # refactor later for jobs, extra safety for now
                    # only GET request will be sent to the replica
                    if (
                        "http.method" in flask.g.request_stat_doc
                        and flask.g.request_stat_doc["http.method"] == "GET"
                    ):
                        doc = {"from_app_replica": True}
                        flask.g.request_stat_doc.update(doc)
                return f(*args, **kwargs)
            finally:
                from_replica = self._from_replica_stack.pop() or False
                flask.g.from_replica = from_replica
                if flask.g and hasattr(flask.g, "request_stat_doc"):
                    if (
                        "from_app_replica" in flask.g.request_stat_doc
                        and flask.g.request_stat_doc["from_app_replica"]
                    ):
                        doc = {"from_app_replica": False}
                        flask.g.request_stat_doc.update(doc)

        return wrapper

    @property
    def is_from_app_replica(self) -> bool:
        try:
            if flask.g and hasattr(flask.g, "request_stat_doc"):
                return (
                    # refactor later for jobs, extra safety for now
                    "http.method" in flask.g.request_stat_doc
                    and flask.g.request_stat_doc["http.method"] == "GET"
                    and "from_app_replica" in flask.g.request_stat_doc
                    and flask.g.request_stat_doc["from_app_replica"]
                )
        except Exception as e:
            log.error(f"exception when check is_from_app_replica: {e}")
        return False

    @property
    def is_from_olap_replica(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return flask.g.get("from_replica", False)


def _wrap_make_table(mk_tbl):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    @functools.wraps(mk_tbl)
    def _make_table_wrapper(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        info = kwargs.pop("info", None) or {}
        info.setdefault("bind_key", DEFAULT_BIND_KEY)
        kwargs["info"] = info
        return mk_tbl(*args, **kwargs)

    return _make_table_wrapper


class BoundScopedSessionProxy:
    def __init__(self, session: scoped_session, db: SQLAlchemy, bind_key: str):
        self.scoped = session
        self.db = db
        self.bind_key = bind_key

    def __call__(self, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        sess = self.scoped(*args, **kwargs)
        bind = self.db.get_engine(bind=self.bind_key)
        return BoundSessionProxy(sess, bind)

    def __getattr__(self, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        attr = getattr(self.scoped, name)
        if accepts_bind_param(name):
            bind = self.db.get_engine(bind=self.bind_key)
            wrapped = wrap_with_default_bind(attr, name, bind)
            setattr(self, name, wrapped)
            return wrapped
        return attr


class BoundSessionProxy:
    def __init__(self, session: RoutingSession, bind: engine.Connectable):
        self.session = session
        self.bind = bind

    def __getattr__(self, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        attr = getattr(self.session, name)
        if accepts_bind_param(name):
            wrapped = wrap_with_default_bind(attr, name, self.bind)
            setattr(self, name, wrapped)
            return wrapped
        return attr


def wrap_with_default_bind(func: Callable, name: str, bind: engine.Connectable):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    @functools.wraps(func)
    @ddtrace.tracer.wrap()
    def bind_wrapper(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        final = kwargs.setdefault("bind", bind)
        log.debug(f"Attaching bind {final} to method {name!r} ({func.__qualname__!r})")
        return func(*args, **kwargs)

    return bind_wrapper


@functools.lru_cache(maxsize=None)
def accepts_bind_param(name: str) -> bool:
    if name not in orm.Session.public_methods:
        return False
    method = getattr(orm.Session, name)
    return "bind" in inspect.signature(method).parameters
