import http

import flask
import redis.exceptions
import sqlalchemy.exc
from flask_restful import Resource

from common import stats
from common.services.api import ExceptionAwareApi
from storage.connection import db
from utils import log
from utils.cache import redis_client

logger = log.logger(__name__)


class ReadinessResource(Resource):
    """Used to determine if a live service is currently ready to receive traffic.

    See Also:
        https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/#define-readiness-probes
    """

    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            with db.session().connection() as conn:
                db_ok = bool(conn.execute("SELECT 1 as ok").first()["ok"])
        except (OSError, sqlalchemy.exc.DatabaseError) as db_ex:
            db_ok = False
            logger.error(f"[readiness_check] db connectivity check exception {db_ex}")

        try:
            default_client = redis_client(decode_responses=True, socket_timeout=5.0)
            default_redis_ok = default_client.ping() if default_client else False
            if not default_redis_ok and default_client:
                logger.warning("[readiness_check] default cache is not ready")
        except (OSError, redis.exceptions.RedisError) as default_redis_ex:
            default_redis_ok = False
            logger.error(
                f"[readiness_check] default cache redis connectivity check exception {default_redis_ex}"
            )
            stats.increment(
                "mono.redis.readiness.failure", pod_name=stats.PodNames.CORE_SERVICES
            )

        # going forward, Redis should be used for caching purposes only
        # Redis connectivity issues should not block API pods to receive traffic
        # ready = (db_ok, redis_ok) == (True, True)
        ready = db_ok
        status = http.HTTPStatus.OK if ready else http.HTTPStatus.SERVICE_UNAVAILABLE
        response = {
            "healthy": ready,
            "status": status,
            "backends": {"mysql": db_ok, "redis": default_redis_ok},
        }
        return response, status


class StartupResource(ReadinessResource):
    """Used to determine if the service is ready to receive traffic on startup.

    See Also:
        https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/#define-startup-probes
    """

    ...


class LivenessResource(Resource):
    """Used to determine if the service is responsive or if it should be restarted.

    See Also:
         https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/#define-a-liveness-http-request
    """

    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return {"healthy": True}, http.HTTPStatus.OK


def add_routes(api):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    api.add_resource(ReadinessResource, "readyz")
    api.add_resource(StartupResource, "startupz")
    api.add_resource(LivenessResource, "livez")
    return api


def init_healthchecks(app: flask.Flask, *, prefix: str = "/"):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    healthcheck_api = ExceptionAwareApi(app, prefix=prefix)
    add_routes(healthcheck_api)
    return healthcheck_api
