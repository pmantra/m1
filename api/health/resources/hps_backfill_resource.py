import dataclasses
from typing import Any, Dict, List, Union

from flask import request

from common.services.api import InternalServiceResource
from health.data_models.fertility_treatment_status import FertilityTreatmentStatus
from storage.connection import db
from utils.log import logger

log = logger(__name__)


# Internal API used by HealthProfile/HealthProfileStorage Service to fetch content needed for backfills
# Creating Single API whose content will be modified over time since these APIs are internal and will only be one/few time usage per data-type
# It'll be less code to keep the Route constant and just modify the implementation


@dataclasses.dataclass
class FertilityTreatmentStatusResult:
    id: int
    user_id: int
    fertility_treatment_status: str
    created_at: str
    modified_at: str


@dataclasses.dataclass
class HealthProfileBackfillResult:
    fertility: Union[None, List[FertilityTreatmentStatusResult]] = None


class HealthProfileBackfillResource(InternalServiceResource):
    def get(self) -> Dict[str, Any]:  # HealthProfileBackfillGetResponse
        log.info("HealthProfileBackfill API received")
        self._check_permissions()
        response = HealthProfileBackfillResult()

        fertility_id = request.args.get("fertility_id", default=-1, type=int)
        process_size = request.args.get("process_size", default=10_000, type=int)
        if fertility_id >= 0 and process_size > 0:
            response.fertility = self.get_fertility(fertility_id, process_size)

        return dataclasses.asdict(response)

    def get_fertility(
        self, last_id: int, process_size: int
    ) -> List[FertilityTreatmentStatusResult]:
        log.info("Getting Fertility History", last_id=last_id)
        db_items: List[FertilityTreatmentStatus] = (
            db.session.query(FertilityTreatmentStatus)
            .filter(FertilityTreatmentStatus.id > last_id)
            .order_by(FertilityTreatmentStatus.id)
            .limit(process_size)
            .all()
        )
        return [
            FertilityTreatmentStatusResult(
                i.id,
                i.user_id,
                i.fertility_treatment_status,
                i.created_at.isoformat(),
                i.modified_at.isoformat(),
            )
            for i in db_items
        ]
