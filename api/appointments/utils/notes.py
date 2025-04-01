from maven import feature_flags

from authn.models.user import User
from utils.flag_groups import MPACTICE_NOTES_WRITING_WITHOUT_APPT_RELEASE
from utils.launchdarkly import user_context
from utils.log import logger

log = logger(__name__)


def is_save_notes_without_appointment_table(user: User) -> bool:
    return feature_flags.bool_variation(
        MPACTICE_NOTES_WRITING_WITHOUT_APPT_RELEASE,
        user_context(user),
        default=False,
    )
