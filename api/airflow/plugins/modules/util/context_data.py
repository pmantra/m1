from dataclasses import dataclass
from datetime import datetime
from typing import Dict

from pytz import timezone


@dataclass
class DagContextData:
    dag_id: str
    dag_start_date: str
    dag_end_date: str
    log_url: str
    team_ns: str
    service_ns: str


def get_context_data_from_context(context: Dict) -> DagContextData:
    task_instance = context.get("task_instance")
    dag_id = task_instance.dag_id  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "dag_id"
    dag_exec_date = (
        context.get("logical_date")
        if context.get("logical_date")
        else context.get("execution_date")
    )
    dag_start_date = dag_exec_date.astimezone(timezone("US/Eastern")).strftime(  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "astimezone"
        "%Y-%m-%d %I:%M:%S %p EST"
    )
    log_url = context.get("task_instance").log_url  # type: ignore[union-attr] # Item "None" of "Optional[Any]" has no attribute "log_url"
    dag_end_date = (
        datetime.utcnow()
        .astimezone(timezone("US/Eastern"))
        .strftime("%Y-%m-%d %I:%M:%S %p EST")
    )

    return DagContextData(
        dag_id=dag_id,
        dag_start_date=dag_start_date,
        log_url=log_url,
        dag_end_date=dag_end_date,
        team_ns=context["params"]["team_ns"],
        service_ns=context["params"]["service_ns"],
    )
