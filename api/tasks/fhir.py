from requests import HTTPError

from common import stats
from tasks.queues import job
from utils.exceptions import log_exception
from utils.fhir_requests import (
    FHIRClient,
    FHIRClientValueError,
    MonolithFHIRSources,
    OperationOutcomeException,
)
from utils.log import logger
from utils.service_owner_mapper import service_ns_team_mapper

log = logger(__name__)


@job
def import_hdc_payload_to_fhir(user_id: int, resource_name: str, data: dict):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    source = MonolithFHIRSources.ASSESSMENT_WEBHOOK
    log.debug(
        "FHIR HDC import started",
        resource_name=resource_name,
        source=source,
    )

    try:
        service_ns_tag = "health"
        team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
        fhir_export.delay(
            resource_name,
            data=data,
            subject=user_id,
            service_ns=service_ns_tag,
            team_ns=team_ns_tag,
        )
    except Exception as e:
        log_exception(e)
        success = False
    else:
        success = True

    stats.increment(
        metric_name="api.tasks.import_hdc_payload_to_fhir",
        pod_name=stats.PodNames.PERSONALIZED_CARE,
        tags=[
            f"fhir_export_resource:{resource_name.lower()}",
            f"success:{str(success).lower()}",
        ],
    )


@job
def fhir_export(resource_name, data, subject):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.debug(
        "FHIR individual export started", resource_name=resource_name, subject=subject
    )
    try:
        fhir_client = FHIRClient()
    except FHIRClientValueError as e:
        log.error("Failed to create a FHIR Client. Check credentials.", exception=e)
        stats.increment(
            metric_name="api.tasks.fhir_export",
            pod_name=stats.PodNames.PERSONALIZED_CARE,
            tags=[
                f"fhir_export_resource:{resource_name.lower()}",
                "success:false",
                "error:init",
            ],
        )
        return

    resource_client = getattr(fhir_client, resource_name)
    try:
        resource_client.create(data)
    except (OperationOutcomeException, HTTPError) as e:
        log.error(
            "Failed to export json to FHIR store.",
            exception=e,
            target=resource_name,
            subject=subject,
        )
        log_exception(e)
        success = False
    else:
        success = True

    stats.increment(
        metric_name="api.tasks.fhir.fhir_export",
        pod_name=stats.PodNames.PERSONALIZED_CARE,
        tags=[
            f"fhir_export_resource:{resource_name.lower()}",
            f"success:{str(success).lower()}",
        ]
        + ([] if success else ["error:runtime"]),
    )
