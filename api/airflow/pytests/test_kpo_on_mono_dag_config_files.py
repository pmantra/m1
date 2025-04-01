import calendar
import os
import pathlib
from unittest.mock import patch

import croniter
import yaml

from utils.service_owner_mapper import service_ns_team_mapper

CONFIG_FILE_DIR = (
    pathlib.Path(__file__).parent.parent / "configs" / "kpo_on_mono_dag_configs"
)

REQUIRED_FIELDS = {
    "dag_id",
    "task_id",
    "commands",
    "team_namespace",
    "service_namespace",
    "start_year",
    "start_month",
    "start_day",
}

OPTIONAL_FIELDS = {
    "schedule",
    "catchup",
    "task_retries",
    "retry_delay_in_seconds",
    "pod_template_file",
}


def test_command_correctness():
    for file_path in _get_all_config_file():
        with open(file_path, "r") as file:
            yaml_contents = yaml.safe_load(file)
            commands = yaml_contents["commands"]
            assert commands is not None

            assert len(commands) == 3

            with patch(
                "utils.launchdarkly.should_job_run_in_airflow"
            ) as should_job_run_in_airflow:
                should_job_run_in_airflow.return_value = True

                try:
                    exec(commands[2])
                except (ImportError, NameError) as e:
                    raise e
                # Executing the job may throw exceptions in the testing environment,
                # which should be ignored in this test. The scope of this test is for
                # checking the correctness of the command to be executed
                except Exception:
                    pass


def test_config_file_valid_syntax():
    dag_ids = set()

    all_service_namespaces = set(service_ns_team_mapper.keys())
    all_team_namespaces = set(service_ns_team_mapper.values())

    for file_path in _get_all_config_file():
        with open(file_path, "r") as file:
            yaml_contents = yaml.safe_load(file)

            # Check all required fields are set
            for require_field in REQUIRED_FIELDS:
                assert yaml_contents[require_field] is not None

            for field_name in yaml_contents.keys():
                assert field_name in REQUIRED_FIELDS or field_name in OPTIONAL_FIELDS

                # Check if the cron expression is valid
                if field_name == "schedule":
                    assert _is_valid_cron(yaml_contents[field_name])

                # Check if dag_id is unique
                if field_name == "dag_id":
                    assert yaml_contents[field_name] not in dag_ids
                    dag_ids.add(yaml_contents[field_name])

                # Check if the service namespace is valid
                if field_name == "service_namespace":
                    assert yaml_contents[field_name] in all_service_namespaces

                # Check if the team namespace is valid
                if field_name == "team_namespace":
                    assert yaml_contents[field_name] in all_team_namespaces

            # Check if the start date of the DAG is valid
            assert _is_valid_date(
                int(yaml_contents["start_year"]),
                int(yaml_contents["start_month"]),
                int(yaml_contents["start_day"]),
            )


def _is_valid_cron(expression):
    try:
        croniter.croniter(expression)
        return True
    except ValueError:
        return False


def _get_all_config_file():
    yaml_files = []
    for root, _, files in os.walk(CONFIG_FILE_DIR):
        for file in files:
            if file.endswith(".yaml") or file.endswith(".yml"):
                yaml_files.append(os.path.join(root, file))
    return yaml_files


def _is_valid_date(year: int, month: int, day: int):
    try:
        return calendar.monthrange(year, month)[1] >= day
    except ValueError:
        return False
