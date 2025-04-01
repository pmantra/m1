from __future__ import annotations

import datetime
import enum
import glob
import inspect
import logging
import os
import pathlib
import random
import re
import string
from typing import Any, Callable
from unittest import mock
from unittest.mock import MagicMock, patch

import ddtrace

# This MUST happen before we import any internal modules
# because of numerous import-time side-effects.
import factory
import phonenumbers
import redis
import rq
from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po
from maven import feature_flags
from structlog import testing

import caching
from authn.domain.model import User
from models.tracks import TrackName
from pytests import freezegun

os.environ["DISABLE_TRACING"] = "1"
os.environ["DEV_LOGGING"] = "1"
ddtrace.tracer.enabled = False

import pytest
from _pytest.config import argparsing
from faker import Faker
from faker.providers import phone_number
from flask import current_app
from flask_sqlalchemy import get_state
from sqlalchemy import engine, event
from sqlalchemy.orm import scoped_session

import configuration
from admin.factory import create_admin
from admin.factory import setup_flask_app as create_admin_app
from app import create_app
from eligibility.e9y import model as e9y_model
from glidepath.pytests import helpers as glidepath_helpers
from pytests.compat import *  # noqa: F403,F401
from storage.connection import db as _db
from storage.dev import reset_test_schemas, setup_test_dbs
from tasks import queues
from utils.api_interaction_mixin import APIInteractionMixin
from utils.log import configure, logger
from utils.mock_zendesk import MockZendesk

logging.captureWarnings(True)
logging.getLogger("faker").setLevel(logging.ERROR)
logging.getLogger("storage").setLevel(logging.WARNING)
logging.getLogger("bq_etl").setLevel(logging.WARNING)
logging.getLogger("factory").setLevel(logging.INFO)
logging.getLogger("datadog.dogstatsd").setLevel(logging.CRITICAL)

CUR_DIR = pathlib.Path(__file__).parent.resolve()
DEFAULT = CUR_DIR / "default.db"

Session = scoped_session(
    lambda: get_state(current_app).db.session,
    scopefunc=lambda: get_state(current_app).db.session,
)


class BaseMeta:
    sqlalchemy_session = Session
    sqlalchemy_session_persistence = "flush"


@pytest.fixture(scope="function")
def enterprise_user(factories):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return factories.EnterpriseUserFactory.create()


@pytest.fixture(scope="session")
def api_helpers():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return APIInteractionMixin()


def pytest_configure(config):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    configure(test_worker=os.environ.get("PYTEST_XDIST_WORKER"))
    freezegun.setutc()


def pytest_addoption(parser: argparsing.Parser):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    parser.addoption(
        "--db",
        "-D",
        action="store",
        default="mysql",
        choices=tuple(PytestBackends),
        help="[DEPRECATED] Optionally point the test connection to a specific database backend.",
    )


def pytest_collection_modifyitems(config, items):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    rootdir = pathlib.Path(config.rootdir)
    groups = {}
    for path in rootdir.iterdir():
        if not path.is_dir():
            continue
        if path.stem == "pytests":
            groups["unsorted"] = path
        else:
            groups[path.stem] = path

    for item in items:
        item_path = pathlib.Path(item.fspath).resolve()
        group = next(
            (group for group, path in groups.items() if item_path.is_relative_to(path)),  # type: ignore[attr-defined] # "Path" has no attribute "is_relative_to"
            "unsorted",
        )
        # Group items by root application for distributed testing
        item.add_marker(pytest.mark.xdist_group(name=group))


class PytestBackends(str, enum.Enum):
    SQLITE = "sqlite"
    MYSQL = "mysql"


@pytest.fixture(scope="session")
def backend(request) -> PytestBackends:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    return PytestBackends(request.config.getoption("db"))


def _get_mock_queue():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log = logger("MockQueue")
    q = MagicMock(spec=rq.Queue)
    q.enqueue.side_effect = lambda fn, *args, **kwargs: (
        log.debug(f"'Queue.enqueue' called for {fn.__qualname__!r}: {args}, {kwargs}")
    )
    return q


