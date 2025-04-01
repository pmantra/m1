import traceback

from health.services.health_profile_service import HealthProfileService
from health.tasks.health_profile import (
    send_braze_biological_sex,
    send_braze_fertility_status,
    send_braze_prior_c_section_status,
)
from models import tracks
from models.base import db
from models.tracks.member_track import ChangeReason
from utils.log import logger
from utils.service_owner_mapper import service_ns_team_mapper

log = logger(__name__)


# Centralize Downstream subscribers to Health Profile changes
# Note: This centralization is not yet complete
# 1. All code that commits the HealthProfile should redirect to HealthProfileService class
#    Which will then invoke this class.
#    And any necessary downstream calls should be moved here or to HealthProfileService class
# 2. Risk Flags get updated when the Health Profile is committed
#    This happens inside the HealthProfile class within a SQL Alchemy Event Handler
#    It cannot safely be moved here until we are certain all HP write paths use HealthProfileService class
# 3. We will also want to add an internal API ontop of this class to be invoked by the new Health Profile Service
class HealthProfileChangeNotifyService:
    def on_health_profile_saved(
        self,
        hp_service: HealthProfileService,
    ) -> None:

        self.update_member_track(hp_service)  # type: ignore
        self.update_braze(hp_service)

    def update_member_track(
        self,
        hp_service: HealthProfileService,
    ) -> None:
        log.info(
            "Updating Member Track for Health Profile Change", user=hp_service.user_id
        )

        modified_by = str(hp_service.user_id)
        try:
            if hp_service.accessing_user:
                modified_by = str(hp_service.accessing_user.id)
        except Exception:
            log.error("Error getting Accessing User ID", error=traceback.format_exc())

        change_reason = (
            hp_service.change_reason or ChangeReason.AUTO_HEALTH_PROFILE_UPDATE
        )
        tracks.on_health_profile_update(
            user=hp_service.user,
            modified_by=modified_by,
            change_reason=change_reason,
        )
        db.session.commit()  # type: ignore

    def update_braze(self, hp_service: HealthProfileService) -> None:
        # send relevant braze events
        service_ns_tag = "health"
        team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
        user_id = hp_service.user_id
        if hp_service.changed_fields.fertility_treatment_status:
            send_braze_fertility_status.delay(user_id, hp_service.get_fertility_treatment_status(), service_ns=service_ns_tag, team_ns=team_ns_tag)  # type: ignore
        if hp_service.changed_fields.prior_c_section:
            send_braze_prior_c_section_status.delay(user_id, hp_service.get_prior_c_section(), service_ns=service_ns_tag, team_ns=team_ns_tag)  # type: ignore
        if hp_service.changed_fields.sex_at_birth:
            send_braze_biological_sex.delay(user_id, str(hp_service.get_sex_at_birth()), service_ns=service_ns_tag, team_ns=team_ns_tag)  # type: ignore
