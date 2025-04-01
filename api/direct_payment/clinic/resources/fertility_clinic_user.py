from direct_payment.clinic.resources.clinic_auth import ClinicAuthorizedResource
from direct_payment.clinic.schemas.fertility_clinic_user import (
    FertilityClinicUserProfileSchema,
)
from utils.log import logger

log = logger(__name__)


class FertilityClinicUserMeResource(ClinicAuthorizedResource):
    """
    Get information about the logged in FertilityClinicUserProfile
    """

    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return FertilityClinicUserProfileSchema().dump(self.current_user)
