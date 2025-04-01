from __future__ import annotations

import builtins
import dataclasses
import functools
import os
import types
import warnings
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional, TypeVar

from maven.data_access.settings import ErrorHandlerSettings
from pymysql.constants import CLIENT
from sqlalchemy.engine import url

from l10n.lazy_string_encoder import JSONEncoderForHTMLAndLazyString


def refresh_configuration() -> None:
    get_api_config.cache_clear()
    get_admin_config.cache_clear()
    get_data_admin_config.cache_clear()
    get_server_config.cache_clear()


@functools.lru_cache(maxsize=1)
def get_server_config(**environ: str) -> ServerConfig:
    """A factory-function for fetching the Server configuration from the environment."""
    environ = environ or get_environ_casefold()
    config = load_config_type(ServerConfig, root="server", **environ)
    return config


@functools.lru_cache(maxsize=1)
def get_idp_config(**environ: str) -> IDPConfig:
    """A factory-function for fetching the IDP configuration from the environment."""
    environ = environ or get_environ_casefold()
    config = load_config_type(IDPConfig, root="auth0", **environ)
    return config


@functools.lru_cache(maxsize=1)
def get_zendesksc_config(**environ: str) -> ZendeskSCConfig:
    """
    A factory-function for fetching the Zendesk Sunshine Conversations
    configuration from the environment.
    """
    environ = environ or get_environ_casefold()
    config = load_config_type(ZendeskSCConfig, root="zendesksc", **environ)
    return config


@functools.lru_cache(maxsize=1)
def get_api_config(**environ: str) -> APIConfig:
    """A factory-function for fetching the Mono API config from the environment."""
    environ = environ or get_environ_casefold()
    common = get_common_config(**environ)
    thumbor = load_config_type(ThumborConfig, root="thumbor", **environ)

    app_config = load_config_type(APIConfig, common=common, thumbor=thumbor, **environ)
    return app_config


@functools.lru_cache(maxsize=1)
def api_config_to_flask_config(api_config: APIConfig) -> FlaskConfig:
    """Represent the APIConfig in a manner which Flask understands."""
    common = common_config_to_flask_config(api_config.common)
    return FlaskConfig(
        ASSET_CONTENT_LENGTH_LIMIT=api_config.asset_content_length_limit,
        ERROR_404_HELP=api_config.error_404_help,
        IMAGE_BUCKET=api_config.image_bucket,
        RESTFUL_JSON=dataclasses.asdict(api_config.restful_json),
        MAX_CONTENT_LENGTH=api_config.max_content_length,
        THUMBOR_URL=api_config.thumbor.url,
        THUMBOR_SECRET_KEY=api_config.thumbor.secret_key,
        **common.__dict__,
    )


@functools.lru_cache(maxsize=1)
def get_admin_config(**environ: str) -> AdminConfig:
    """A factory-function for fetching the Mono Admin config from the environment."""
    environ = environ or get_environ_casefold()
    common = get_common_config(**environ)
    templates = load_config_type(TemplateConfig, root="template", **environ)
    app_config = load_config_type(
        AdminConfig, common=common, templates=templates, **environ
    )
    return app_config


@functools.lru_cache(maxsize=1)
def admin_config_to_flask_config(admin_config: AdminConfig) -> FlaskConfig:
    """Represent the Admin config in a manner which Flask understands."""
    common = common_config_to_flask_config(admin_config.common)
    return FlaskConfig(
        LOGIN_DISABLED=admin_config.login_disabled,
        PERMANENT_SESSION_LIFETIME=admin_config.permanent_session_lifetime,
        PREFERRED_URL_SCHEME=admin_config.preferred_url_scheme,
        # this is for backward compatibility
        RQ_POLL_INTERVAL=admin_config.rq_poll_interval,
        # this is the new config name for poll internal
        RQ_DASHBOARD_POLL_INTERVAL=admin_config.rq_poll_interval,
        # this is the new config name for dashboard redis url
        RQ_DASHBOARD_REDIS_URL=(admin_config.common.redis_url,),
        EXPLAIN_TEMPLATE_LOADING=admin_config.templates.explain_loading,
        TEMPLATE_ROOT=admin_config.templates.root,
        SECRET_KEY=admin_config.secret_key,
        **common.__dict__,
    )


@functools.lru_cache(maxsize=1)
def get_data_admin_config(**environ: str) -> DataAdminConfig:
    """A factory-function for fetching the Mono Data Admin config from the environment."""
    environ = environ or get_environ_casefold()
    common = get_common_config(**environ)
    app_config = load_config_type(DataAdminConfig, common=common, **environ)
    return app_config


