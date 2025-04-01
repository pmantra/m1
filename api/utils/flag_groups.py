from __future__ import annotations

from enum import Enum

from utils.dotdict import DotDict


class AllowedFlagTypes(str, Enum):
    KILL_SWITCH = "kill-switch"
    RELEASE = "release"
    EXPERIMENT = "experiment"
    CONFIGURE = "configure"
    ENABLE = "enable"

    # * DO NOT USE WITH NEW FLAG GROUPS *
    # this exists to allow for the migration of existing flag that do not
    # confirm to the naming best practices to a flag group without key
    # modification.
    _EMPTY = ""

    # when used in the context of a string render out the value and not the
    # class name to facilitate a more intuitive interaction.
    def __str__(self) -> str:
        return self.value


disallowed_flag_group_characters = ["_", " "]


class FlagNameGroup(DotDict):
    """
    Provides a clean helper for organizing flag names into logical groups.
    - enforces naming best practices by default
    - enhances discoverability (search for flag group name to find all
    associated flags)
    - easier group cleanup. (delete the group and all flag references will
    complain at runtime)

    Example usage:

    Lets say you have a general topic that will contain many flags that are all
    part of a system but designed to be controlled independently. Lets call it
    "Cool New Feature". Lets pretend your pod is starting the work and multiple
    team members will be working on different parts of the feature. You could
    structure your flag group like this:

    # define the flag group
    COOL_NEW_FEATURE_RELEASE = FlagNameGroup(
        group_type=AllowedFlagTypes.RELEASE,
        namespace="cool-new-feature",
    )

    # add a flag to the group
    COOL_NEW_FEATURE_RELEASE.SOME_IMPLEMENTATION = (
        "some-implementation"
    )

    # access it anywhere as
    COOL_NEW_FEATURE_RELEASE.SOME_IMPLEMENTATION

    # the full flag name will be...
    COOL_NEW_FEATURE_RELEASE.SOME_IMPLEMENTATION == "release-cool-new-feature-some-implementation"

    # profit
    """

    _controlled_keys = ["_namespace", "_join_char", "_group_type"]

    def __init__(
        self,
        *,  # force keyword only arguments
        # all flags in this group will be of this type
        group_type: AllowedFlagTypes,
        # prefixed namespace of the flag group
        namespace: str,
        # WARNING:
        # Only specify a custom join char if you are attempting to match an
        # existing flag name. The flag name convention preference is hyphen and
        # is applied by default.
        # https://www.notion.so/mavenclinic/Flag-Conventions-a49b4a324b7f4959af2fc0628409eda2
        join_char: str = "-",
    ):
        super().__init__(self)
        # allow for empty string to support legacy flag migration to flag group
        if group_type is None:
            raise ValueError("group_type must be provided")
        # allow for empty string to support legacy flag migration to flag group
        if group_type and AllowedFlagTypes(group_type) not in AllowedFlagTypes:
            raise ValueError(f"invalid group_type [{group_type}]")

        # check against empty string too
        if not namespace:
            raise ValueError("namespace must be provided")
        # assert supported characters
        if any((not c.isalnum() and c != join_char) for c in namespace):
            raise ValueError(
                f"namespace [{namespace}] may only contain alphanumeric [a-z,0-9] and [{join_char}] characters",
            )
        if namespace.lower() != namespace:
            raise ValueError(f"namespace [{namespace}] must be all lowercase")

        self._group_type = group_type
        self._namespace = namespace
        self._join_char = join_char

    # we explicitly override the parent behavior to create the desired behavior
    def __getattr__(self, key: str) -> str | None:  # type: ignore[override]
        val = super().get(key)
        if key in self._controlled_keys:
            return str(val)

        if val is None:
            raise AttributeError(
                f"flag group [{self._namespace}] does not have flag [{key}]",
            )

        # account for _EMPTY group type
        group_part = f"{self._group_type}{self._join_char if self._group_type != AllowedFlagTypes._EMPTY else ''}"
        return f"{group_part}{self._namespace}{self._join_char}{val}"

    def flag_names(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # exclude the control keys
        keys = [k for k in super().keys() if k not in self._controlled_keys]
        return [self.__getattr__(k) for k in keys]


# ------------------------------------------------------------------------------
# Care Delivery Experiment Flags (Please keep the flags in the alphabetical order)
CARE_DELIVERY_EXPERIMENT = FlagNameGroup(
    group_type=AllowedFlagTypes._EMPTY,
    namespace="care-delivery-experiment",
)
# ------------------------------------------------------------------------------
# Care Discovery

# ------------------------------------------------------------------------------
# Care Delivery Release Flags

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# NOTE: CARE_DELIVERY_RELEASE does not conform to the naming best practices
# please create a new flag name group instead of extending this one.
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

# The underscore is not inline with best practice, hyphen is preferred character
# to join the parent namespace and flag name
CARE_DELIVERY_RELEASE = FlagNameGroup(
    group_type=AllowedFlagTypes._EMPTY,  # intentionally empty
    namespace="care_delivery_release",
    join_char="_",
)
# ------------------------------------------------------------------------------
# Virtual Care

CARE_DELIVERY_RELEASE.ENABLE_ZENDESK_V2_WEBHOOK_PROCESSING = (
    "enable_zendesk_v2_webhook_processing"
)
CARE_DELIVERY_RELEASE.ENABLE_ZENDESK_V2_RECONCILIATION_JOB = (
    "enable_zendesk_v2_reconciliation_job"
)
CARE_DELIVERY_RELEASE.ENABLE_MAVEN_TO_ZENDESK_RECONCILIATION_JOB = (
    "enable_maven_to_zendesk_reconciliation_job"
)
CARE_DELIVERY_RELEASE.ENABLE_ZENDESK_V2_RECONCILIATION_OF_TICKET = (
    "enable_zendesk_v2_reconciliation_of_ticket"
)
CARE_DELIVERY_RELEASE.ENABLE_ZENDESK_V2_RECONCILIATION_OF_COMMENT = (
    "enable_zendesk_v2_reconciliation_of_comment"
)

APPOINTMENT_NOTIFICATIONS = FlagNameGroup(
    group_type=AllowedFlagTypes.RELEASE, namespace="notify-appointment"
)

APPOINTMENT_NOTIFICATIONS.CONFIRM_APPOINTMENT_SMS = "confirm-sms"
APPOINTMENT_NOTIFICATIONS.CONFIRM_APPOINTMENT_SMS_CA = "confirm-sms-ca"

APPOINTMENT_NOTIFICATIONS.SET_REMINDER_MINUTES_BEFORE_START = (
    "set-reminder-minutes-before-start"
)

APPOINTMENT_NOTIFICATIONS.SMS_NOTIFY_MEMBER_ABOUT_NEW_APPOINTMENT = (
    "sms-notify-member-about-new-appointment"
)

APPOINTMENT_VIDEO_RELEASE = FlagNameGroup(
    group_type=AllowedFlagTypes.RELEASE,
    namespace="appointment-video-release",
)
APPOINTMENT_ALLOW_RX_OVERWRITE = "release-overwrite-rx-written-at-and-rx-written-via"

MPACTICE_NOTES_WRITING_WITHOUT_APPT_RELEASE = (
    "release-mpractice-save-notes-with-notes-v2-endpoint"
)

GET_MY_PATIENTS_MARSHMALLOW_V3_MIGRATION = "release-get-my-patients-mashmarllow-v3"

MARSHMALLOW_V3_MIGRATION = FlagNameGroup(
    group_type=AllowedFlagTypes.ENABLE, namespace="marshmallow-v3-migration"
)

MARSHMALLOW_V3_MIGRATION.CHANNELS_GET = "channels-get"
BILLING_GET_MARSHMALLOW_V3_MIGRATION = "experiment-marshmallow-billing-get-migration"
BILLING_POST_MARSHMALLOW_V3_MIGRATION = "experiment-marshmallow-billing-post-migration"
MESSAGES_GET_MARSHMALLOW_V3_MIGRATION = "experiment-marshmallow-messages-get-migration"

MAVEN_TO_ZENDESK_RECONCILIATION = FlagNameGroup(
    group_type=AllowedFlagTypes.RELEASE,
    namespace="maven-to-zendesk-reconciliation",
)


ZENDESK_V2_RECONCILIATION = FlagNameGroup(
    group_type=AllowedFlagTypes.CONFIGURE,
    namespace="zendesk-v2-reconciliation",
)
ZENDESK_V2_RECONCILIATION.UPDATED_TICKET_SEARCH_LOOKBACK_SECONDS = (
    "updated-ticket-search-lookback-seconds"
)
ZENDESK_V2_RECONCILIATION.UPDATED_TICKET_SEARCH_RUNAWAY_GUARD_SECONDS = (
    "updated-ticket-search-runaway-guard-seconds"
)

ZENDESK_CLIENT_CONFIGURATION = FlagNameGroup(
    group_type=AllowedFlagTypes.CONFIGURE,
    namespace="zendesk-client",
)
ZENDESK_CLIENT_CONFIGURATION.RATE_LIMIT_WARNING_THRESHOLD = (
    "rate-limit-warning-threshold"
)
ZENDESK_CLIENT_CONFIGURATION.ZENDESK_PERCENTAGE_THRESHOLD = "percentage-threshold"

ZENDESK_USER_PROFILE = FlagNameGroup(
    group_type=AllowedFlagTypes.KILL_SWITCH,
    namespace="zendesk-user-profile",
)

ZENDESK_USER_PROFILE.CREATED_ZENDESK_USER_PROFILE_POST_USER_CREATION = (
    "created-zendesk-user-profile-post-user-creation"
)

ZENDESK_USER_PROFILE.MERGE_DUPLICATE_ZENDESK_PROFILES = (
    "merge-duplicate-zendesk-user-profiles"
)

ZENDESK_USER_PROFILE.UPDATE_ZENDESK_USER_PROFILE = "update-zendesk-user-profile"

ZENDESK_CONFIGURATION = FlagNameGroup(
    group_type=AllowedFlagTypes.RELEASE,
    namespace="zendesk-configuration",
)

ZENDESK_CONFIGURATION.CHECK_CHANNEL_MEMBERS = "check-channel-members"

ZENDESK_UPDATE_ORGANIZATION = "enable-update-zendesk-organizations"

# ------------------------------------------------------------------------------
# Care Discovery
CARE_DELIVERY_RELEASE.ENABLE_APPOINTMENT_QUESTIONNAIRE_DESCENDING_SORT_ORDER = (
    "enable-appointment-questionnaire-descending-sort-order"
)
CARE_DELIVERY_RELEASE.ENABLE_RESCHEDULE_APPOINTMENT_WITHIN_2_HOURS = (
    "enable_reschedule_appointment_within_2_hours"
)

# ------------------------------------------------------------------------------
# DB interaction flags

# Flags to orchestrate db connection recovery behavior
DB_CONNECTION_RECOVERY_RELEASE = FlagNameGroup(
    group_type=AllowedFlagTypes.RELEASE,
    namespace="db-connection-recovery",
)
DB_CONNECTION_RECOVERY_RELEASE.RETRY_READ_ON_NETWORK_ERROR = (
    "retry-read-on-network-error"
)

# ------------------------------------------------------------------------------
# Core Services

# Flags for marshmallow migration
USER_GET_RESOURCE_MARSHMALLOW_V3_MIGRATION = "experiment-marshmallow-user-get-migration"
USER_PUT_RESOURCE_MARSHMALLOW_V3_MIGRATION = "experiment-marshmallow-user-put-migration"
USER_POST_RESOURCE_MARSHMALLOW_V3_MIGRATION = (
    "experiment-marshmallow-user-post-migration"
)
USER_DELETE_RESOURCE_MARSHMALLOW_V3_MIGRATION = (
    "experiment-marshmallow-user-deletion-migration"
)

# ------------------------------------------------------------------------------
