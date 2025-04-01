from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional, Union

import ddtrace
from attr import dataclass
from ldclient import Stage
from maven import feature_flags
from maven.feature_flags import migration_variation
from sqlalchemy import desc

from authn.models.user import User
from common import stats
from common.health_profile.health_profile_service_client import (
    HealthProfileServiceClient,
)
from common.health_profile.health_profile_service_models import (
    ClinicalStatus,
    ConditionType,
    MemberCondition,
    Modifier,
)
from health.data_models.fertility_treatment_status import FertilityTreatmentStatus
from health.data_models.member_risk_flag import MemberRiskFlag
from health.models.health_profile import HealthProfile
from health.services.risk_service import RiskService
from health.utils.constants import (
    MIGRATE_PREGNANCY_DATA_FROM_MONO_TO_HPS,
    VALID_FERTILITY_STATUS_CODES,
)
from models.tracks.member_track import ChangeReason
from storage.connection import db
from utils.launchdarkly import user_context
from utils.log import logger

log = logger(__name__)


# Code should stop using the HealthProfile Db Model directly.
# And instead use this "Service" class for the logic of retrieving & saving the HealthProfile.
# This way reads/writes can be redirected to the new Health Profile Service as needed.
# And downstream logic can be invoked AFTER DB commits, or API calls complete
# Eventually this class might go away once the Health Profile is fully migrated to the new service,
# at which point code can then directly use HealthProfileServiceClient

FERTILITY_STATUS_TO_RISK_FLAG_NAME: dict[str, str] = {
    "not_ttc_learning": "Not TTC learning - Onboarding status",
    "ttc_in_six_months": "TTC in 6 months - Onboarding status",
    "ttc_no_treatment": "TTC no treatment - Onboarding status",
    "considering_fertility_treatment": "Considering fertility treatment - Onboarding status",
    "undergoing_iui": "Undergoing IUI - Onboarding status",
    "undergoing_ivf": "Undergoing IVF - Onboarding status",
    "ttc_no_iui_ivf": "TTC no IUI no IVF - Onboarding status",
    "successful_pregnancy": "Successful Pregnancy - Onboarding status",
}


