from __future__ import annotations

from typing import Optional

import datadog
import ddtrace
import flask
import structlog.contextvars
from flask_principal import Need, Principal, RoleNeed, UserNeed, identity_loaded
from jinja2 import select_autoescape
from sqlalchemy.orm import joinedload
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

import configuration
from appointments.utils.flask_redis_ext import flask_redis, redis_config
from authn.models.user import User
from authn.routes.saml import add_saml
from common.services import healthchecks, ratelimiting
from common.services.api import create_api
from l10n.config import register_babel
from models.marketing import URLRedirect
from storage import mapper
from storage.connection import db
from utils.log import logger
from utils.requests_stats import get_request_stats
from utils.service_hooks import register_worker_shutdown_hook
from utils.service_owner_mapper import (
    SERVICE_NS_TAG,
    TEAM_NS_TAG,
    inject_tags_info,
    workflow_metadata_list,
)

log = logger(__name__)


class ExceptionLoggedFlaskApp(flask.Flask):
    def log_exception(self, exc_info):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        log.exception("Unhandled application exception", exception=exc_info)
        # maintain existing behavior
        super().log_exception(exc_info)


def create_app(task_instance=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    config = configuration.get_api_config()
    ddtrace.config.trace_headers(config.common.datadog.trace_headers)
    ddtrace.tracer.on_start_span(inject_tags_info)
    datadog.initialize(
        statsd_host=config.common.datadog.stastd_host,
        statsd_port=config.common.datadog.statsd_port,
        # set hostname_from_config suppresses the "No agent or invalid configuration file found" log
        hostname_from_config=False,
    )
    flask_config = configuration.api_config_to_flask_config(config)
    app = ExceptionLoggedFlaskApp(__name__)
    app.config.from_object(flask_config)
    app.jinja_env.autoescape = select_autoescape(default_for_string=True, default=True)

    db.init_app(app)
    mapper.start_mappers()
    flask_redis.init_app(app, **redis_config())
    # register shutdown hook to close db connections
    register_worker_shutdown_hook(app)
    disable_warnings(InsecureRequestWarning)
    register_babel(app)

    if not task_instance:
        Principal(app, use_sessions=False)
        create_api(app)
        healthchecks.init_healthchecks(app, prefix=config.common.healthcheck_prefix)
        add_saml(app)

        @identity_loaded.connect_via(app)
        def on_identity_loaded(sender, identity):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            user: Optional[User] = getattr(flask.g, "current_user", None)

            if user and user.is_authenticated():
                identity.user = user
            else:
                flask.abort(403)

            # Add the UserNeed to the identity
            if hasattr(identity.user, "id"):
                identity.provides.add(UserNeed(identity.user.id))

            user_role_identities = flask.g.get("user_role_identities", [])
            if user_role_identities:
                for role_need, cap_needs in user_role_identities:
                    identity.provides.add(role_need)
                    for cap_need in cap_needs:
                        identity.provides.add(cap_need)
            else:
                roles = []
                # Add the roles and capabilities
                if hasattr(identity.user, "roles"):
                    roles.extend(identity.user.roles)

                for prof in ("practitioner_profile", "member_profile"):
                    profile = getattr(identity.user, prof, None)
                    if profile:
                        roles.append(profile.role)

                for role in roles:
                    role_need = RoleNeed(role.name)
                    identity.provides.add(role_need)
                    needs = []
                    for cap in role.capabilities:
                        need = Need(cap.method, cap.object_type)
                        identity.provides.add(need)
                        needs.append(need)
                    user_role_identities.append((role_need, needs))
                flask.g.user_role_identities = user_role_identities

        @app.before_request
        def before_request() -> None:
            flask.g.request_stat_doc = get_request_stats(flask.request)
            structlog.contextvars.bind_contextvars(**flask.g.request_stat_doc)

            # set service_ns tag
            # if no active_span, we will try another approach later
            active_span = ddtrace.tracer.current_root_span()
            if flask.g.request_stat_doc and active_span:
                key_to_tag_map = {
                    "request.service_ns": SERVICE_NS_TAG,
                    "request.team_ns": TEAM_NS_TAG,
                    "session_id": "session_id",
                    "priority": "priority",
                }
                tags = {}

                for key, tag_name in key_to_tag_map.items():
                    value = flask.g.request_stat_doc.get(key)
                    tags[tag_name] = str(value)

                for workflow in workflow_metadata_list:
                    workflow_value = flask.g.request_stat_doc.get(workflow)
                    tags[workflow] = str(workflow_value)

                active_span.set_tags(tags)

        @app.after_request
        def response_after_request(response: flask.Response):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
            if not hasattr(flask.g, "request_stat_doc"):
                flask.g.request_stat_doc = get_request_stats(flask.request)
                structlog.contextvars.bind_contextvars(**flask.g.request_stat_doc)

            log.debug("api_hit", **{"http.status_code": response.status_code})
            structlog.contextvars.unbind_contextvars(*flask.g.request_stat_doc)
            response = ratelimiting.inject_x_rate_headers(response) or response
            response = inject_cache_headers(response) or response
            response = inject_view_name_header(response) or response
            return response

        @app.route("/Join/<path>", strict_slashes=False)
        @app.route("/join/<path>", strict_slashes=False)
        def join(path):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            result = (
                db.session.query(URLRedirect)
                .options(joinedload(URLRedirect.organization))
                .filter(URLRedirect.path == path, URLRedirect.active.is_(True))
                .one_or_none()
            )
            if result is None:
                # TODO: should there be a default here?
                flask.abort(404)
            return flask.redirect(result.build_redirect_url("https://mavenclinic.com"))

    return app


def inject_cache_headers(response):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    h = response.headers
    h.add("Cache-Control", "no-cache, no-store, must-revalidate")
    h.add("Expires", "Tue, 01 Jan 1980 1:00:00 GMT")
    return response


def inject_view_name_header(response):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    response.headers.add(
        "X-View-Name", flask.g.request_stat_doc.get("request.view_name", "")
    )
    return response
