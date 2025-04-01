import time
from typing import Optional

import redis.exceptions
import sqlalchemy.engine
from sqlalchemy import create_engine

import configuration
from common import stats
from utils.cache import redis_client
from utils.log import logger

log = logger(__name__)


def ensure_dependency_readiness(max_retry_limit: Optional[int] = None) -> bool:
    """spins forever or to the maximum times passed in until the db is available"""

    # this is our hacky way of getting at the primary db without needing to instantiate
    # a full flask application and initializing RoutingSQLAlchemy with it
    conf = configuration.get_api_config()
    engine: sqlalchemy.engine.Engine = create_engine(
        conf.common.sqlalchemy.databases.default_url,
    )

    db_ok = False
    while not db_ok:
        log.info("Checking if database is ready...")

        try:
            with engine.connect() as conn:
                db_ok = bool(conn.execute("SELECT 1 as ok").scalar())
        except Exception as e:
            db_ok = False
            log.warning(
                "Database is not quite ready, waiting and checking again",
                exc_info=True,
                error=e,
            )

        if not db_ok:
            if max_retry_limit is not None:
                if max_retry_limit > 0:
                    max_retry_limit = max_retry_limit - 1
                    log.info(
                        f"Database is not ready, will retry {max_retry_limit} more times"
                    )
                    stats.increment(
                        metric_name="mono.rq_tasks.worker_probe_retry",
                        pod_name=stats.PodNames.CORE_SERVICES,
                        tags=["probe_failed:false"],
                    )
                else:
                    stats.increment(
                        metric_name="mono.rq_tasks.worker_probe_retry",
                        pod_name=stats.PodNames.CORE_SERVICES,
                        tags=["probe_failed:true"],
                    )
                    log.warning(
                        "Database is not ready after maximum number of retries, quitting"
                    )
                    return False
            time.sleep(1)

        # add non-blocking best-effort check for now
        # redis is a hard dependency for RQ framework and this has not happened in reality
        try:
            default_client = redis_client(decode_responses=True, socket_timeout=5.0)
            default_redis_ok = default_client.ping() if default_client else False
            if not default_redis_ok and default_client:
                log.warning("[readiness_check] default cache is not ready")
        except (OSError, redis.exceptions.RedisError) as default_redis_ex:
            default_redis_ok = False
            log.error(
                f"default cache redis is not quite ready, redis connectivity check exception {default_redis_ex}"
            )

    if max_retry_limit is None:
        # suppress log line for job health probe logic
        log.info(
            f"Database is ready, proceeding with db status {db_ok} and redis status {default_redis_ok}"
        )
    return True
