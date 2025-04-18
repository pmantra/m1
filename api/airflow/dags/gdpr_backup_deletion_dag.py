# Generated by jinja based on the template dag_with_kpo_template.j2.
# Don't modify it unless you know what you are doing.

# mypy: ignore-errors
import os

from modules.util.dag_utils import (
    dag_failure_callback,
    dag_starting_task,
    dag_success_callback,
    kpo_failure_callback,
    kpo_success_callback,
)
from modules.util.kube_utils import get_env_vars, get_image_name, get_metadata_labels
from pendulum import datetime, duration

from airflow import models
from airflow.operators.python import PythonOperator
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator

with models.DAG(
    dag_id="gdpr_backup_deletion_dag",
    params={"team_ns": "core_services", "service_ns": "gdpr_deletion"},
    schedule="0 5 * * *",
    catchup=False,
    start_date=datetime(2024, 3, 31),
    tags=["core_services", "gdpr_deletion", "in_mono"],
    on_success_callback=dag_success_callback,
    on_failure_callback=dag_failure_callback,
) as dag:
    task_id = "gdpr_backup_deletion_job"
    pod_template_file = "/home/airflow/gcs/" + "plugins/mono_api_pod_spec_file.yaml"

    image_name = get_image_name()
    image_tag = image_name.split(":")[1]
    gcp_project = os.environ.get("GCP_PROJECT")

    starting_task = PythonOperator(
        task_id="dag_start", python_callable=dag_starting_task
    )

    kpo_task = KubernetesPodOperator(
        task_id=task_id,
        name=f"mono-for-{task_id}",
        namespace="mvn-airflow-job",
        labels=get_metadata_labels(image_tag),
        image=image_name,
        env_vars=get_env_vars(),
        config_file="/home/airflow/composer_kube_config",
        kubernetes_conn_id="kubernetes_default",
        pod_template_file=pod_template_file,
        is_delete_operator_pod=True,
        startup_timeout_seconds=600,
        log_pod_spec_on_failure=False,
        log_events_on_failure=True,
        cmds=[
            "python3",
            "-c",
            "from airflow.scripts.core_service_team.gdpr_backup_deletion import gdpr_backup_deletion_job; gdpr_backup_deletion_job()",
        ],
        retries=2,
        retry_delay=duration(seconds=300),
        on_success_callback=kpo_success_callback,
        on_failure_callback=kpo_failure_callback,
    )

    starting_task >> kpo_task
