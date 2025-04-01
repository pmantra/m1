import functools
from importlib import import_module

from app import create_app
from common import stats
from common.services.api import IMPORTED_MODULES
from tasks.owner_utils import get_pod_name
from utils.constants import CronJobName
from utils.launchdarkly import should_job_run_in_airflow
from utils.log import logger
from utils.service_owner_mapper import (
    SERVICE_NS_TAG,
    TEAM_NS_TAG,
    service_ns_team_mapper,
)

log = logger(__name__)


def with_app_context(team_ns: str = "", service_ns: str = ""):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    all_service_namespaces = set(service_ns_team_mapper.keys())
    all_team_namespaces = set(service_ns_team_mapper.values())

    if team_ns != "" and team_ns not in all_team_namespaces:
        raise NameError(f"team_ns {team_ns} is invalid")

    if service_ns != "" and service_ns not in all_service_namespaces:
        raise NameError(f"service_ns {service_ns} is invalid")

    def decorator(func):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        @functools.wraps(func)
        def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            try:
                for m in IMPORTED_MODULES:
                    import_module(m)

                tags = [
                    f"task_name:{func.__name__}",
                    f"{SERVICE_NS_TAG}:{service_ns}",
                    f"{TEAM_NS_TAG}:{team_ns}",
                ]

                with create_app(task_instance=True).app_context():
                    with stats.timed(
                        metric_name="mono.airflow_tasks.duration",
                        pod_name=get_pod_name(team_ns),  # type: ignore[arg-type] # Argument "pod_name" to "timed" has incompatible type "str"; expected "PodNames"
                        tags=tags,
                    ):
                        func(*args, **kwargs)
            except Exception as e:
                log.warn(f"Error in with_app_context: {e}")
                raise e

        return wrapper

    return decorator


def check_if_run_in_airflow(cron_job_name: CronJobName):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    def decorator(func):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        @functools.wraps(func)
        def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            try:
                # no need to call feature_flag.initialize() explicitly because feature_flag
                # auto initialization is enabled in Airflow
                if should_job_run_in_airflow(cron_job_name):
                    log.info(f"Job {cron_job_name} is going to run in Airflow")
                    func(*args, **kwargs)
                else:
                    log.info(f"Job {cron_job_name} is not going to run in Airflow")
            except Exception as e:
                log.warn(
                    f"Error in check_if_run_in_airflow for job {cron_job_name}: {e}"
                )
                raise e

        return wrapper

    return decorator
