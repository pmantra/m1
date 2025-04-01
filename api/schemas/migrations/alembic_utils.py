from __future__ import annotations

import pathlib
import threading
from time import monotonic

from alembic.config import Config
from alembic.script import ScriptDirectory

from common import stats
from utils import log

# NOTE: this will be updated according to duration metrics later
DEFAULT_MAX_WAIT_IN_SECONDS = (
    90.0  # default to wait for a maximum of 90 seconds for now
)
DEFAULT_WAKEUP_INTERVAL_IN_SECONDS = 10.0  # default to wake up every 10 seconds

logger = log.logger(__name__)


def get_source_head(db_name: str = "default"):
    migration_folder = pathlib.Path(__file__).parent

    # audit db scenario
    if db_name == "audit":
        conf = Config(ini_section="audit")
        conf.set_section_option("audit", "db_name", "audit")
        conf.set_section_option(
            "audit", "version_locations", str(migration_folder / "audit-versions")
        )
    else:
        conf = Config()

    conf.set_main_option("script_location", str(migration_folder))
    script = ScriptDirectory.from_config(conf)

    return script.get_current_head()


def start_monitoring_loop(
    exiting_event: threading.Event,
    db_name: str,
    source_head: str,
    db_head: str,
    sql_pid: int = 0,
    max_wait_interval_in_seconds: float = DEFAULT_MAX_WAIT_IN_SECONDS,
    wakeup_interval_in_seconds: float = DEFAULT_WAKEUP_INTERVAL_IN_SECONDS,
):
    assert wakeup_interval_in_seconds > 0
    assert wakeup_interval_in_seconds < max_wait_interval_in_seconds

    logger.debug(
        f"Starting the monitoring loop for db {db_name}, source head {source_head}, db head {db_head}"
    )
    start_time = monotonic()
    monitoring_thread = threading.Thread(
        target=_monitoring_loop,
        args=(
            exiting_event,
            start_time,
            db_name,
            source_head,
            sql_pid,
            max_wait_interval_in_seconds,
            wakeup_interval_in_seconds,
        ),
    )
    monitoring_thread.daemon = True
    monitoring_thread.start()
    logger.info(
        f"Started the monitoring loop for db {db_name}, source head {source_head}, db head {db_head}"
    )


def _perform_healing(db_name: str, source_head: str, sql_pid: int):
    from sqlalchemy.engine import create_engine

    import configuration

    # this indicates potential production issues
    # will set up monitors and alerting accordingly
    stats.increment(
        metric_name="mono.migrations.healing",
        pod_name=stats.PodNames.CORE_SERVICES,
        tags=[f"db_name:{db_name}", f"revision:{source_head}"],
    )
    logger.error(
        f"Perform healing on db {db_name} with process id {sql_pid} for source head {source_head}. "
        f"This needs to be manually investigated and mitigated!"
    )

    app_conf = configuration.get_api_config()
    db_url = None
    if (
        app_conf
        and app_conf.common
        and app_conf.common.sqlalchemy
        and app_conf.common.sqlalchemy.databases
    ):
        if db_name == "audit":
            db_url = app_conf.common.sqlalchemy.databases.audit_url  # type: ignore[attr-defined] # "DatabaseConfig" has no attribute "audit_url"
        else:
            db_url = app_conf.common.sqlalchemy.databases.default_url

    if db_url is None or sql_pid <= 0:
        logger.error(
            f"Perform healing validation check failed with db_url {db_url} and sql_pid {sql_pid}, simply quit!"
        )
        return

    engine = create_engine(db_url)
    try:
        with engine.connect() as connection:
            cur_result = connection.execute("SELECT CONNECTION_ID()")
            my_sql_pid = cur_result.fetchall()[0][0]
            logger.warning(
                f"In perform_healing, used sql_pid is {my_sql_pid}, sql_pid to be killed is {sql_pid}"
            )

            # kill the migration SQL process if stuck
            connection.execute(f"KILL {sql_pid}")
    except Exception as e:
        logger.error(
            f"Perform healing on db {db_name} with process id {sql_pid} for source head {source_head} "
            f"throws exception. Exception info: {e}. This needs to be manually investigated and mitigated!"
        )
    finally:
        # proactively dispose the engine and release resources
        engine.dispose()


def _monitoring_loop(
    exiting_event: threading.Event,
    start_time: float,
    db_name: str,
    source_head: str,
    sql_pid: int,
    max_wait_interval_in_seconds: float,
    wakeup_interval_in_seconds: float,
):
    should_perform_healing = True
    elapsed = monotonic() - start_time
    while elapsed < max_wait_interval_in_seconds:
        # add a temp metric for now to monitor a while
        time_tag = "under_20_sec"
        if elapsed >= 60:
            time_tag = "one_min_plus"
        elif elapsed >= 40:
            time_tag = "40_sec_plus"
        elif elapsed >= 20:
            time_tag = "20_sec_plus"

        stats.increment(
            metric_name="mono.migrations.monitoring_wakeup",
            pod_name=stats.PodNames.CORE_SERVICES,
            tags=[f"db_name:{db_name}", f"bucket:{time_tag}"],
        )

        time_remaining = max_wait_interval_in_seconds - elapsed
        wait_time = (
            wakeup_interval_in_seconds
            if wakeup_interval_in_seconds < time_remaining
            else time_remaining
        )

        exiting_event.wait(timeout=wait_time)
        if exiting_event.is_set():
            # migration is done in this case
            should_perform_healing = False
            exiting_event.clear()
            break

        # recalculate elapsed time
        elapsed = monotonic() - start_time

    logger.info(
        f"Exiting the monitoring loop for db {db_name},  source_head {source_head}, "
        f"should_perform_healing flag is {should_perform_healing}, "
        f"running time is {elapsed} seconds"
    )

    # if still not done after max waiting time, kill the migration process and resort to alerting and manual process
    if should_perform_healing and not exiting_event.is_set():
        _perform_healing(db_name=db_name, source_head=source_head, sql_pid=sql_pid)


def get_migration_sql(path: pathlib.Path) -> tuple[str, str]:
    path = path.resolve()
    sql_text = path.read_text()
    up, down = sql_text.split("/* break */")
    return up, down
