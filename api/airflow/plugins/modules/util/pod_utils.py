from typing import List, Optional

from kubernetes import (  # type: ignore[attr-defined] # Module "kubernetes" has no attribute "client" #type: ignore[attr-defined] # Module "kubernetes" has no attribute "config"
    client,
    config,
)
from kubernetes.client.models.v1_container import V1Container
from kubernetes.client.models.v1_pod import V1Pod
from kubernetes.client.models.v1_pod_list import V1PodList
from kubernetes.client.models.v1_pod_spec import V1PodSpec
from modules.logger import logger
from modules.util.exceptions import RetrievePodSpecError


def get_pod_spec_and_image_name(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    pod_name_prefix: str,
    pod_namespace: str,
    container_name: str,
    debug_mode: bool = False,
):
    pods = get_pod_spec(pod_name_prefix, pod_namespace)

    if len(pods) > 0:
        pod = pods[0]

        pod_name = pod.metadata.name
        if debug_mode:
            print_pod(pod)

        # The following fields in metadata should not be copied, but determined by KubernetesPodOperator
        pod.metadata.resource_version = None
        pod.metadata.owner_references = None
        pod.metadata.name = None
        pod.metadata.generate_name = None
        pod.metadata.labels = None

        # disable falcon in the pod created by KubernetesPodOperator
        annotations: dict[str, str] = (
            pod.metadata.annotations if pod.metadata.annotations is not None else {}
        )
        annotations["sensor.falcon-system.crowdstrike.com/injection"] = "disabled"
        pod.metadata.annotations = annotations

        # status is the result of the deployment. No need to copy.
        pod.status = None

        # Remove node_name from the source pod spec as the pod created by KubernetesPodOperator
        # may be in a different node. It should be set by KubernetesPodOperator.
        pod.spec.node_name = None

        container = _get_container(pod, pod_name, container_name, debug_mode)
        if container is None:
            raise RetrievePodSpecError(
                f"Unable to get container {container_name} with prefix {pod_name_prefix} in the namespace {pod_namespace}"
            )

        pod.spec.containers = [container]

        return pod, container.image

    raise RetrievePodSpecError(
        f"Unable to find pods with prefix {pod_name_prefix} in the namespace {pod_namespace}"
    )


def get_pod_spec(pod_name_prefix: str, pod_namespace: str) -> List[V1Pod]:
    config.load_config(config_file="/home/airflow/composer_kube_config")

    api_instance = client.CoreV1Api()

    try:
        pods: V1PodList = api_instance.list_namespaced_pod(namespace=pod_namespace)
        return list(
            filter(lambda pod: pod_name_prefix in pod.metadata.name, pods.items)
        )
    except Exception as e:
        logger.error(
            f"Error in get_pod_spec. Type: {e.__class__.__name__}. Message: {str(e)}"
        )
        raise RetrievePodSpecError(
            f"Error in listing pod in the namespace {pod_namespace}"
        )


def print_pod(pod: V1Pod) -> None:
    logger.info(f"Pod Name: {pod.metadata.name}")
    logger.info(f"Namespace: {pod.metadata.namespace}")
    logger.info(f"Status: {pod.status.phase}")

    pod_spec: V1PodSpec = pod.spec
    logger.info("Containers:")
    for container in pod_spec.containers:
        logger.info(f"Container name: {container.name}")
        logger.info(f"Container image: {container.image}")


def _get_container(
    pod: V1Pod, pod_name: str, container_name: str, debug_mode: bool = False
) -> Optional[V1Container]:
    pod_spec: V1PodSpec = pod.spec
    for container in pod_spec.containers:
        if container.name == container_name:
            if debug_mode:
                logger.info(
                    f"ImageName: {container.image}, PodName: {pod_name} PodNamespace: {pod.metadata.namespace}, ContainerName: {container_name}"
                )
            return container

    if debug_mode:
        logger.info(
            f"Image name is unavailable, PodName: {pod_name}, PodNamespace: {pod.metadata.namespace}, ContainerName: {container_name}"
        )
    return None
