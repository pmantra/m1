from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

import ddtrace
from ldclient import Stage
from maven import feature_flags
from maven.feature_flags import migration_variation
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import insert, update

from authn.models.user import User
from common.health_profile.health_profile_service_client import (
    HealthProfileServiceClient,
)
from common.health_profile.health_profile_service_models import (
    ConditionType,
    GestationalDiabetesStatus,
)
from health.data_models.member_risk_flag import MemberRiskFlag
from health.data_models.risk_flag import RiskFlag
from health.models.health_profile import HealthProfile
from health.models.risk_enums import ModifiedReason, RiskFlagName, RiskInputKey
from health.services.risk_service import RiskService
from health.utils.constants import MIGRATE_PREGNANCY_DATA_FROM_MONO_TO_HPS
from storage.connection import db
from utils.launchdarkly import user_context
from utils.log import logger

log = logger(__name__)


@dataclass
class SetRiskResult:
    # set_risk() will do one of the following:
    # 1. Nothing (Risk name is invalid)
    # 2. Create a New Risk if it wasn't already active
    # 3. Confirm the Existing Risk
    # 4. End the Existing Risk & Create a new one if its value is different
    created_risk: Optional[MemberRiskFlag] = None
    confirmed_risk: Optional[MemberRiskFlag] = None
    ended_risk: Optional[MemberRiskFlag] = None


@dataclass
class ClearRiskResult:
    ended_risk: Optional[MemberRiskFlag] = None


