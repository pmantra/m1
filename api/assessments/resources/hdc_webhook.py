from __future__ import annotations

import traceback
from datetime import datetime
from typing import Any, List

from flask import Response, request
from httpproblem import Problem
from ldclient import Stage
from maven.feature_flags import migration_variation

from assessments.models.hdc_models import HdcExportEventType, HdcExportItem
from common.services.api import UnauthenticatedResource
from health.utils.constants import MIGRATE_PREGNANCY_DATA_FROM_MONO_TO_HPS
from models.FHIR.condition import Condition, FHIRClinicalStatusEnum
from tasks.fhir import import_hdc_payload_to_fhir
from utils.launchdarkly import user_context
from utils.log import logger
from utils.service_owner_mapper import service_ns_team_mapper
from views.schemas.FHIR.common import (
    FHIR_DATETIME_FORMAT,
    FLAGGED_EXTENSION_URL,
    FHIRVerificationStatusEnum,
)

log = logger(__name__)


class HDCWebhookResource(UnauthenticatedResource):
    # Data is either a HdcExportItem or a list of HdcExportItem
    def post(self) -> Response:
        items = self._extract_items_from_request()

        (pregnancy_migration_stage, _) = migration_variation(
            flag_key=MIGRATE_PREGNANCY_DATA_FROM_MONO_TO_HPS,
            context=user_context(self.user),
            default=Stage.OFF,
        )
        release_pregnancy_updates = pregnancy_migration_stage != Stage.OFF

        success = self._handle_health_profile(items, release_pregnancy_updates)
        success = success & self._handle_risk(items, release_pregnancy_updates)
        success = success & self._handle_fhir(items)
        success = success & self._handle_completion(items)
        if success:
            return "", 200  # type: ignore
        else:
            return "There was a failure handling one or more ExportItems. Check Logs for details", 500  # type: ignore

    def _extract_items_from_request(self) -> List[HdcExportItem]:
        if not self.user:
            message = "HdcWebhook: Invalid User"
            log.error(message, context=request.data)
            raise Problem(400, message)
        log.info(
            "HdcWebhook: received",
            context=request.data,
            user_id=self.user.id,
        )
        try:
            json = request.get_json(force=True)
            # Input can either be a single HdcExportItem or a list of HdcExportItem
            if not isinstance(request.json, list):
                json = [json]  # treat single item as a list
            return [HdcExportItem.from_json(obj) for obj in json]  # type: ignore
        except Exception:
            message = "HdcWebhook: Invalid Data"
            log.error(
                message,
                context=request.data,
                user_id=self.user.id,
            )
            raise Problem(
                400,
                message="HdcWebhook: Invalid Data",
                detail=f"Input: {str(request.data)}",
            )

    def _handle_health_profile(
        self, items: List[HdcExportItem], release_pregnancy_updates: bool = False
    ) -> bool:
        items = [i for i in items if i.event_type == HdcExportEventType.HEALTH_PROFILE]
        from health.services.hdc_health_profile_import_service import (
            HdcHealthProfileImportService,
        )

        service = HdcHealthProfileImportService(self.user)
        return service.import_items(items, release_pregnancy_updates)

    def _handle_risk(
        self, items: List[HdcExportItem], release_pregnancy_updates: bool = False
    ) -> bool:
        items = [i for i in items if i.event_type == HdcExportEventType.RISK_FLAG]
        from health.services.hdc_risk_import_service import HdcRiskImportService

        service = HdcRiskImportService(self.user)
        return service.import_items(items, release_pregnancy_updates)

    def _handle_fhir(self, items: List[HdcExportItem]) -> bool:
        items = [i for i in items if i.event_type == HdcExportEventType.FHIR]
        success = True
        for item in items:

            try:
                handle_fhir(self.user, item.label, item.value)
            except Exception as e:
                success = False
                log.error(
                    "Error Handling FHIR Import",
                    context={"label": item.label, "value": str(item.value)},
                    user_id=self.user.id,
                    error=str(e),
                    error_trace=traceback.format_exc(),
                )
        return success

    def _handle_completion(self, items: List[HdcExportItem]) -> bool:
        items = [
            i for i in items if i.event_type == HdcExportEventType.ASSESSMENT_COMPLETION
        ]
        from assessments.services.hdc_assessment_completion import (
            HdcAssessmentCompletionHandler,
        )

        service = HdcAssessmentCompletionHandler(self.user)
        return service.process_items(items)


def handle_fhir(user, label: str, value: dict) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    """Import FHIR data in `value` to the resource specified in `label`."""
    if label == "Condition":
        data: Condition = _build_condition(user, value, datetime.now())
    else:
        raise ValueError(f"Unknown FHIR resource type {label!r}.")

    service_ns_tag = "health"
    team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
    import_hdc_payload_to_fhir.delay(
        user.id, label, data, service_ns=service_ns_tag, team_ns=team_ns_tag
    )


def _build_condition(user, value: Any, timestamp: datetime) -> Condition:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    return Condition.construct_fhir_condition_json(
        identifiers=[
            ("user", str(user.id)),
        ],
        clinical_status_text=FHIRClinicalStatusEnum.active.value,
        verification_status_text=FHIRVerificationStatusEnum.provisional.value,
        condition_text=value,
        subject=user,
        recorded_date=timestamp.strftime(FHIR_DATETIME_FORMAT),  # type: ignore[arg-type] # Argument "recorded_date" to "construct_fhir_condition_json" of "Condition" has incompatible type "str"; expected "datetime"
        recorder=user,
        extensions=[
            {
                "url": FLAGGED_EXTENSION_URL,
                "extension": [{"url": "flagged", "valueBoolean": True}],
            }
        ],
    )
