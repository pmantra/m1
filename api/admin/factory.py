import json
import warnings

import datadog
import ddtrace
import flask
import rq_dashboard
import structlog.contextvars
from flask import Flask, get_flashed_messages, got_request_exception, session
from flask_admin import Admin
from flask_pagedown import PageDown
from werkzeug.middleware.http_proxy import ProxyMiddleware

import configuration
from admin.blueprints import register_blueprints
from admin.common import ROOT_URL_PREFIX, check_auth, handle_exception
from admin.login import init_login
from admin.views import init_admin
from admin.views.base import AuthenticatedMenuLink
from appointments.utils.flask_redis_ext import flask_redis, redis_config
from authn.resources import admin as authn_admin
from l10n.config import register_babel
from storage.connection import db
from utils.log import logger
from utils.requests_stats import get_request_stats
from utils.service_owner_mapper import SERVICE_NS_TAG, TEAM_NS_TAG

log = logger(__name__)
# -----
# Flask Admin's base model warns us when our views define fields that are then  not
# present in the view's ruleset. This makes sense, but our views inherit from the
# SQLAlchemy model view that automatically defines fields by reflecting on the
# underlying model type. We then define a ruleset that selectively shows or hides
# just the fields we want to. In our case, it's totally fine to ignore fields that
# are missing from the ruleset.
warnings.filterwarnings("ignore", "Fields missing from ruleset", UserWarning)

FLASK_ADMIN_PROXY_TIMEOUT = 90


class RQDashboardLink(AuthenticatedMenuLink):
    read_permission = "read:rq-dashboard"
    delete_permission = "delete:rq-dashboard"
    create_permission = "create:rq-dashboard"
    edit_permission = "edit:rq-dashboard"


def init_rq(admin: Admin):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # default cache migration for RQ use-cases
    _update_rq_dashboard_url(admin.app)
    # rq_dashboard before_first_request setup
    rq_dashboard.web.setup_rq_connection(admin.app)
    # overcome 'before_request' can no longer be called on the blueprint 'rq_dashboard' issue
    # strict check with the latest Flask logic
    if not rq_dashboard.blueprint._got_registered_once:
        rq_dashboard.blueprint.before_request(check_auth)
    admin.app.register_blueprint(
        rq_dashboard.blueprint, url_prefix=f"{ROOT_URL_PREFIX}/rq"
    )
    admin.add_link(
        RQDashboardLink(name="RQ Dashboard", category="Developer", url="/admin/rq")
    )


