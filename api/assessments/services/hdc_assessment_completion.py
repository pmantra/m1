from __future__ import annotations

import traceback
from datetime import datetime
from typing import List

from assessments.models.hdc_models import HdcExportItem
from authn.models.user import User
from braze import client
from incentives.services.incentive_organization import IncentiveOrganizationService
from tasks.helpers import get_user
from tasks.queues import job
from utils.log import logger
from utils.service_owner_mapper import service_ns_team_mapper

log = logger(__name__)


class HdcAssessmentCompletionHandler:
    # Global Flag to process assesments in background. Some pytests set this to False
    PROCESS_ASYNC: bool = True

    def __init__(self, user: User) -> None:
        self.user = user

    def process_items(self, items: List[HdcExportItem]) -> bool:
        success = True
        for item in items:
            try:
                assessment = item.value["assessments"][0]
                slug = assessment["assessment_slug"]
                date_completed_str = assessment["date_completed"]
                if self.PROCESS_ASYNC:
                    service_ns_tag = "health"
                    team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
                    process_completion.delay(self.user.id, slug, date_completed_str, service_ns=service_ns_tag, team_ns=team_ns_tag)  # type: ignore
                else:
                    self.process_completion(slug, date_completed_str)
            except Exception as e:
                success = False
                log.error(
                    "Error Handling Assessment Completion",
                    context={"value": str(item.value)},
                    user_id=self.user.id,
                    error=str(e),
                    error_trace=traceback.format_exc(),
                )
        return success

    def process_completion(self, slug: str, date_completed_str: str) -> None:
        date_completed = datetime.fromisoformat(date_completed_str)
        self.send_to_braze(slug, date_completed)
        IncentiveOrganizationService().on_assessment_completion(
            self.user.id, slug, date_completed
        )

    def send_to_braze(self, slug: str, date_completed: datetime) -> None:
        user_esp_id = self.user.esp_id
        braze_client = client.BrazeClient()
        resp = braze_client.track_user(
            events=[
                client.BrazeEvent(
                    external_id=user_esp_id,
                    name=f"{slug}-assessment",
                    time=date_completed,
                )
            ]
        )
        if resp and resp.ok:
            log.info(
                "Successfully sent assessment completion event to Braze",
                user_id=self.user.id,
                user_esp_id=user_esp_id,
                assessment_slug=slug,
            )
        else:
            log.error(
                "Failed to send assessment completion event to Braze",
                user_id=self.user.id,
                user_esp_id=user_esp_id,
                assessment_slug=slug,
            )


@job  # type: ignore
def process_completion(user_id: int, slug: str, date_completed_str: str) -> None:
    user = get_user(user_id)
    HdcAssessmentCompletionHandler(user).process_completion(slug, date_completed_str)
