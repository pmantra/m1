import warnings
from itertools import chain

from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.session import SessionTransaction

from storage.connector import RoutingSession, RoutingSQLAlchemy


class testsessionmaker(sessionmaker):
    def __init__(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        bind=None,
        class_=Session,
        autoflush=True,
        autocommit=False,
        expire_on_commit=True,
        info=None,
        **kw,
    ):
        super().__init__(
            bind=bind,
            class_=class_,
            autoflush=autoflush,
            autocommit=autocommit,
            expire_on_commit=expire_on_commit,
            info=info,
            **kw,
        )
        self.db: TestingSQLAlchemy = kw["db"]

    def __call__(self, **local_kw):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not self.db.has_root_transaction:
            return super().__call__(**local_kw)

        engine = local_kw.pop("bind", None) or self.db.get_engine(self.db.get_app())
        return self.db._root_transaction_by_engine[engine.url]["session"]


class TestingSQLAlchemy(RoutingSQLAlchemy):
    """
    via https://github.com/mitsuhiko/flask-sqlalchemy/issues/107
    """

    def __init__(self) -> None:
        super().__init__()
        self._root_transaction_by_engine = {}
        self._root_session_by_bind_key = {}

    @property
    def has_root_transaction(self) -> bool:
        return bool(self._root_transaction_by_engine)

    def from_replica(self, f):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """No-op for testing."""

        return f

    def from_app_replica(self, f):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """No-op for testing."""

        return f

    def create_session(self, options):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return testsessionmaker(class_=RoutingSession, db=self, **options)

    def get_engine(self, app=None, bind=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if bind in {"replica1", "app_replica", None}:
            bind = "default"
        return super().get_engine(app, bind)

    def begin_root_transaction(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.has_root_transaction:
            warnings.warn(  # noqa  B028  TODO:  No explicit stacklevel keyword argument found. The warn method from the warnings module uses a stacklevel of 1 by default. This will only show a stack trace for the line on which the warn method is called. It is therefore recommended to use a stacklevel of 2 or greater to provide more information to the user.
                "Root sessions have already been established!", RuntimeWarning
            )
            self.rollback_root_transaction()

        # Create a root transactions to bind to.
        app = self.get_app()
        for bind_key in chain(app.config["SQLALCHEMY_BINDS"], (None,)):
            engine = self.get_engine(app, bind_key)
            # Check if we're creating a new binding.
            if engine.url not in self._root_transaction_by_engine:
                s = RoutingSession(self, bind=engine)
                cn = engine.connect()
                tn = cn.begin()
                s.begin_nested()

                @event.listens_for(s, "after_transaction_end")
                def restart_savepoint(session, transaction):  # type: ignore[no-untyped-def] # Function is missing a type annotation
                    if transaction.nested and not transaction._parent.nested:
                        # ensure that state is expired the way
                        # session.commit() at the top level normally does
                        # (optional step)
                        session.expire_all()
                        session.begin_nested()

                self._root_transaction_by_engine[engine.url] = dict(
                    connection=cn, transaction=tn, session=s
                )
            # Otherwise, associate the bind key to the existing session for this engine.
            else:
                s = self._root_transaction_by_engine[engine.url]["session"]
            self._root_session_by_bind_key[bind_key] = s

    def rollback_root_transaction(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        while self._root_transaction_by_engine:
            key, root = self._root_transaction_by_engine.popitem()
            session: RoutingSession = root["session"]
            transaction: SessionTransaction = root["transaction"]
            connection: Connection = root["connection"]
            transaction.rollback()
            connection.close()
            session.close()
        self.session.rollback()
        self.session.remove()
        self._root_session_by_bind_key.clear()

    def disable_pooling(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        app = self.get_app()
        app.config["SQLALCHEMY_POOL_SIZE"] = 0

    @property
    def s_replica1(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.has_root_transaction:
            return self._root_session_by_bind_key["replica1"]
        return super().s_replica1

    @property
    def s_app_replica(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.has_root_transaction:
            return self._root_session_by_bind_key["app_replica"]
        return super().s_app_replica