@pytest.fixture(scope="session")
def mock_queue():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    q = _get_mock_queue()
    mock_queue = dict.fromkeys(queues._queues, q)
    with mock.patch.object(queues, attribute="_queues", new=mock_queue):
        yield q
    q.reset_mock()
    queues._queues = mock_queue


@pytest.fixture(scope="session")
def sync_queue():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log = logger("MockQueue")

    q = _get_mock_queue()

    def sync(fn, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        log.debug(f"'Queue.enqueue' called for {fn.__qualname__!r}: {args}, {kwargs}")
        # remove the rq worker related parameters here to make sure test can pass
        # in real world, this will be popped by the RQ worker logic
        params = inspect.signature(fn).parameters
        kwargs = {k: kwargs[k] for k in params.keys() & kwargs.keys()}
        kwargs.pop("job_timeout", None)
        kwargs.pop("failure_ttl", None)
        kwargs.pop("retry", None)
        kwargs.pop("on_success", None)
        kwargs.pop("on_failure", None)
        kwargs.pop("on_stopped", None)
        kwargs.pop("meta", {})

        return fn(*args, **kwargs)

    q.enqueue.side_effect = sync
    real_queues = queues._queues
    queues._queues = dict.fromkeys(real_queues, q)
    yield q
    q.reset_mock()
    queues._queues = real_queues


@pytest.fixture()
def valid_pharmacy():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return {
        "PharmacyId": "1",
        "StoreName": "Test One Pharmacy",
        "Address1": "90001 1ST ST",
        "Address2": "1ST FL",
        "City": "Washington",
        "State": "DC",
        "ZipCode": "20000",
        "PrimaryPhone": "2025551212",
        "PrimaryPhoneType": "Work",
        "PrimaryFax": "2025551213",
        "PharmacySpecialties": [],
    }


@pytest.fixture(scope="session")
def app(mock_queue, backend, worker_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """An application instance boot-strapped for local testing with sqlite."""

    config = configuration.get_api_config()
    api_dsn = config.common.sqlalchemy.databases.default_url

    db_fixture_strategy = os.getenv("DB_FIXTURE_STRATEGY", "setup")
    if db_fixture_strategy == "setup":
        setup_test_dbs(
            ident=worker_id, default=api_dsn, replica1=api_dsn, app_replica=api_dsn
        )
    elif db_fixture_strategy == "reset":
        reset_test_schemas(
            recreate=True,
            ident=worker_id,
            default=api_dsn,
            replica1=api_dsn,
            app_replica=api_dsn,
        )
    else:
        raise NotImplementedError(
            f"DB_FIXTURE_STRATEGY: {db_fixture_strategy} has not been implemented."
        )

    app = create_app()
    app.testing = True
    app.env = "testing"
    app.config["SERVER_NAME"] = f"test-{worker_id}"
    with patch("utils.cache.RedisLock"):
        yield app


@pytest.fixture(scope="session")
def base_admin_app():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    app = create_admin_app()
    app.testing = True
    app.env = "testing"
    app.template_folder = "templates"
    return app


@pytest.fixture(scope="session")
def admin(base_admin_app, testdb):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    admin = create_admin(base_admin_app)
    return admin


@pytest.fixture(scope="session", autouse=True)
def mock_marshmallow_experiment():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with mock.patch(
        "utils.marshmallow_experiment.marshmallow_experiment_enabled", return_value=True
    ) as mock_experiment:
        yield mock_experiment


@pytest.fixture(scope="function")
def app_context(app):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    with app.app_context():
        yield app


@pytest.fixture(scope="session", autouse=True)
def testdb(app, base_admin_app):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """This pins the transaction state at the test-session level.

    Warnings:
        This should not be used directly!
    """
    yield _db


@pytest.fixture(scope="function")
def db(testdb, app_context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """A db connection object which automatically rolls back any changes."""
    # Get or create an active connection
    connection: engine.Connection = _db.session.connection()
    assert connection is not None, "Failed to connect to the database!"
    # Begin the external transaction which will ensure we don't persist after a test.
    transaction = connection.begin()
    # Create a special scoped session bound only to this connection.
    session = _db.create_scoped_session({"bind": connection})
    bound = session()

    # --------------------------------------------------------------------------
    # IMPORTANT (Glidepath / Do Not Remove):
    # These cached values are leveraged by the glidepath decorators to restore
    # runtime consistent behavior.
    #
    # Their use can be found here:
    # api/glidepath/pytest/helpers.py
    #
    # extended information can be found here:
    # docs/code/glidepath/glidepath.md
    setattr(session, "_commit", session.commit)  # noqa: B010
    setattr(session, "_flush", session.flush)  # noqa: B010

    # overriding the session commit keeps data from being persisted to the db
    # across tests. without it we would be forced to do things like truncate and
    # reseed for each test creating a lot of unnecessary overhead and
    # performance loss.
    session.commit = session.flush
    bound.commit = bound.flush
    # --------------------------------------------------------------------------

    # Create a root savepoint for this test.
    nested = connection.begin_nested()

    # Simulate the expected behavior for rollbacks
    @event.listens_for(_db.session, "after_transaction_end")
    def end_savepoint(s, t):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        nonlocal nested
        if not nested.is_active and not connection.closed:
            nested = connection.begin_nested()

    bind = _db.get_engine(bind="default")
    with mock.patch.object(_db, "session", session):
        with mock.patch("storage.connector.RoutingSession.get_bind", return_value=bind):
            yield _db

    try:
        # Rollback the test transaction
        nested.rollback()
        transaction.rollback()
        transaction.close()
    finally:
        session.remove()


@pytest.fixture(scope="function", autouse=True)
def session(db):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """A session scoped to an individual test run.

    Ensures no changes made within the test are persisted.
    """
    yield db.session


@pytest.fixture(scope="function")
def client(app):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """A test client for communicating with the local test application."""
    with app.test_client() as client:
        with ddtrace.tracer.trace("test_client"):
            yield client


@pytest.fixture
def factories(session):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """Our pre-defined factories module, scoped to the function transaction."""
    from pytests import factories

    return factories


@pytest.fixture
def eligibility_factories(session):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """factories for eligibility related objects."""
    from eligibility.pytests import factories

    return factories


@pytest.fixture
def wallet_factories(session):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """factories for eligibility related objects."""
    from wallet.pytests import factories

    return factories


@pytest.fixture
def default_user(factories):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return factories.DefaultUserFactory.create()


@pytest.fixture
def default_organization(factories):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return factories.OrganizationFactory.create()


@pytest.fixture()
def random_prefix():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return "".join(
        random.choice(string.ascii_uppercase + string.digits) for _ in range(5)
    )


@pytest.fixture(scope="module")
def patch_user_id_encoded_token():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    token = "".join(
        (random.choice(string.ascii_letters + string.digits) for i in range(64))
    )
    with patch("views.schemas.common.security.new_user_id_encoded_token") as p:
        p.return_value = token
        yield


@pytest.fixture
def patch_braze_send_event():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with patch("utils.braze_events.braze.send_event") as p:
        yield p


@pytest.fixture
def mock_zendesk(request):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    mz = MockZendesk()
    mz.add_finalizer = request.addfinalizer
    mz.mock_zendesk()
    return mz


@pytest.fixture(scope="package", autouse=True)
def patch_bq_export():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with patch(
        "bq_etl.pubsub_bq.exporter.export_rows_to_table", autospec=True, spec_set=True
    ) as expm:
        yield expm


@pytest.fixture
def mock_bq_export(patch_bq_export):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    yield patch_bq_export
    patch_bq_export.reset_mock()


@pytest.fixture
def patch_appointment_generate_video_info():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from appointments.models.appointment import Appointment

    with patch.object(Appointment, "generate_video_info") as mock:
        yield mock


@pytest.fixture
def patch_appointment_update_member_cancellations():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from appointments.models.appointment import Appointment

    with patch.object(Appointment, "_update_member_cancellations") as mock:
        yield mock


def escape_ansi(line):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Removes ANSI escape sequences from strings -- useful for testing development logs
    """
    ansi_escape = re.compile(r"(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]")
    return ansi_escape.sub("", line)


@pytest.fixture(scope="function", autouse=True)
def fhir_client_env():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    fake_init_args = ("fake", "fake", "fake", "fake", False)
    with patch("utils.fhir_requests.default_auth", return_value=(None, None)):
        with patch(
            "utils.fhir_requests.FHIRClient.__init__.__defaults__", fake_init_args
        ):
            yield


@pytest.fixture
def patch_e9y_grpc():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with patch("maven_schemas.eligibility_pb2_grpc.EligibilityServiceStub") as p:
        yield p


@pytest.fixture
def patch_pre9y_grpc():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with patch(
        "maven_schemas.eligibility.pre_eligibility_pb2_grpc.PreEligibilityServiceStub"
    ) as p:
        yield p


@pytest.fixture
def e9y_grpc(patch_e9y_grpc):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    stub = patch_e9y_grpc.return_value
    yield stub
    stub.reset_mock()


@pytest.fixture
def pre9y_grpc(patch_pre9y_grpc):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    stub = patch_pre9y_grpc.return_value
    yield stub
    stub.reset_mock()


@pytest.fixture
def mock_e9y_service():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with patch("eligibility.e9y.grpc_service", autospec=True, spec_set=True) as m:
        with patch("eligibility.repository.grpc_service", new=m):
            m.get_sub_population_id_for_user_and_org.return_value = None
            m.get_eligible_features_for_user_and_org.return_value = (
                e9y_model.EligibleFeaturesForUserResponse(
                    features=[],
                    has_population=False,
                )
            )
            m.get_eligible_features_by_sub_population_id = (
                e9y_model.EligibleFeaturesBySubPopulationIdResponse(
                    features=[],
                    has_definition=False,
                )
            )

            # Create a proper verification with real DateRange
            today = datetime.date.today()
            effective_range = e9y_model.DateRange(
                lower=today,
                upper=today + datetime.timedelta(days=365),
                lower_inc=True,
                upper_inc=False,
            )

            # Configure the mock to have get_verification method
            m.get_verification = MagicMock()
            m.get_verification.return_value = e9y_model.EligibilityVerification(
                user_id=1,
                organization_id=1,
                unique_corp_id="",
                dependent_id="",
                first_name="Test",
                last_name="User",
                date_of_birth=today,
                email="test@example.com",
                record={},
                verified_at=datetime.datetime.utcnow(),
                created_at=datetime.datetime.utcnow(),
                verification_type="standard",
                is_active=True,
                effective_range=effective_range,
            )

            yield m


@pytest.fixture(scope="package")
def patch_e9y_service_functions():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with patch(
        "eligibility.e9y.grpc_service.get_sub_population_id_for_user_and_org",
        mock.MagicMock(return_value=None),
    ), patch(
        "eligibility.e9y.grpc_service.get_eligible_features_for_user_and_org",
        mock.MagicMock(
            return_value=(
                e9y_model.EligibleFeaturesForUserResponse(
                    features=[],
                    has_population=False,
                )
            )
        ),
    ), patch(
        "eligibility.e9y.grpc_service.get_eligible_features_by_sub_population_id",
        mock.MagicMock(
            return_value=(
                e9y_model.EligibleFeaturesBySubPopulationIdResponse(
                    features=[],
                    has_definition=False,
                )
            )
        ),
    ):
        yield


@pytest.fixture
def mock_e9y():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with patch("eligibility.e9y", autospec=True, spec_set=True) as m:
        yield m


@pytest.fixture
def mock_enterprise_verification_service():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with patch(
        "eligibility.EnterpriseVerificationService", autospec=True, spec_set=True
    ) as m:
        with patch(
            "eligibility.get_verification_service", autospec=True, spec_set=True
        ) as fm:
            svc = m.return_value
            fm.return_value = svc
            yield svc


@pytest.fixture
def create_state(factories):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    def make_state(name="New York", abbreviation="NY"):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return factories.StateFactory.create(name=name, abbreviation=abbreviation)

    return make_state


@pytest.fixture
def mock_zendesk_module():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with mock.patch("messaging.services.zendesk", autospec=True) as m:
        yield m


@pytest.fixture
def mock_enterprise_zendesk(mock_zendesk_module):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return mock_zendesk_module.EnterpriseValidationZendeskTicket


@pytest.fixture
def mock_redis_lock():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with mock.patch("utils.cache.RedisLock", autospec=True) as m:
        yield m


@pytest.fixture(scope="function")
def mock_redis():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with mock.patch("utils.cache.ResilientRedis") as mock_redis:
        yield mock_redis()


@pytest.fixture(autouse=True)
def mock_redis_client():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with mock.patch("caching.redis.get_redis_client", autospec=True) as m:
        mock_client = mock.MagicMock(autospec=redis.Redis)
        mock_client.get.return_value = None
        m.return_value = mock_client
        yield mock_client


@pytest.fixture()
def mock_redis_ttl_cache():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    mock_cache = mock.MagicMock(autospec=caching.redis.RedisTTLCache)
    mock_cache.get.return_value = None
    return mock_cache


@pytest.fixture
def empty_health_profile():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    return {
        "abortions": None,
        "food_allergies": None,
        "full_term_babies": None,
        "gender": None,
        "sex_at_birth": None,
        "health_issues_current": None,
        "health_issues_past": None,
        "height": None,
        "insurance": None,
        "medications_allergies": None,
        "medications_current": None,
        "medications_past": None,
        "miscarriages": None,
        "number_of_pregnancies": None,
        "premature_babies": None,
        "weight": None,
    }


@pytest.fixture(scope="function")
def risk_flags(session):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    from health.pytests.risk_test_data import create_risk_flags_for_test

    with create_risk_flags_for_test(session) as flags:
        yield flags


@pytest.fixture(scope="session", autouse=True)
def faker():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    fake = Faker()
    Faker.seed(0)
    fake.add_provider(CellPhoneProvider)
    factory.Faker.add_provider(CellPhoneProvider)
    return fake


class CellPhoneProvider(phone_number.Provider):
    formats = (
        "###-###-####",
        "(###) ###-####",
    )

    def cellphone_number(self) -> str:
        return self.phone_number()

    def cellphone_number_with_country_code(self) -> str:
        return f"{self.country_calling_code()} {self.cellphone_number()}"

    def cellphone_number_rfc_3966(self) -> str:
        return phonenumbers.format_number(
            phonenumbers.parse(self.cellphone_number_with_country_code()),
            num_format=phonenumbers.PhoneNumberFormat.RFC3966,
        )

    def cellphone_number_e_164(self) -> str:
        num = self.numerify("+1(###) ###-####")
        return phonenumbers.format_number(
            phonenumbers.parse(num),
            num_format=phonenumbers.PhoneNumberFormat.E164,
        )


@pytest.fixture()
def mock_jwk_client():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with mock.patch("jwt.PyJWKClient") as m:
        yield m


@pytest.fixture()
def mock_decode_jwt():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with mock.patch("jwt.decode") as m:
        yield m


@pytest.fixture
def mock_idp_env():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with mock.patch.dict(
        os.environ, {"AUTH0_DOMAIN": "test-domain", "AUTH0_AUDIENCE": "test-audience"}
    ) as env:
        yield env


@pytest.fixture(scope="function")
def mock_mfa_service():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with mock.patch("authn.domain.service.mfa.MFAService", autospec=True) as m:
        yield m


@pytest.fixture(scope="function")
def mock_idp_management_client():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with mock.patch("authn.services.integrations.idp.ManagementClient") as mock_client:
        yield mock_client()


@pytest.fixture(autouse=True)
def enable_raise_in_primitive_threaded_cached_property():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Enable raising in tests so we provide developers immediate feedback on
    mis-use.
    """
    with mock.patch(
        "utils.primitive_threaded_cached_property.should_raise_on_non_primitive",
        return_value=True,
    ):
        yield


@pytest.fixture
def ff_test_data():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with feature_flags.test_data() as td:
        yield td


# -------------
# Glidepath


@pytest.fixture(autouse=True)
def glidepath_guard_commit_boundary():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Glidepath enforces that no db queries are made during response
    serialization. Additional information, examples, and refactor
    recommendations can be found at:

    docs/code/glidepath/glidepath.md
    """
    enter_hook = mock.patch(
        "glidepath.glidepath.on_enter_guarded_commit_boundary",
        new=glidepath_helpers.glidepath_on_enter_guarded_commit_boundary,
    )
    enter_hook.start()
    exit_hook = mock.patch(
        "glidepath.glidepath.on_exit_guarded_commit_boundary",
        new=glidepath_helpers.glidepath_on_exit_guarded_commit_boundary,
    )
    exit_hook.start()
    obj_eval_hook = mock.patch(
        "glidepath.glidepath.session_object_evaluation",
        new=glidepath_helpers.glidepath_session_object_evaluation,
    )
    obj_eval_hook.start()

    yield

    enter_hook.stop()
    exit_hook.stop()
    obj_eval_hook.stop()


@pytest.fixture(autouse=True)
def glidepath_hook_respond(db):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Glidepath enforces that no db queries are made during response
    serialization. Additional information, examples, and refactor
    recommendations can be found at:

    docs/code/glidepath/glidepath.md
    """
    with mock.patch(
        "glidepath.glidepath.respond",
        glidepath_helpers.glidepath_query_limiter(
            db=db,
            query_limit=1,
        ),
    ):
        yield


@pytest.fixture
def logs():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with testing.capture_logs() as logs:
        yield logs


# -------------


def pytest_sessionstart(session: pytest.Session) -> None:
    """
    Compile and write Babel translations, so they are available for API integration tests
    This is run on every test session start and recreates the .mo files.
    copies the important things from https://github.com/python-babel/babel/blob/8babd2413b6b4eb99304f8f2ae10bbbca4a1fe7d/babel/messages/frontend.py#L199"""

    po_files = glob.glob(
        os.path.join(session.config.rootdir, "**", "*.po"), recursive=True
    )
    for po_file in po_files:
        with open(po_file, "rb") as infile:
            catalog = read_po(infile)
        mo_file = po_file.replace(".po", ".mo")
        with open(mo_file, "wb") as outfile:
            write_mo(outfile, catalog, use_fuzzy=True)


@pytest.fixture
def release_mono_api_localization_on(ff_test_data):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    ff_test_data.update(
        ff_test_data.flag("release-mono-api-localization").variation_for_all(True)
    )


@pytest.fixture
def mock_intro_appointment_flag(ff_test_data: Any) -> Callable[[str], None]:
    def _mock(eligible_tracks: str = "") -> None:
        ff_test_data.update(
            ff_test_data.flag("eligible-tracks-for-ca-intro-appointment").value_for_all(
                eligible_tracks
            )
        )

    return _mock


@pytest.fixture
def create_doula_only_member(factories) -> User:  # type: ignore[no-untyped-def] # Function is missing a type annotation
    client_track = factories.ClientTrackFactory.create(
        track_modifiers="doula_only",
        track=TrackName.PREGNANCY,
    )
    member = factories.EnterpriseUserFactory.create(
        tracks=[],
        member_profile__state=factories.StateFactory.create(
            abbreviation="CA", name="California"
        ),
    )
    tracks = [
        factories.MemberTrackFactory.create(
            name="pregnancy", user=member, client_track=client_track
        )
    ]
    need_categories = [factories.NeedCategoryFactory.create()]
    factories.NeedCategoryTrackFactory.create(
        track_name=tracks[0].name,
        need_category_id=need_categories[0].id,
    )
    return member