class HealthProfileService:
    # Changed fields that consumers care about
    # bool indicates the field whether has changed, not what it's new value is
    @dataclass
    class ChangedFields:
        fertility_treatment_status: bool = False
        prior_c_section: bool = False
        sex_at_birth: bool = False
        children: bool = False

    def __init__(
        self,
        user: User,
        accessing_user: Optional[User] = None,
        change_reason: Optional[ChangeReason] = None,
    ):
        self.user: User = user
        self.user_id: int = user.id
        self.accessing_user: Optional[User] = accessing_user
        self.change_reason = change_reason  # needed by downstream MemberTracks function
        self._health_profile: HealthProfile = self.user.health_profile

        self.changed_fields = HealthProfileService.ChangedFields()

        self._client: Optional[HealthProfileServiceClient] = None

    @property
    def client(self) -> HealthProfileServiceClient:
        if not self._client:
            self._client = HealthProfileServiceClient(self.user, self.accessing_user)
        return self._client

    def _reset_changed_field(self) -> None:
        self.fertility_treatment_status_changed = False

    def commit(self) -> None:
        db.session.add(self._health_profile)  # type: ignore
        db.session.commit()  # type: ignore

        from health.services.health_profile_change_notify_service import (
            HealthProfileChangeNotifyService,
        )

        HealthProfileChangeNotifyService().on_health_profile_saved(self)
        self.changed_fields = HealthProfileService.ChangedFields()

    def set_json_field(self, label: str, value: Any) -> None:
        current_value = self._health_profile.json.get(label)
        if current_value == value:
            return
        self._health_profile.json[label] = value

        if label == "prior_c_section":
            self.changed_fields.prior_c_section = True
        if label == "sex_at_birth":
            self.changed_fields.sex_at_birth = True

    ####
    # Field-Specific get/setters
    # functions below this line should be in alphabetical order to make them easier to visually scan
    ###
    def add_child(
        self, birthday: Union[str, datetime, date], name: Union[str, None] = None
    ) -> None:
        self._health_profile.add_a_child(birthday, name)
        self.changed_fields.children = True

    def add_or_update_child(
        self,
        birthday: Union[str, datetime, date],
        name: Union[str, None] = None,
        child_id: Union[str, None] = None,
    ) -> None:
        self._health_profile.add_or_update_a_child(birthday, name, child_id)
        self.changed_fields.children = True

    def get_fertility_treatment_status(self) -> Union[str, None]:
        mono_status = self._get_fertility_treatment_status_mono()
        hps_status = self._get_fertility_treatment_status_hps()
        if mono_status == hps_status:
            category = "same"
            if not mono_status:
                category = "same_both_null"
        elif mono_status not in VALID_FERTILITY_STATUS_CODES:
            category = "mono_invalid_fertility_status"
        else:
            category = "different"
            if not mono_status:
                category = "different_mono_null"
            if not hps_status:
                category = "different_hps_null"
            log.error(
                "Fertility Status Mismatch",
                context={
                    "user_id": self.user_id,
                    "category": category,
                    "mono_status": mono_status,
                    "hps_status": hps_status,
                },
            )

        stats.increment(
            metric_name="mono.health_profile.fertility.read",
            pod_name=stats.PodNames.MPRACTICE_CORE,
            tags=[
                f"match:{mono_status == hps_status}",
                f"category:{category}",
            ],
        )
        if feature_flags.bool_variation(
            "release-fertility-status-in-m-practice", default=False
        ):
            log.info("Fertility Status: Using HPS Value")
            return hps_status
        log.info("Fertility Status: Using Mono Value")
        return mono_status

    def _get_fertility_treatment_status_mono(self) -> Union[str, None]:
        current_status_record = (
            db.session.query(FertilityTreatmentStatus)
            .filter_by(user_id=self.user_id)
            .order_by(
                desc(FertilityTreatmentStatus.created_at),
                desc(FertilityTreatmentStatus.fertility_treatment_status),
            )
            .first()
        )
        if current_status_record:
            return current_status_record.fertility_treatment_status
        return None

    def _get_fertility_treatment_status_hps(self) -> Union[str, None]:
        # Read from new HealthProfile
        # FF will be used as a kill-switch.  Default on.
        # try/catch around for now.
        hps_status = None
        if feature_flags.bool_variation("hps-migration-fertility-read", default=True):
            try:
                response = self.client.get_fertility_status_history()
                history = response.fertility_status_history
                if history:
                    item = max(history, key=lambda o: o.updated_at)
                    return item.status_code
            except Exception:
                pass
        return hps_status

    def get_prior_c_section(self) -> Union[bool, None]:
        return self._health_profile.json.get("prior_c_section")

    def get_sex_at_birth(self) -> Union[str, None]:
        return self._health_profile.json.get("sex_at_birth")

    def set_fertility_treatment_status(self, value: str) -> None:
        # Save to log table
        new_status = FertilityTreatmentStatus(
            user_id=self.user_id, fertility_treatment_status=value
        )
        db.session.add(new_status)

        if feature_flags.bool_variation(
            "create-risk-flag-based-on-fertility-status",
            user_context(self.user),
            default=False,
        ):
            try:
                new_member_risk_flag_based_on_fertility_status = (
                    self.get_new_member_risk_flag_based_on_fertility_status(
                        new_status.fertility_treatment_status
                    )
                )
                if new_member_risk_flag_based_on_fertility_status:
                    db.session.add(new_member_risk_flag_based_on_fertility_status)
            except Exception as e:
                log.error(
                    f"Could not set risk flag based on fertility status, error: {e}",
                    context={
                        "user_id": self.user_id,
                    },
                )

        db.session.commit()
        self.changed_fields.fertility_treatment_status = True

        # Write to new HealthProfile
        # FF will be used as a kill-switch.  Default on.
        # try/catch around for now.
        # When we transition to HPS being the source-of-truth
        # then the try/except should be removed
        if feature_flags.bool_variation("hps-migration-fertility-write", default=True):
            try:
                self.client.set_fertility_status(value)
            except Exception:
                pass

    def set_first_time_mom(self, value: bool) -> None:
        self._health_profile.first_time_mom = value

    def get_new_member_risk_flag_based_on_fertility_status(
        self, fertility_treatment_status: str
    ) -> Optional[MemberRiskFlag]:
        risk_name = FERTILITY_STATUS_TO_RISK_FLAG_NAME.get(
            fertility_treatment_status, None
        )
        if not risk_name:
            log.info(
                f"get_new_member_risk_flag_based_on_fertility_status returns None because no matching risk name is found for fertility_treatment_status: {fertility_treatment_status}"
            )
            return None

        risk_service = RiskService()
        risk_flag = risk_service.get_by_name(risk_name)
        if not risk_flag:
            log.info(
                f"get_new_member_risk_flag_based_on_fertility_status returns None because no matching risk_flag name is found for risk_name: {risk_name}"
            )
            return None

        now = datetime.now(timezone.utc)
        today = now.date()

        member_risk = MemberRiskFlag(
            user_id=self.user_id, risk_flag=risk_flag, start=today
        )
        log.info(f"member_risk for fertility status created for user: {self.user_id}")

        return member_risk

    @ddtrace.tracer.wrap()
    def update_due_date_in_hps(self, due_date: date | None, modifier: Modifier) -> None:
        if not due_date:
            log.warning(
                f"Due date is missing for user. "
                f"Skipping due date update in HPS for user {self.user_id}."
            )
            return

        (pregnancy_migration_stage, _) = migration_variation(
            flag_key=MIGRATE_PREGNANCY_DATA_FROM_MONO_TO_HPS,
            context=user_context(self.user),
            default=Stage.OFF,
        )
        if pregnancy_migration_stage == Stage.OFF:
            log.info(
                f"Pregnancy migration flag is off. "
                f"Skipping due date update in HPS for user {self.user_id}."
            )
            return

        try:
            existing_pregnancies: list[MemberCondition] = self.client.get_pregnancy(
                user_id=self.user_id, status=ClinicalStatus.ACTIVE.value
            )

            if len(existing_pregnancies) == 1:
                pregnancy_id = existing_pregnancies[0].id
                current_pregnancy = MemberCondition(
                    id=pregnancy_id,
                    user_id=self.user.id,
                    condition_type=ConditionType.PREGNANCY.value,
                    estimated_date=due_date,
                    updated_at=datetime.now(timezone.utc),
                )
                current_pregnancy.modifier = modifier
                pregnancy_and_related_conditions = {
                    "pregnancy": current_pregnancy.to_dict(),
                    "related_conditions": {},
                }
                self.client.patch_pregnancy_and_related_conditions(
                    pregnancy_id, pregnancy_and_related_conditions
                )
            elif len(existing_pregnancies) == 0:
                current_pregnancy = MemberCondition(
                    condition_type=ConditionType.PREGNANCY.value,
                    status=ClinicalStatus.ACTIVE.value,
                    estimated_date=due_date,
                )
                current_pregnancy.modifier = modifier
                self.client.put_pregnancy(current_pregnancy)
            else:
                log.error(
                    f"Found more than one current pregnancy. "
                    f"Skipping due date update in HPS for user {self.user_id}."
                )
                return

            log.info(f"Successfully updated due date in HPS for user {self.user_id}.")
        except Exception as e:
            log.error(
                f"Failed to update due date in HPS for user {self.user_id} due to {e}"
            )