# https://github.com/pallets/flask/issues/1548#issuecomment-819647349
class DebuggableProxyMiddleware(ProxyMiddleware):
    @property
    def debug(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.app.debug  # type: ignore[attr-defined] # "Callable[[Dict[str, Any], StartResponse], Iterable[bytes]]" has no attribute "debug"


def init_proxies(admin: Admin):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    ALL_HTTP_METHODS = [
        "GET",
        "HEAD",
        "POST",
        "PUT",
        "DELETE",
        "CONNECT",
        "OPTIONS",
        "TRACE",
        "PATCH",
    ]

    targets = {
        "/eligibility-admin/": {"target": "http://eligibility-admin/"},
    }

    # create sub-application for use with proxied routes,
    # so we can check auth via the main app before delegating to the proxy

    # simple placeholder wsgi app for the proxy middleware to wrap.
    # will never be called directly
    def proxy_wsgi_app(environ, start_response):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        start_response("200 OK", [("Content-Type", "application/json")])
        return json.dumps({"status": "OK"})

    proxy_wsgi_app = DebuggableProxyMiddleware(
        proxy_wsgi_app, targets=targets, timeout=FLASK_ADMIN_PROXY_TIMEOUT
    )

    # some repetition here- prevents duplicate view functions from clobbering each other,
    # and ensures that cases for both "/eligibility-admin/"
    # and "/eligilibility-admin/additional/path" are handled
    @admin.app.route(
        "/eligibility-admin/",
        defaults={"remaining_eligibility_path": ""},
        methods=ALL_HTTP_METHODS,
    )
    @admin.app.route(
        "/eligibility-admin/<path:remaining_eligibility_path>", methods=ALL_HTTP_METHODS
    )
    def check_session_before_eligibility_proxy(remaining_eligibility_path):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        check_auth()
        return proxy_wsgi_app


def create_admin(app_: Flask) -> Admin:
    # Add blueprints
    register_blueprints(app_)
    admin = init_admin(app_)
    authn_admin.init_admin(admin)  # adds authn links
    init_rq(admin)  # adds rq dashboard bp and links
    init_proxies(admin)  # instantiates the proxies.

    return admin


def setup_flask_app() -> Flask:
    config = configuration.get_admin_config()
    ddtrace.config.trace_headers(config.common.datadog.trace_headers)
    datadog.initialize(
        statsd_host=config.common.datadog.stastd_host,
        statsd_port=config.common.datadog.statsd_port,
    )
    flask_config = configuration.admin_config_to_flask_config(config)
    app_ = Flask(__name__, template_folder=config.templates.root)

    if config.common.testing:
        flask_config.LOGIN_DISABLED = True

    app_.config.from_object(flask_config)
    # Add exception logger
    got_request_exception.connect(handle_exception, app_)

    # Bootstrap plugins
    db.init_app(app_)
    PageDown(app_)
    init_login(app_)
    flask_redis.init_app(app_, **redis_config())
    register_babel(app_)
    return app_


def create_app() -> Flask:
    # Init & Configure
    app_ = setup_flask_app()
    admin = create_admin(app_)

    # Setting the session to modified will prolong the session as long as the user remains active
    # The session will still expire after they are inactive for PERMANENT_SESSION_LIFETIME
    @app_.before_request
    def before_request():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        session.permanent = True
        session.modified = True

        if "_flashes" in session:
            get_flashed_messages()  # This will consume and clear the messages

        try:
            flask.g.request_stat_doc = get_request_stats(flask.request, "/admin/")
            structlog.contextvars.bind_contextvars(**flask.g.request_stat_doc)

            active_span = (
                ddtrace.tracer.current_root_span()
                or ddtrace.tracer.start_span("admin.request")
            )

            if flask.g.request_stat_doc and active_span:
                active_span.set_tags(
                    {
                        SERVICE_NS_TAG: str(
                            flask.g.request_stat_doc.get("request.service_ns", None)
                        ),
                        TEAM_NS_TAG: str(
                            flask.g.request_stat_doc.get("request.team_ns", None)
                        ),
                    }
                )
        except Exception as e:
            log.warning(f"Unable to setup datadog tag due to: {e}")

    return admin.app


def _update_rq_dashboard_url(app):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    import os

    redis_auth_string = os.environ.get("DEFAULT_CACHE_REDIS_AUTH_STRING", None)
    redis_host = os.environ.get("DEFAULT_CACHE_REDIS_HOST", None)
    redis_port = os.environ.get("DEFAULT_CACHE_REDIS_PORT", "6379")
    redis_cert_file_path = os.environ.get("DEFAULT_CACHE_REDIS_CERT_FILE_PATH", None)
    ssl = True if redis_cert_file_path else False

    if redis_host:
        if ssl:
            redis_url = f"rediss://{redis_host}:{redis_port}/0?password={redis_auth_string}&ssl_ca_certs={redis_cert_file_path}"
        else:
            redis_url = (
                f"redis://{redis_host}:{redis_port}/0?password={redis_auth_string}"
            )
        app.config["RQ_DASHBOARD_REDIS_URL"] = redis_url
        # log.info("RQ dashboard redis URL is updated successfully.")
    else:
        log.warning(
            "RQ dashboard redis URL is not updated due to missing default cache environment settings!"
        )
