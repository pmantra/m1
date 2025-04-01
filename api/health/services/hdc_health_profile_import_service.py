from __future__ import annotations

import traceback
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

import ddtrace
from maven import feature_flags

from assessments.models.hdc_models import HdcExportItem
from authn.models.user import User
from health.constants import (
    BABY_DOB_LABEL,
    DID_NOT_USE_IUI_IVF,
    DUE_DATE,
    FERTILITY_TREATMENT_STATUS_UPDATE_LABEL,
    FIRST_TIME_MOM_LABEL,
    GLUCOSE_SCREENING_COMPLETION,
    GLUCOSE_SCREENING_RESULT,
    GOT_PREGNANT_OUTSIDE_IUI_IVF_CYCLE,
    LOSS_WHEN,
)
from health.models.risk_enums import ModifiedReason, RiskFlagName
from health.services.hdc_risk_import_service import HdcExportLabels
from health.services.health_profile_service import HealthProfileService
from health.services.hps_export_utils import (
    FERTILITY_TRANSITION_OFFBOARDING_EXPORT_LABEL,
    PREGNANCY_WELCOME_EXPORT_LABEL,
    export_pregnancy_data_to_hps,
    handle_glucose_test_result_export,
)
from health.services.member_risk_service import MemberRiskService
from utils.launchdarkly import user_context
from utils.log import logger

log = logger(__name__)

PREGNANCY_RELATED_LABELS_TO_SEND_TO_HPS = {
    FIRST_TIME_MOM_LABEL,
    DUE_DATE,
    DID_NOT_USE_IUI_IVF,
    GOT_PREGNANT_OUTSIDE_IUI_IVF_CYCLE,
    BABY_DOB_LABEL,
    LOSS_WHEN,
    PREGNANCY_WELCOME_EXPORT_LABEL,
    FERTILITY_TRANSITION_OFFBOARDING_EXPORT_LABEL,
}
PREGNANCY_RELATED_LABELS_NOT_TO_SAVE_IN_HP_MONO = {
    DID_NOT_USE_IUI_IVF,
    GOT_PREGNANT_OUTSIDE_IUI_IVF_CYCLE,
    LOSS_WHEN,
    PREGNANCY_WELCOME_EXPORT_LABEL,
    FERTILITY_TRANSITION_OFFBOARDING_EXPORT_LABEL,
    GLUCOSE_SCREENING_RESULT,
    GLUCOSE_SCREENING_COMPLETION,
}


# Handles HDC-Assessment HealthProfile Exports
class HdcHealthProfileImportService:
    def __init__(self, user: User):
        self.user = user
        self.hp_service = HealthProfileService(user)
        self.mr_service = MemberRiskService(
            user.id,
            commit=False,
            modified_by=user.id,
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
                self._update_health_profile(
                    item.label, item.value, release_pregnancy_updates
                )
                if item.label == HdcExportLabels.DUE_DATE:
                    if feature_flags.bool_variation(
                        "trimester-risk-flag-release",
                        user_context(self.user),
                        default=False,
                    ):
                        # label: 'due_date'; value sample: '2025-07-23 21:08:00+00:00'
                        #
                        # trimester_label is converted to the trimester risk flags
                        # trimester_value is set to None
                        trimester_label = self._calculate_trimester(item.value)
                        log.info(f"trimester label: {trimester_label}")
                        trimester_value = None
                        if trimester_label:
                            self.mr_service.set_risk(trimester_label, trimester_value)
            except Exception as e:
                success = False
                log.error(
                    "Error Handling Health Profile Import",
                    context={"label": item.label, "value": str(item.value)},
                    user_id=self.user.id,
                    error=str(e),
                    error_trace=traceback.format_exc(),
                )

        try:
            self.hp_service.commit()
        except Exception as e:
            success = False
            log.error(
                "Error Handling Health Profile Import.  Commit failed",
                user_id=self.user.id,
                error=str(e),
                error_trace=traceback.format_exc(),
            )
        return success

    def _update_health_profile(
        self, label: str, value: Any, release_pregnancy_updates: bool = False
    ) -> None:
        """Update Health Profile in mono and/or update HPS for label-value pair"""
        if (
            release_pregnancy_updates
            and label in PREGNANCY_RELATED_LABELS_TO_SEND_TO_HPS
        ):
            log.info(
                f"export_pregnancy_related_data _update_health_profile with label: {label} value: {value}"
            )
            export_pregnancy_data_to_hps(self.user, label, value)

        should_export_glucose_results_to_hps = feature_flags.bool_variation(
            "export-glucose-screening-results-to-hps",
            user_context(self.user),
            default=False,
        )

        if should_export_glucose_results_to_hps and (
            label == GLUCOSE_SCREENING_RESULT or label == GLUCOSE_SCREENING_COMPLETION
        ):
            handle_glucose_test_result_export(
                self.user, value, release_pregnancy_updates
            )

        if label == BABY_DOB_LABEL:
            self.hp_service.add_child(value)
        elif label == FIRST_TIME_MOM_LABEL:
            self.hp_service.set_first_time_mom(self._convert_yes_no_to_bool(value))
        elif label == FERTILITY_TREATMENT_STATUS_UPDATE_LABEL:
            self.hp_service.set_fertility_treatment_status(value)
        elif label in PREGNANCY_RELATED_LABELS_NOT_TO_SAVE_IN_HP_MONO:
            # these types of input only need to saved to HPS, not hp in mono
            log.info(
                f"export_pregnancy_related_data skip save to hp with label: {label} value: {value}"
            )
            return
        else:
            self.hp_service.set_json_field(label, value)

    def _convert_yes_no_to_bool(self, value: str) -> bool:
        if value == "yes":
            return True
        elif value == "no":
            return False
        raise Exception("Unable to convert to value to boolean")

    @staticmethod
    @ddtrace.tracer.wrap()
    def _calculate_trimester(due_date: str) -> Optional[RiskFlagName]:
        """
        Calculate the member's pregnancy trimester based on the due date.

        Parameters:
        due_date (str): Expected due date in the format 'YYYY-MM-DD HH:MM:SS+00:00'.

        Returns:
        Optional[str]: Trimester risk flag based on the pregnancy week at onboarding,
                       or None if input is invalid.
        """
        try:
            # Convert due_date string to a datetime object
            due_date_dt = datetime.fromisoformat(due_date)
            log.info(f"due_date_dt: {due_date_dt}")

            # Calculate the start date of pregnancy (280 days pregnancy period, so 280 days before due date)
            pregnancy_start_date = due_date_dt - timedelta(days=280)
            log.info(f"pregnancy_start_date: {pregnancy_start_date}")

            # Calculate today's date
            today = datetime.now(timezone.utc)
            log.info(f"today: {today}")

            # Calculate member pregnancy week
            days_since_start = (today - pregnancy_start_date).days
            log.info(f"days_since_start: {days_since_start}")
            member_pregnancy_week = days_since_start // 7
            log.info(f"member_pregnancy_week: {member_pregnancy_week}")

            # Determine trimester based on member pregnancy week
            if member_pregnancy_week <= 13:
                return RiskFlagName.FIRST_TRIMESTER
            elif 14 <= member_pregnancy_week <= 27:
                return RiskFlagName.SECOND_TRIMESTER
            elif 28 <= member_pregnancy_week <= 33:
                return RiskFlagName.EARLY_THIRD_TRIMESTER
            elif member_pregnancy_week >= 34:
                return RiskFlagName.LATE_THIRD_TRIMESTER
            else:
                return None
        except ValueError:
            return None
