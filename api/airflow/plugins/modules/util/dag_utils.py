from typing import Dict

from modules.logger import logger
from modules.util.context_data import DagContextData, get_context_data_from_context
from modules.util.kube_utils import get_environment_name


def dag_starting_task(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    **contexts,
) -> None:
    logger.info(
        f"Starting dag. dag_id={contexts['dag'].dag_id}, team_ns={contexts['params']['team_ns']}, service_ns={contexts['params']['service_ns']}"
    )


def kpo_success_callback(contexts: Dict) -> None:
    logger.info(
        f"Task Success. dag_id={contexts['dag'].dag_id}, team_ns={contexts['params']['team_ns']}, service_ns={contexts['params']['service_ns']}"
    )


def kpo_failure_callback(contexts: Dict) -> None:
    logger.info(
        f"Task Failure. dag_id={contexts['dag'].dag_id}, team_ns={contexts['params']['team_ns']}, service_ns={contexts['params']['service_ns']}"
    )


def dag_success_callback(contexts: Dict) -> None:
    dag_context_data = get_context_data_from_context(contexts)
    logger.info(
        f"Successful DAG. {_generate_logs_from_dag_context_data(dag_context_data)}"
    )


def dag_failure_callback(contexts: Dict) -> None:
    dag_context_data = get_context_data_from_context(contexts)
    logger.info(f"Failed DAG. {_generate_logs_from_dag_context_data(dag_context_data)}")


def _generate_logs_from_dag_context_data(dag_context_data: DagContextData) -> str:
    return f"env={get_environment_name()}, job_name={dag_context_data.dag_id}, dag_start_time={dag_context_data.dag_start_date}, dag_end_time={dag_context_data.dag_end_date}, team_ns={dag_context_data.team_ns}, service_ns={dag_context_data.service_ns}, log_url={dag_context_data.log_url}"