@functools.lru_cache(maxsize=1)
def data_admin_config_to_flask_config(
    data_admin_config: DataAdminConfig,
) -> FlaskConfig:
    """Represent the Data Admin config in a manner which Flask understands."""
    common = common_config_to_flask_config(data_admin_config.common)
    return FlaskConfig(
        SECRET_KEY=data_admin_config.secret_key,
        FIXTURE_DIRECTORY=data_admin_config.fixture_directory,
        SESSION_COOKIE_NAME=data_admin_config.session_cookie_name,
        **common.__dict__,
    )


@functools.lru_cache(maxsize=1)
def get_common_config(**environ: str) -> CommonConfig:
    """A factory-function for fetching shared configuration from the environment."""
    environ = environ or get_environ_casefold()
    databases = load_config_type(DatabaseConfig, root="database", **environ)
    sqlalchemy_pool = load_config_type(
        SQLAlchemyPoolConfig, root="sqlalchemy_pool", **environ
    )
    server_config = get_server_config(**environ)
    max_pool_size = sqlalchemy_pool.size + sqlalchemy_pool.max_overflow
    max_concurrent_requests = server_config.request_backlog
    if max_pool_size < max_concurrent_requests:
        warnings.warn(
            f"The max number of connections to the database ({max_pool_size}) "
            f"is less than the max number of concurrent requests ({max_concurrent_requests}). "
            "It is highly recommended to set SQLALCHEMY_POOL_MAX_OVERFLOW to a value "
            "greater than or equal to SERVER_REQUEST_BACKLOG.",
            category=RuntimeWarning,
            stacklevel=3,
        )
    echo = load_bool(environ.get("sqlalchemy_echo"))
    sqlalchemy = SQLAlchemyConfig(databases=databases, pool=sqlalchemy_pool, echo=echo)
    datadog = load_config_type(DataDogConfig)
    common_config = load_config_type(
        CommonConfig, datadog=datadog, sqlalchemy=sqlalchemy, **environ
    )
    return common_config


