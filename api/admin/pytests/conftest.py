import os

import ddtrace
import pytest

os.environ["DISABLE_TRACING"] = "1"
os.environ["DEV_LOGGING"] = "1"
ddtrace.tracer.enabled = False


@pytest.fixture
def admin_app(admin):
    with admin.app.app_context():
        yield admin


@pytest.fixture(scope="function")
def mock_request_ctx(admin_app):
    with admin_app.app.test_request_context():
        yield


@pytest.fixture(scope="function")
def commit_expire_behavior(db):
    # https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session.expire_all
    # The Session object’s default behavior is to expire all state
    # whenever the Session.rollback() or Session.commit() methods are called,
    # so that new state can be loaded for the new transaction.
    # Here we include that behavior without persisting data to the db.
    def flush_and_expire():
        db.session.flush()
        db.session.expire_all()
        return

    db.session.commit = flush_and_expire


@pytest.fixture(scope="function", autouse=True)
def admin_session(session, admin_app):
    for view in admin_app._views:
        view.session = session


@pytest.fixture(scope="function")
def admin_client(admin_app):
    """A test client for communicating with the local test application."""
    with admin_app.app.test_client() as client:
        with ddtrace.tracer.trace("test_client"):
            yield client
