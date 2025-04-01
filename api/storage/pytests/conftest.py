import os
from unittest import mock

import flask
import pytest
import sqlalchemy as sa

import app as factory
import configuration
from storage import connector, dev


@pytest.fixture(scope="package")
def app():
    pass


@pytest.fixture(scope="package")
def testdb(app):
    pass


@pytest.fixture(scope="package")
def db(testdb):
    pass


@pytest.fixture(scope="package")
def session(testdb):
    pass


@pytest.fixture(scope="module")
def replica_url():
    url = configuration.construct_dsn(
        **configuration._BASE_DEV_DB_PARAMS, database="test-replica"
    )
    return url


@pytest.fixture(scope="module")
def given_app(replica_url) -> flask.Flask:
    with mock.patch.dict(
        os.environ,
        DEFAULT_REPLICA_URL=str(replica_url),
        REPLICA1_DB_URL=str(replica_url),
    ):
        configuration.refresh_configuration()
        config = configuration.get_api_config()
        api_dsn = config.common.sqlalchemy.databases.default_url
        dev.setup_test_dbs(
            default=api_dsn, replica1=replica_url, app_replica=replica_url
        )
        app_ = factory.create_app()
        app_.testing = True
        app_.env = "testing"
        app_.config["SERVER_NAME"] = f"local-test-{os.uname().nodename}"
        with app_.app_context():
            yield app_


@pytest.fixture(scope="module")
def given_db(given_app) -> connector.RoutingSQLAlchemy:
    db = connector.RoutingSQLAlchemy()
    db.init_app(given_app)
    yield db
    db.session.close_all()
    db.session.remove()


@pytest.fixture(scope="module")
def given_model(given_db):
    class GivenModel(given_db.Model):
        __tablename__ = "test_model"
        id = sa.Column(sa.Integer, primary_key=True)
        col = sa.Column(sa.String(256))

    # Set up the table in the DB
    given_db.drop_all()
    given_db.create_all()
    return GivenModel


@pytest.fixture(scope="module")
def given_table():
    table = sa.Table(
        "test_model",
        sa.MetaData(),
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("col", sa.String(256)),
    )
    return table
