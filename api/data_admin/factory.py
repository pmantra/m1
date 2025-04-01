import sys

import datadog
import ddtrace
import flask
import structlog.contextvars
from flask_admin import Admin

import configuration
from data_admin.common import check_environment
from data_admin.views import MavenDataAdminHomeView
from l10n.config import register_babel
from storage.connection import db
from utils.exceptions import log_exception
from utils.gcp import safe_get_project_id
from utils.log import logger
from utils.requests_stats import get_request_stats
from utils.service_owner_mapper import SERVICE_NS_TAG, TEAM_NS_TAG

log = logger(__name__)


def handle_exception(sender, exception, **extra):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    sender.logger.debug("Got exception during processing: %s", exception)
    log_exception(exception, service="data-admin")


def create_data_admin_app():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    config = configuration.get_data_admin_config()
    ddtrace.config.trace_headers(config.common.datadog.trace_headers)
    datadog.initialize(
        statsd_host=config.common.datadog.stastd_host,
        statsd_port=config.common.datadog.statsd_port,
    )

    # THIS SHUTS DOWN THE APP IF RUNNING IN AN INVALID ENVIRONMENT
    if not check_environment():
        print("DATA ADMIN CANNOT RUN IN THIS ENVIRONMENT")
        sys.exit(1)
    # --

    app_ = flask.Flask(__name__)  # passing in template_folder
    flask_config = configuration.data_admin_config_to_flask_config(config)
    app_.config.from_object(flask_config)
    db.init_app(app_)
    register_babel(app_)

    if safe_get_project_id():
        flask.got_request_exception.connect(handle_exception, app_)

    @app_.before_request
    def before_request():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            flask.g.request_stat_doc = get_request_stats(flask.request, "/data-admin/")
            structlog.contextvars.bind_contextvars(**flask.g.request_stat_doc)

            active_span = (
                ddtrace.tracer.current_root_span()
                or ddtrace.tracer.start_span("data-admin.request")
            )

            if flask.g.request_stat_doc and active_span:
                active_span.set_tags(
                    {
                        SERVICE_NS_TAG: "data-admin",
                        TEAM_NS_TAG: str(
                            flask.g.request_stat_doc.get("request.team_ns", None)
                        ),
                    }
                )
        except Exception as e:
            log.warning(f"Unable to setup datadog tags due to: {e}")

    admin = Admin(
        app_,
        index_view=MavenDataAdminHomeView(url="/data-admin", endpoint="data-admin"),
        name="Maven Data Admin",
        template_mode="bootstrap3",
    )

    return admin.app
