import json

from maven import feature_flags

from airflow.utils import logger, with_app_context

log = logger(__name__)


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def get_consolidated_accumulation_file_generation_feature_flag() -> None:
    feature_flag_result = feature_flags.json_variation(
        "release-consolidate-accumulation-file-generation-dag",
        default={},
    )
    log.info(
        f"LaunchDarkly enabled payers for accumulation file generation: {feature_flag_result}"
    )
    with open("/airflow/xcom/return.json", "w") as f:
        json.dump(feature_flag_result, f)
        log.info("Successfully wrote feature flag result to xcom")


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def get_consolidated_accumulation_data_sourcing_feature_flag() -> None:
    feature_flag_result = feature_flags.json_variation(
        "release-consolidate-accumulation-data-sourcing-dag",
        default={},
    )
    log.info(
        f"LaunchDarkly enabled payers for accumulation data sourcing: {feature_flag_result}"
    )
    with open("/airflow/xcom/return.json", "w") as f:
        json.dump(feature_flag_result, f)
        log.info("Successfully wrote feature flag result to xcom")


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def get_consolidated_accumulation_process_responses_feature_flag() -> None:
    feature_flag_result = feature_flags.json_variation(
        "release-consolidate-accumulation-process-responses-dag",
        default={},
    )
    log.info(
        f"LaunchDarkly enabled payers for accumulation process responses: {feature_flag_result}"
    )
    with open("/airflow/xcom/return.json", "w") as f:
        json.dump(feature_flag_result, f)
        log.info("Successfully wrote feature flag result to xcom")


@with_app_context(team_ns="payments_platform", service_ns="payer_accumulation")
def get_consolidated_accumulation_file_transfer_feature_flag() -> None:
    feature_flag_result = feature_flags.json_variation(
        "release-consolidate-accumulation-file-transfer-dag",
        default={},
    )
    log.info(
        f"LaunchDarkly enabled payers for accumulation file transfer: {feature_flag_result}"
    )
    with open("/airflow/xcom/return.json", "w") as f:
        json.dump(feature_flag_result, f)
        log.info("Successfully wrote feature flag result to xcom")