# MemberRiskFlags should be queried via this service.
# A Member will have at most one active instance of a particular risk
class MemberRiskService:
    def __init__(
        self,
        # Provide User if already loaded, else the user id
        user: Union[User, int],
        # Set to False if you want caller to handle commits.   Useful for batch operations
        commit: bool = True,
        # Use session.execute for Insert/Update statements instead of session.add()
        # HealthProfile ORM events (set_risks_for_health_profile_change) invoke Risk Updates
        # from inside Flush/Commit event handlers.  SQL Alchemy ORM does not correctly handle
        # ORM model updates from within these handlers. Therefore updates need to be made via session.execute()
        write_using_execute: bool = False,
        # Written to the corresponding MemberRiskFlag fields during insert/updates
        modified_by: Optional[int] = None,  # user id of logged-in-user
        modified_reason: Optional[str] = None,
        # Incase you want to override the creation of the RiskService
        risk_service: Optional[RiskService] = None,
        # Provide Health Profile if already loaded
        health_profile: Optional[HealthProfile] = None,
        # Set to False if you do not want to update confirmed_at timestamp for existings risks
        confirm_existing_risks: bool = True,
    ):
        if isinstance(user, int):
            self.user = None
            self.user_id = user
        else:
            self.user = user
            self.user_id = user.id  # type: ignore

        self.commit = commit
        self.write_using_execute = write_using_execute

        self.modified_by = modified_by
        self.modified_reason = modified_reason

        if risk_service is None:
            risk_service = RiskService()
        self.risk_service = risk_service
        self.health_profile = health_profile

        self.confirm_existing_risks = confirm_existing_risks

        # Instance-level cache to reduce queries when
        # set_risk/clear_risk is called more than once
        self._active_risks: Optional[Dict[int, MemberRiskFlag]] = None

    def _user(self) -> User:
        if self.user is None:
            self.user = db.session.query(User).filter(User.id == self.user_id).one()  # type: ignore
        return self.user  # type: ignore

    def _active_track_names(self) -> List[str]:
        return [track.name for track in self._user().active_tracks]

    def get_member_risks(
        self, active_only: bool, track_relevant_only: bool
    ) -> List[MemberRiskFlag]:
        query = (
            db.session.query(MemberRiskFlag)
            .options(selectinload(MemberRiskFlag.risk_flag))
            .filter(MemberRiskFlag.user_id == self.user_id)
        )
        if active_only:
            query = query.filter(MemberRiskFlag.end.is_(None))
        results: List[MemberRiskFlag] = query.all()

        # filter out results that were never active (start & end date is same)
        results = [item for item in results if item.is_ever_active()]

        if track_relevant_only:
            tracks = self._active_track_names()
            results = [
                item for item in results if item.risk_flag.is_track_relevant(tracks)
            ]

        return results

    def has_risk(self, name: Union[str, RiskFlagName]) -> bool:
        return self.get_active_risk(name) is not None

    def get_active_risk(
        self, name: Union[str, RiskFlagName]
    ) -> Optional[MemberRiskFlag]:
        risk_flag = self.risk_service.get_by_name(name)
        if risk_flag is None:
            return None
        return self._get_active_risk(risk_flag.id)

    @ddtrace.tracer.wrap()
    def set_risk(
        self,
        name: Union[str, RiskFlagName],
        value: Optional[int] = None,
        update_calculated_risks: bool = True,
    ) -> SetRiskResult:
        result = SetRiskResult()
        now = datetime.now(timezone.utc)
        today = now.date()
        risk_flag = self.risk_service.get_by_name(name)
        if risk_flag is None:
            # Risk Flag/Name is invalid
            return result
        # check for active risk
        member_risk = self._get_active_risk(risk_flag.id)

        self._user()

        is_sync_risk_flag_and_gdm_status = self.user and feature_flags.bool_variation(
            "sync-risk-flag-and-gdm-status",
            user_context(self.user),
            default=False,
        )
        should_update_gdm_status = (
            is_sync_risk_flag_and_gdm_status
            and self.modified_reason != ModifiedReason.GDM_STATUS_UPDATE
        )

        if member_risk is not None:
            # If the Risk Value hasn't changed, confirm the existing instance
            # Otherwise end the existing instance and create a new one
            if value == member_risk.value:
                self._confirm_risk(member_risk, now)
                result.confirmed_risk = member_risk

                # update HPS GDM status when confirm member risk
                if should_update_gdm_status:
                    self.update_hps_gdm_status(member_risk, self.user)

            else:
                self._end_risk(member_risk, today)
                result.ended_risk = member_risk
                member_risk = None
        if member_risk is None:
            result.created_risk = self._create_risk(risk_flag, value, today, now)
            if update_calculated_risks:
                self.calculate_risks({}, risk_flag.name)

            # update HPS GDM status when create new member risk
            if should_update_gdm_status:
                self.update_hps_gdm_status(result.created_risk, self.user)
        return result

    @ddtrace.tracer.wrap()
    def update_hps_gdm_status(
        self, member_risk_flag: Optional[MemberRiskFlag], user: User
    ) -> None:
        split_cron_in_half_enabled = feature_flags.bool_variation(
            "split-nightly-risk-calculation-cron-into-half",
            default=False,
        )

        try:
            risk_flag_name = None
            if split_cron_in_half_enabled:
                # Safely access risk_flag.name without relying on lazy loading
                risk_flag_id = getattr(member_risk_flag, "risk_flag_id", None)
                if not risk_flag_id:
                    log.warning("No risk_flag_id for member_risk_flag")
                    return

                # Get risk flag directly instead of through relationship
                risk_flag = db.session.query(RiskFlag).get(risk_flag_id)
                if not risk_flag:
                    log.warning(f"Risk flag not found for ID {risk_flag_id}")
                    return

                risk_flag_name = risk_flag.name
            else:
                if not member_risk_flag or not member_risk_flag.risk_flag:
                    log.warning("Invalid member_risk_flag.", user.id)
                    return

                risk_flag_name = member_risk_flag.risk_flag.name

            context = user_context(user) if self.user else None
            (pregnancy_migration_stage, _) = migration_variation(
                flag_key=MIGRATE_PREGNANCY_DATA_FROM_MONO_TO_HPS,
                context=context,
                default=Stage.OFF,
            )
            release_pregnancy_updates = pregnancy_migration_stage != Stage.OFF

            health_profile_service_client = HealthProfileServiceClient(
                user=user, release_pregnancy_updates=release_pregnancy_updates
            )
            if risk_flag_name == RiskFlagName.DIABETES_EXISTING:
                self._handle_chronic_diabetes(
                    health_profile_service_client, member_risk_flag, user
                )
            elif risk_flag_name == RiskFlagName.GESTATIONAL_DIABETES_CURRENT_PREGNANCY:
                self._handle_gdm_current_pregnancy(
                    health_profile_service_client, member_risk_flag, user
                )
        except Exception as e:
            log.error(
                f"Failed to update GDM status for user {user.id}",
                error=str(e),
            )

    @ddtrace.tracer.wrap()
    def _handle_chronic_diabetes(
        self,
        health_profile_service_client: HealthProfileServiceClient,
        member_risk_flag: MemberRiskFlag,
        user: User,
    ) -> None:
        """Handles updates for chronic diabetes condition."""
        member_conditions = [
            {
                "condition_type": ConditionType.CHRONIC_DIABETES.value,
                "status": "active",
                "onset_date": None,
                "modifier": {
                    "id": user.id,
                    "name": user.full_name,
                    "role": "member",
                    "verticals": [],
                },
            }
        ]
        log.info("Handle Chronic Diabetes")
        health_profile_service_client.put_member_conditions(
            member_conditions=member_conditions
        )

    @ddtrace.tracer.wrap()
    def _handle_gdm_current_pregnancy(
        self,
        health_profile_service_client: HealthProfileServiceClient,
        member_risk_flag: MemberRiskFlag,
        user: User,
    ) -> None:
        """Handles updates for gestational diabetes during current pregnancy."""
        if not user.health_profile:
            log.warning(
                f"Health profile missing for user {user.id}. Skipping GDM status update for current pregnancy."
            )
            return
        if not user.health_profile.due_date:
            log.warning(
                f"Due date missing for user {user.id}. Skipping GDM status update for current pregnancy."
            )
            return
        log.info("Handle GDM Current Pregnancy!")
        health_profile_service_client.put_current_pregnancy_and_gdm_status(
            pregnancy_due_date=user.health_profile.due_date,
            gdm_status=GestationalDiabetesStatus.HAS_GDM,
            gdm_onset_date=None,
        )

    def clear_risk(
        self,
        name: Union[str, RiskFlagName],
        update_calculated_risks: bool = True,
    ) -> ClearRiskResult:
        result = ClearRiskResult()
        today = datetime.now(timezone.utc).date()
        risk_flag = self.risk_service.get_by_name(name)
        if risk_flag is None:
            return result
        member_risk = self._get_active_risk(risk_flag.id)
        if member_risk is not None:
            self._end_risk(member_risk, today)
            result.ended_risk = member_risk
            if update_calculated_risks:
                self.calculate_risks({}, risk_flag.name)
        return result

    # Update/Calculate Risks dependent on the provided updated values or risk
    def calculate_risks(
        self,
        updated_values: Dict[RiskInputKey, Any],
        updated_risk: Union[str, None] = None,
    ) -> None:
        from health.services.member_risk_calc_service import MemberRiskCalcService

        MemberRiskCalcService(self).run_for_updates(updated_values, updated_risk)

    def _get_active_risks(self) -> Dict[int, MemberRiskFlag]:
        if self._active_risks is None:
            self._set_active_risk_cache(self.get_member_risks(True, False))
        return self._active_risks  # type: ignore

    def _set_active_risk_cache(self, active_member_risks: List[MemberRiskFlag]) -> None:
        self._active_risks = {}
        for member_risk in active_member_risks:
            if member_risk.risk_flag_id in self._active_risks:
                self._end_duplicated_risk(member_risk)
            else:
                self._active_risks[member_risk.risk_flag_id] = member_risk

    def _get_active_risk(self, risk_flag_id: int) -> Optional[MemberRiskFlag]:
        return self._get_active_risks().get(risk_flag_id, None)

    def _create_risk(
        self,
        risk_flag: RiskFlag,
        value: Optional[int],
        start: date,
        confirmed_at: datetime,
    ) -> MemberRiskFlag:
        member_risk = MemberRiskFlag(
            user_id=self.user_id,
            risk_flag=risk_flag,
            value=value,
            start=start,
            confirmed_at=confirmed_at,
        )

        self._add_to_session(member_risk)
        self._log_info(
            "Created MemberRiskFlag",
            member_risk,
        )
        self._active_risks[member_risk.risk_flag.id] = member_risk  # type: ignore
        return member_risk

    def _confirm_risk(
        self,
        member_risk: MemberRiskFlag,
        confirmed_at: datetime,
    ) -> None:
        if self.confirm_existing_risks is False:
            return
        member_risk.confirmed_at = confirmed_at
        self._add_to_session(member_risk)
        self._log_info(
            "Confirming existing MemberRiskFlag",
            member_risk,
        )

    def _end_risk(
        self,
        member_risk: MemberRiskFlag,
        today: date,
    ) -> None:
        member_risk.end = today
        self._add_to_session(member_risk)
        self._log_info("Ended MemberRiskFlag", member_risk)
        self._active_risks.pop(member_risk.risk_flag_id)  # type: ignore

    def _end_duplicated_risk(
        self,
        member_risk: MemberRiskFlag,
    ) -> None:
        # If a risk is set concurrently across different requests
        # it's possible for there to be multiple instances of it
        # Ideally this would be stopped at the DB.
        # Sql Server has Filtered Unique Indices to do this
        # MySQL has a workaround, but it's complicated
        member_risk.end = datetime.now(timezone.utc).date()
        self._add_to_session(member_risk)
        self._log_info(
            "Member has multiple active instances of Risk. Ending extra instance",
            member_risk,
        )

    def _add_to_session(self, member_risk: MemberRiskFlag) -> None:
        member_risk.modified_by = self.modified_by
        member_risk.modified_reason = self.modified_reason

        if self.write_using_execute:
            if member_risk.id:
                op = update(MemberRiskFlag).where(MemberRiskFlag.id == member_risk.id)  # type: ignore
            else:
                op = insert(MemberRiskFlag)  # type: ignore
            db.session.execute(  # type: ignore
                op.values(
                    user_id=member_risk.user_id,
                    risk_flag_id=member_risk.risk_flag.id,
                    value=member_risk.value,
                    start=member_risk.start,
                    end=member_risk.end,
                    confirmed_at=member_risk.confirmed_at,
                    modified_by=member_risk.modified_by,
                    modified_reason=member_risk.modified_reason,
                )
            )
        else:
            db.session.add(member_risk)  # type: ignore
        if self.commit:
            db.session.commit()  # type: ignore

    def _log_info(
        self,
        message: str,
        member_risk: MemberRiskFlag,
    ) -> None:
        context: Dict[str, Any] = {
            "risk_flag": member_risk.risk_flag.name,
        }
        if member_risk is not None:
            context["member_risk_id"] = member_risk.id
            context["value"] = member_risk.value
            context["start"] = str(member_risk.start)
            context["end"] = str(member_risk.end)
            context["confirmed_at"] = str(member_risk.confirmed_at)
        log.info(
            message,
            user_id=self.user_id,
            context=context,
        )

    @ddtrace.tracer.wrap()
    def create_trimester_risk_flags(self, due_date: date) -> Optional[SetRiskResult]:
        self._user()
        log.info(f"user: {self.user}")

        should_create_trimester_flags = (
            self.user is not None
            and feature_flags.bool_variation(
                "trimester-risk-flag-release",
                user_context(self.user),
                default=False,
            )
        )
        log.info(f"should_create_trimester_flags: {should_create_trimester_flags}")
        result = None
        if should_create_trimester_flags:
            # label: 'due_date'; value sample: '2025-07-23 21:08:00+00:00'
            #
            # trimester_label is converted to the trimester risk flags
            # trimester_value is set to None
            trimester_label = self._calculate_trimester(due_date)
            log.info(f"trimester label: {trimester_label}")
            trimester_value = None
            if trimester_label:
                result = self.set_risk(trimester_label, trimester_value)
        return result

    @staticmethod
    @ddtrace.tracer.wrap()
    def _calculate_trimester(due_date: date) -> Optional[RiskFlagName]:
        """
        Calculate the member's pregnancy trimester based on the due date.

        Parameters:
        due_date (str): Expected due date in the format 'YYYY-MM-DD HH:MM:SS+00:00'.

        Returns:
        Optional[str]: Trimester risk flag based on the pregnancy week at onboarding,
                       or None if input is invalid.
        """
        try:
            due_date_dt = datetime.combine(due_date, datetime.min.time(), timezone.utc)

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
