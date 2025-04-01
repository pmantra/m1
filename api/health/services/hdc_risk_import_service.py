from __future__ import annotations

import traceback
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, List

from assessments.models.hdc_models import HdcExportItem
from authn.models.user import User
from health.constants import (
    FERTILITY_TREATMENTS,
    PREGNANT_DURING_IUI,
    PREGNANT_DURING_IVF,
)
from health.models.risk_enums import ModifiedReason, RiskFlagName, RiskInputKey
from health.risk_calculators.months_ttc_calculator import (
    MonthsTryingToConceiveCalculator,
)
from health.services.hps_export_utils import export_pregnancy_data_to_hps
from health.services.member_risk_service import MemberRiskService
from storage.connection import db
from utils.log import logger

log = logger(__name__)


@dataclass
class HdcObesityCalcExportValue:
    weight: int | None
    height: int | None

    @staticmethod
    def from_json(input: Any) -> HdcObesityCalcExportValue:
        weight = int(input["weight"]) if input.get("weight") else None
        height = int(input["height"]) if input.get("height") else None
        return HdcObesityCalcExportValue(
            weight=weight,
            height=height,
        )


# Export labels that need special handling
class HdcExportLabels(str, Enum):
    OBESITY_CALC = "obesity_calc"  # we should be able to deprecate this one as it'll happen via the health profile
    DUE_DATE = "due_date"


# Handles HDC Assessment Risk Exports
class HdcRiskImportService:
    def __init__(self, user: User):
        self.user = user
        user_id: int = self.user.id  # type: ignore
        self._service = MemberRiskService(
            user_id,
            commit=False,
            modified_by=user_id,
            modified_reason=ModifiedReason.HDC_ASSESSMENT_IMPORT,
        )

    def import_items(
        self, items: List[HdcExportItem], release_pregnancy_updates: bool = False
    ) -> bool:
        success = True
        if not items:
            return success
        for item in items:
            try:
                self._import_item(item, release_pregnancy_updates)
            except Exception as e:
                success = False
                log.error(
                    "Error Handling Risk Import",
                    context={"label": item.label, "value": str(item.value)},
                    user_id=self.user.id,
                    error=str(e),
                    error_trace=traceback.format_exc(),
                )
        try:
            db.session.commit()  # type: ignore
        except Exception as e:
            success = False
            log.error(
                "Error Handling Risk Import.  Commit failed",
                user_id=self.user.id,
                error=str(e),
                error_trace=traceback.format_exc(),
            )
        return success

    def _import_item(
        self, item: HdcExportItem, release_pregnancy_updates: bool = False
    ) -> None:
        value = item.value
        label = item.label

        # handle pregnancy - send pregnancy related risk data to HPS
        if release_pregnancy_updates and (
            value == PREGNANT_DURING_IUI
            or value == PREGNANT_DURING_IVF
            or label == FERTILITY_TREATMENTS
        ):
            log.info(
                f"export_pregnancy_related_data risks _import_item with label: {label} value: {value}"
            )
            export_pregnancy_data_to_hps(self.user, label, value)

        if label == HdcExportLabels.OBESITY_CALC:
            self._handle_obesity(value)
            return
        if label == RiskFlagName.MONTHS_TRYING_TO_CONCEIVE:
            # Assessment Question is a date picker, we need to convert it to #months from today
            value = self._convert_date_to_months_since(value)
        self._handle_item(label, value)

    def _handle_obesity(self, value: Any):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        value = HdcObesityCalcExportValue.from_json(value)
        self._service.calculate_risks(
            {
                RiskInputKey.WEIGHT_LB: value.weight,
                RiskInputKey.HEIGHT_IN: value.height,
            }
        )

    def _handle_item(self, label: str, value: Any):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            # In most cases HDC will provide a non-numeric string value -- which we can treat as None
            # When value is a number, pass it along to MemberRiskService
            # Numeric value is only useful if RiskFlag.uses_value is set -- but that's MemberRiskService logic
            value = int(value)  # type: ignore
        except Exception:
            value = None
        self._service.set_risk(label, value)

    @staticmethod
    def _convert_date_to_months_since(value: Any) -> Any:
        try:
            # this will round down, ie 0-30/31 days = 0 months
            start = datetime.fromisoformat(value).date()
            return MonthsTryingToConceiveCalculator.convert_date_to_months_since(start)
        except Exception:
            # value is not a date, return it unmodified
            return value
