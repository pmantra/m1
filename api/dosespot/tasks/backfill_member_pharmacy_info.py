from __future__ import annotations

import traceback
from dataclasses import dataclass

import ddtrace
from maven import feature_flags

from dosespot.constants import (
    DOSESPOT_GLOBAL_CLINIC_ID_V2,
    DOSESPOT_GLOBAL_CLINIC_KEY_V2,
    DOSESPOT_GLOBAL_CLINIC_USER_ID_V2,
)
from dosespot.resources.dosespot_api import DoseSpotAPI
from models.profiles import MemberProfile
from storage.connection import db
from tasks.queues import job
from utils.log import logger

log = logger(__name__)


@dataclass
class Stats:
    num_users_already_have_pharmacy_info_in_mono: int = 0
    num_users_no_patient_id_in_mono: int = 0
    num_users_no_pharmacy_info_in_dosespot: int = 0
    num_users_updated: int = 0
    num_total_users_to_update: int = 0


class BackfillMemberPharmacyInfo:
    def __init__(self) -> None:
        self.dry_run = feature_flags.json_variation(
            "backfill-member-pharmacy-info",
            default='{"dry_run": true,  "user_ids": []}',
        ).get("dry_run", True)

        # TODO: update this job to auto fetch users that have DoseSpot patient ID but no pharmacy info in mono
        self.user_ids = feature_flags.json_variation(
            "backfill-member-pharmacy-info",
            default='{"dry_run": true,  "user_ids": []}',
        ).get("user_ids", [])

        self.session = db.session
        self.stats = Stats(num_total_users_to_update=len(self.user_ids))

    @ddtrace.tracer.wrap()
    def run(self) -> None:
        self._log_info("Backfill member pharmacy info - Starting")
        try:
            for user_id in self.user_ids:
                self.backfill_pharmacy_info_for_user(user_id)
            self._log_info("Backfill member pharmacy info - Completed")
            self._log_info(f"Backfill stats: {self.stats}")
        except Exception as e:
            self._log_info("Backfill member pharmacy info - Aborted")
            self._log_info(f"Backfill stats: {self.stats}")
            raise e

    @ddtrace.tracer.wrap()
    def backfill_pharmacy_info_for_user(self, user_id: int) -> None:
        try:
            self._log_info(f"Processing user {user_id}")

            member_profile: MemberProfile = MemberProfile.query.filter(
                MemberProfile.user_id == user_id
            ).one()
            pharmacy_info_mono = member_profile.get_prescription_info()
            if pharmacy_info_mono.get("pharmacy_info"):
                self._log_info(
                    f"User {user_id} already has pharmacy info in mono - Skipping"
                )
                self.stats.num_users_already_have_pharmacy_info_in_mono += 1
                return

            patient_id = self._get_patient_id(member_profile)
            if not patient_id:
                self._log_info(
                    f"User {user_id} does not have DoseSpot patient ID - Skipping"
                )
                self.stats.num_users_no_patient_id_in_mono += 1
                return

            pharmacy_info_dosespot = self._get_pharmacy_info_dosespot(
                user_id=user_id, patient_id=patient_id
            )
            if not pharmacy_info_dosespot:
                self._log_info(
                    f"User {user_id} does not have pharmacy info in DoseSpot - Skipping"
                )
                self.stats.num_users_no_pharmacy_info_in_dosespot += 1
                return

            pharmacy_info_to_save = {
                "pharmacy_id": pharmacy_info_dosespot["PharmacyId"],
                "pharmacy_info": pharmacy_info_dosespot,
            }
            member_profile.set_prescription_info(**pharmacy_info_to_save)
            if not self.dry_run:
                self.session.add(member_profile)
                self.session.commit()

            self._log_info(f"Successfully saved pharmacy info for user {user_id}")
            self.stats.num_users_updated += 1
        except Exception as e:
            log.error(
                "Backfill member pharmacy info - Exception",
                error=str(e),
                exc=traceback.format_exc(),
                context={"user_id": user_id},
            )
            raise e

    @staticmethod
    def _get_patient_id(member_profile: MemberProfile) -> str | None:
        for key in member_profile.dosespot.keys():
            if "practitioner:" in key and member_profile.dosespot.get(key).get(
                "patient_id"
            ):
                return member_profile.dosespot.get(key).get("patient_id")
        return None

    @staticmethod
    def _get_pharmacy_info_dosespot(user_id: int, patient_id: str) -> dict | None:
        dosespot_api = DoseSpotAPI(
            clinic_id=DOSESPOT_GLOBAL_CLINIC_ID_V2,
            clinic_key=DOSESPOT_GLOBAL_CLINIC_KEY_V2,
            user_id=DOSESPOT_GLOBAL_CLINIC_USER_ID_V2,
            maven_user_id=user_id,
        )
        return dosespot_api.get_patient_pharmacy(
            member_id=user_id, patient_id=patient_id
        )

    def _log_info(self, message: str) -> None:
        if self.dry_run:
            message = "[DRY RUN] " + message
        log.info(message)


@ddtrace.tracer.wrap()
@job("priority")
def backfill_member_pharmacy_info() -> None:
    BackfillMemberPharmacyInfo().run()
