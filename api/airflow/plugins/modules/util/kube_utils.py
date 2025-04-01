import json
import os
import subprocess
from dataclasses import dataclass
from typing import Dict, Optional

from modules.logger import logger

GCP_PROJECTS_TO_ENVIRONMENT_MAP = {
    "maven-clinic-qa1": "qa1",
    "maven-clinic-qa2": "qa2",
    "maven-clinic-staging": "staging",
    "maven-clinic-prod": "production",
}
UNKNOWN_ENVIRONMENT_NAME = "unknown_environment"


@dataclass
class RedisInstanceInfo:
    auth_string: str
    host: str
    port: str
    cert_file_path: str
    read_only_host: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")
    read_only_port: str = None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "None", variable has type "str")


DEFAULT_CACHE_REDIS_SETUP = {
    "maven-clinic-qa1": RedisInstanceInfo(
        auth_string=os.getenv("DEFAULT_CACHE_REDIS_AUTH_STRING", ""),
        host="10.170.1.99",
        port="6378",
        cert_file_path="/mvn-memorystore/default-cache-ca.pem",
    ),
    "maven-clinic-qa2": RedisInstanceInfo(
        auth_string=os.getenv("DEFAULT_CACHE_REDIS_AUTH_STRING", ""),
        host="10.170.1.227",
        port="6378",
        cert_file_path="/mvn-memorystore/default-cache-ca.pem",
    ),
    "maven-clinic-staging": RedisInstanceInfo(
        auth_string=os.getenv("DEFAULT_CACHE_REDIS_AUTH_STRING", ""),
        host="10.170.1.235",
        port="6378",
        cert_file_path="/mvn-memorystore/default-cache-ca.pem",
    ),
    "maven-clinic-prod": RedisInstanceInfo(
        auth_string=os.getenv("DEFAULT_CACHE_REDIS_AUTH_STRING", ""),
        host="172.20.1.100",
        port="6378",
        cert_file_path="/mvn-memorystore/default-cache-ca.pem",
    ),
}


def get_env_vars() -> Dict[str, str]:
    gcp_project = os.environ.get("GCP_PROJECT")
    env_vars = {
        "CLOUD_PROJECT": gcp_project,
        "FEATURE_FLAGS_AUTO_INITIALIZE": "true",
    }

    internal_gateway_ip = os.environ.get("APP_CLUSTER_INTERNAL_GATEWAY_IP")
    if internal_gateway_ip:
        env_vars.update({"INTERNAL_GATEWAY_URL": f"http://{internal_gateway_ip}"})

    env_vars.update(get_default_cache_env_vars(gcp_project))  # type: ignore[arg-type] # Argument 1 to "get_default_cache_env_vars" has incompatible type "Optional[str]"; expected "str"

    return env_vars  # type: ignore[return-value] # Incompatible return value type (got "Dict[str, Optional[str]]", expected "Dict[str, str]")


def get_default_cache_env_vars(gcp_project: str) -> dict:
    redis_instance_info = DEFAULT_CACHE_REDIS_SETUP.get(gcp_project)
    if redis_instance_info:
        env_vars = {
            "DEFAULT_CACHE_REDIS_AUTH_STRING": redis_instance_info.auth_string,
            "DEFAULT_CACHE_REDIS_CERT_FILE_PATH": redis_instance_info.cert_file_path,
            "DEFAULT_CACHE_REDIS_HOST": redis_instance_info.host,
            "DEFAULT_CACHE_REDIS_PORT": redis_instance_info.port,
            "DEFAULT_REDIS_PROXY_HOST": os.environ.get(
                "DEFAULT_REDIS_PROXY_HOST", None
            ),
            "DEFAULT_REDIS_PROXY_PORT": os.environ.get(
                "DEFAULT_REDIS_PROXY_PORT", "6379"
            ),
        }

        if redis_instance_info.read_only_host:
            env_vars[
                "DEFAULT_CACHE_REDIS_READONLY_HOST"
            ] = redis_instance_info.read_only_host
            env_vars[
                "DEFAULT_CACHE_REDIS_READONLY_PORT"
            ] = redis_instance_info.read_only_port
        return env_vars

    return {}


def get_environment_name() -> str:
    gcp_project = os.environ.get("GCP_PROJECT")
    environment_name = UNKNOWN_ENVIRONMENT_NAME
    if gcp_project is not None:
        environment_name = GCP_PROJECTS_TO_ENVIRONMENT_MAP.get(
            gcp_project, UNKNOWN_ENVIRONMENT_NAME
        )
    return environment_name


def get_metadata_labels(image_tag: str) -> Dict[str, str]:
    environment_name = get_environment_name()

    return {
        "app.mvnapp.net/dataclass": "internal",
        "app.mvnapp.net/environment": environment_name,
        "app.mvnapp.net/name": "airflow-mono",
        "app.mvnapp.net/part-of": "maven",
        "app.mvnapp.net/phi": "false",
        "app.mvnapp.net/pii": "false",
        "tags.datadoghq.com/env": environment_name,
        "tags.datadoghq.com/service": "airflow-mono",
        "tags.datadoghq.com/version": image_tag,
    }


def get_image_name() -> Optional[str]:
    try:
        # Run the kubectl command and capture the output
        # if 'api-helm-release' is not found, an error will be thrown
        result = subprocess.run(
            [
                "kubectl",
                "get",
                "helmrelease",
                "api-helm-release",
                "-n",
                "mvn-airflow-job",
                "-o",
                "json",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        # Load the JSON output
        data = json.loads(result.stdout)
        image_tag = (
            data.get("spec", {})
            .get("values", {})
            .get("global", {})
            .get("ci", {})
            .get("imageTag")
        )
        image_name = (
            data.get("spec", {})
            .get("values", {})
            .get("global", {})
            .get("ci", {})
            .get("imageUrl")
        )
        image_url = f"{image_name}:{image_tag}"
        if image_url:
            logger.info(image_url)
            return image_url

        raise RuntimeError(
            "Unable to find image name. Please confirm 'api-helm-release' in 'mvn-airflow-job' namespace is formatted as expected."
        )

    except Exception as e:
        logger.error(f"Error occurred: {e}")
        return None