@functools.lru_cache(maxsize=1)
def common_config_to_flask_config(common_config: CommonConfig) -> FlaskConfig:
    """Represent shared configuration in a manner which Flask understands."""
    return FlaskConfig(
        BASE_URL=common_config.base_url,
        BROKER_URL=common_config.redis_url,
        DEBUG=common_config.debug,
        REDIS_URL=common_config.redis_url,
        SQLALCHEMY_ECHO=common_config.sqlalchemy.echo,
        SQLALCHEMY_DATABASE_URI=common_config.sqlalchemy.databases.default_url,
        SQLALCHEMY_BINDS=dict(
            default=common_config.sqlalchemy.databases.default_url,
            replica1=common_config.sqlalchemy.databases.replica_url,
            # dedicated for OLTP purposes
            app_replica=common_config.sqlalchemy.databases.app_replica_url,
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS=dict(
            pool_timeout=common_config.sqlalchemy.pool.timeout,
            pool_size=common_config.sqlalchemy.pool.size,
            pool_recycle=common_config.sqlalchemy.pool.recycle,
            pool_pre_ping=common_config.sqlalchemy.pool.pre_ping,
            pool_use_lifo=common_config.sqlalchemy.pool.use_lifo,
            max_overflow=common_config.sqlalchemy.pool.max_overflow,
            # pymysql backward compatibility
            connect_args={
                "binary_prefix": True,
                "client_flag": CLIENT.MULTI_STATEMENTS | CLIENT.FOUND_ROWS,
            },
        ),
        TESTING=common_config.testing,
    )


def get_environ_casefold() -> dict[str, str]:
    """Load any local dotenv file if the package is available, then casefold the os.environ."""
    try:
        import dotenv

        dotenv.load_dotenv()
    except ImportError:
        dotenv_file = Path(__file__).resolve().parent / ".env"
        assert (
            not dotenv_file.exists()
        ), "A .env file was provided, but the dotenv package is not installed in this environment."

    return {k.casefold(): v for k, v in os.environ.items()}


def load_config_type(config: type[T], *, root: str = "", **environ: Any) -> T:
    """Load a given config dataclass, enriching parameters from `environ`."""
    environ = environ or get_environ_casefold()
    fields = dataclasses.fields(config)  # type: ignore[arg-type]
    kwargs = {}
    for field, value in iter_environ(*fields, environ=environ, root=root):
        type = (
            getattr(builtins, field.type, None)  # type: ignore[call-overload]
            if isinstance(field.type, str)
            else field.type
        )
        if type is None:
            kwargs[field.name] = value
            continue

        loader = field.metadata.get("loader") or _LOADERS.get(type, type)
        kwargs[field.name] = loader(value)

    return config(**kwargs)


def load_dsn(value: str | url.URL) -> url.URL:
    """Convert a DSN str or URL to URL, ensuring it's appropriately namespaced."""
    return apply_dsn_namespacing(url.make_url(value))  # type: ignore[arg-type,return-value]


def load_bool(value: Any) -> bool:
    """Parse a string value as a boolean."""
    if isinstance(value, str):
        return value in ("1", "yes", "Yes", "YES", "true", "TRUE", "True")
    return bool(value)


_LOADERS = {bool: load_bool}


def iter_environ(
    *fields: dataclasses.Field, environ: dict[str, str], root: str
) -> Iterator[tuple[dataclasses.Field, str]]:
    """Iterate over the key-values in `environ` and yield values which match a field."""
    for field in fields:
        if not field.init:
            continue
        key = field.name.casefold()
        if root:
            key = f"{root}_{field.name}".casefold()
        aliases = {key, *field.metadata.get("aliases", key).casefold().split(",")}

        # Find the first key which is present in the environment, or exit if none.
        #   We don't do anything fancy with ranking keys.
        #   Providing multiple values on intersecting aliases is undefined.
        alias = next(iter(environ.keys() & aliases), None)
        if alias is None:
            continue

        yield field, environ[alias]


T = TypeVar("T")


@dataclasses.dataclass(frozen=True)
class CommonConfig:
    """Shared configuration for all runtimes."""

    sqlalchemy: SQLAlchemyConfig
    datadog: DataDogConfig
    debug: bool = False
    testing: bool = False
    base_url: str = "https://www.mavenclinic.com"
    redis_url: str = "redis://redis:6379/0"
    healthcheck_prefix: str = "/api/"


@dataclasses.dataclass(frozen=True)
class ServerConfig:
    # https://docs.pylonsproject.org/projects/waitress/en/latest/arguments.html
    host: str = "localhost"
    port: int = 8080
    request_backlog: int = 2048
    shutdown_timeout: int = 10
    threads: int = 2048 // 100
    connection_limit: int = 100
    channel_timeout: int = 30
    cleanup_interval: int = 120


@dataclasses.dataclass(frozen=True)
class Auth0ErrorSettings:
    errors = ErrorHandlerSettings(max_retries=4)


@dataclasses.dataclass(frozen=True)
class IDPConfig:
    auth_client_id: str = ""
    auth_client_secret: str = ""
    mgmt_client_id: str = ""
    mgmt_client_secret: str = ""
    web_client_id: str = ""
    web_client_secret: str = ""
    domain: str = ""
    custom_domain: str = ""
    audience: str = ""
    base_connection_id: str = ""
    base_connection_name: str = "Username-Password-Authentication"
    base_url: str = dataclasses.field(default="", metadata={"aliases": "base_url"})
    client_secret_dict: dict = dataclasses.field(default_factory=dict, hash=False)
    errors = Auth0ErrorSettings()

    def __post_init__(self) -> None:
        if not self.client_secret_dict:
            self.client_secret_dict.update(
                {
                    self.auth_client_id: self.auth_client_secret,
                    self.mgmt_client_id: self.mgmt_client_secret,
                    self.web_client_id: self.web_client_secret,
                }
            )


@dataclasses.dataclass(frozen=True)
class APIConfig:
    """API-specific configuration."""

    common: CommonConfig
    thumbor: ThumborConfig
    image_bucket: str = "maven-dev-images"
    restful_json: RestfulJSONConfig = dataclasses.field(
        default_factory=lambda: RestfulJSONConfig()
    )
    max_content_length: int = 50 * 1024 * 1024  # 50MB
    asset_content_length_limit: int = 50 * 1024 * 1024  # 50MB
    error_404_help = False


@dataclasses.dataclass(frozen=True)
class RestfulJSONConfig:
    separators: tuple[str, str] = (",", ":")
    cls: type[JSONEncoderForHTMLAndLazyString] = JSONEncoderForHTMLAndLazyString


@dataclasses.dataclass(frozen=True)
class AdminConfig:
    """Admin-specific configuration."""

    common: CommonConfig
    templates: TemplateConfig
    login_disabled: bool = False
    # 30 minute sessions on the admin application
    permanent_session_lifetime: int = 30 * 60
    # RQ Dashboard
    rq_poll_interval: int = 2500
    # RQ dashboard new config convention
    rq_dashboard_poll_interval: int = 2500
    rq_dashboard_redis_url: tuple = ("redis://redis:6379/0",)
    preferred_url_scheme: str | None = None
    secret_key: str = (
        "\x940\xa2\x00m\xe1\x81\xbf\x16\x80a&"
        "B\xcf6h\x02@\xb5\xfa\xd9\x891\x92\xedc\xb3V"
    )

    def __post_init__(self) -> None:
        if self.preferred_url_scheme is None:
            object.__setattr__(
                self,
                "preferred_url_scheme",
                "http" if self.common.debug or self.common.testing else "https",
            )


@dataclasses.dataclass(frozen=True)
class DataAdminConfig:
    common: CommonConfig
    secret_key: str = "BwJq\xdc`j)%\x90\x11\x00\x1d\xf5\xe2\x13\x87I\xb1jP\xb4\x83\xf6"
    session_cookie_name: str = "session_data_admin"
    fixture_directory: str = "/api/data_admin/fixtures"


@dataclasses.dataclass(frozen=True)
class TemplateConfig:
    explain_loading: bool = dataclasses.field(
        default=False, metadata={"aliases": "explain_template_loading"}
    )
    root: str = "/api/admin/templates"


@dataclasses.dataclass(frozen=True)
class DataDogConfig:
    trace_headers: Iterable[str] = dataclasses.field(
        default_factory=lambda: (
            "User-Agent",
            "X-Request-ID",
            "x-maven-internal",
            "Sentry-Trace",
            "X-Real-IP",
            "Device-Model",
            "Maven-Web-Version",
            "Maven-Web-Date",
        ),
        metadata={"loader": lambda v: (*v.split(","),)},
    )
    stastd_host: str | None = dataclasses.field(
        default=None,
        metadata={"aliases": "dd_agent_host"},
    )
    statsd_port: int = dataclasses.field(
        default=8125,
        metadata={"aliases": "dd_agent_port"},
    )


@dataclasses.dataclass(frozen=True)
class ZendeskSCConfig:
    api_secret_key_primary: str | None = None
    api_secret_key_secondary: str | None = None


@dataclasses.dataclass(frozen=True)
class SQLAlchemyConfig:
    databases: DatabaseConfig = dataclasses.field(repr=False)
    pool: SQLAlchemyPoolConfig
    echo: bool = False


def get_default_pool_overflow() -> int:
    """Get the maximum number of connections the pool may checkout."""
    # Use the request backlog as a proxy for the max concurrency for this process.
    return get_server_config().request_backlog


@dataclasses.dataclass(frozen=True)
class SQLAlchemyPoolConfig:
    """Connection Pooling configuration.

    See Also: https://docs.sqlalchemy.org/en/13/core/pooling.html#setting-pool-recycle
    """

    recycle: int = 30
    """How long a connection may sit un-used in the connection pool."""
    timeout: int = 20
    """How long to wait for a connection from the pool before timing out."""
    max_overflow: int = dataclasses.field(default_factory=get_default_pool_overflow)
    """Max connections the pool may check out over the value provided in `size`."""
    size: int = 20
    """Max active connections to maintain in the pool."""
    pre_ping: bool = True
    """Pre-check connections before checking them out of the pool."""
    use_lifo: bool = True
    """Grab the most-recently-used connection first,
    allowing un-used connections to be invalidated and closed."""


@dataclasses.dataclass(frozen=True)
class ThumborConfig:
    url: str = "https://img-res.mavenclinic.com"
    secret_key: str = "foo"


def default_url_factory() -> str:
    return construct_dsn(**_BASE_DEV_DB_PARAMS, database="maven")  # type: ignore[arg-type,return-value]


_BASE_DEV_DB_PARAMS = {
    "drivername": "mysql+pymysql",
    "username": "root",
    "password": "root",
    "host": "mysql",
    "port": None,
}


@dataclasses.dataclass(frozen=True)
class DatabaseConfig:
    default_url: str = dataclasses.field(
        default_factory=default_url_factory,
        metadata={
            "aliases": "default_db_url",
            "loader": load_dsn,
        },
    )
    # this is mostly for data-eng usage
    replica_url: str = dataclasses.field(
        default_factory=default_url_factory,
        metadata={
            "aliases": "replica1_db_url,default_db_url",
            "loader": load_dsn,
        },
    )
    # this is dedicated for application read replica
    app_replica_url: str = dataclasses.field(
        default_factory=default_url_factory,
        metadata={
            "aliases": "default_replica_url,default_db_url",
            "loader": load_dsn,
        },
    )


def apply_dsn_namespacing(dsn: Optional[url.URL]) -> url.URL | None:
    if dsn:
        dsn.database = apply_app_environment_namespace(dsn.database)
    return dsn


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


def construct_dsn(
    drivername: str,
    username: str,
    password: str,
    host: str,
    port: int | None = None,
    database: str | None = None,
    query: dict | None = None,
) -> url.URL:
    if query is None:
        query = {"charset": "utf8mb4"}
    return url.URL(drivername, username, password, host, port, database, query)


class FlaskConfig(types.SimpleNamespace):
    """Placeholder for env keys."""
