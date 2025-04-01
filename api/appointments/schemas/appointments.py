from __future__ import annotations

import enum
from typing import Any, Dict, List, Tuple

import ddtrace
from marshmallow import Schema as Schema_v3
from marshmallow import fields as fields_v3
from marshmallow import validate as validate_v3
from marshmallow_v1 import Schema, fields
from maven import feature_flags
from sqlalchemy import and_
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.expression import desc

from appointments.models.appointment import Appointment
from appointments.models.appointment_meta_data import AppointmentMetaData
from appointments.models.constants import PRIVACY_CHOICES
from appointments.schemas.booking import NeedLiteSchema
from appointments.schemas.utils.reschedule_appointment import (
    get_rescheduled_from_previous_appointment_time,
)
from appointments.services.common import obfuscate_appointment_id
from appointments.services.flags import can_show_questionnaire_by_appt_vertical
from authn.models.user import User
from authz.models.roles import ROLES, Role
from common import stats
from models.questionnaires import (
    PROVIDER_ADDENDA_QUESTIONNAIRE_OID,
    ProviderAddendum,
    Question,
    Questionnaire,
    QuestionSet,
    RecordedAnswer,
    RecordedAnswerSet,
)
from providers.service.provider import ProviderService
from storage.connection import db
from utils.flag_groups import CARE_DELIVERY_RELEASE
from utils.launchdarkly import user_context
from utils.log import logger
from views.questionnaires import (
    ProviderAddendumSchema,
    QuestionnaireSchema,
    QuestionSetSchema,
    RecordedAnswerSchema,
    RecordedAnswerSetSchema,
)
from views.schemas.common import (
    BooleanField,
    CSVIntegerField,
    CSVStringField,
    DoseSpotPharmacySchema,
    MavenDateTime,
    MavenSchema,
    OrderDirectionField,
    PaginableArgsSchema,
    PaginableOutputSchema,
    PractitionerProfileSchema,
    PrivacyOptionsField,
    ProductSchema,
    SessionMetaInfoSchema,
    UserSchema,
    VideoSchema,
)

log = logger(__name__)

CANCELLATION_SURVEY_QUESTIONNAIRE_OID = "cancellation_survey"
# Confirm the prod data and remove one of "member_rating" and "member_rating_v2"
MEMBER_RATING_OIDS = ["member_rating_v2", "member_rating_followup_v2"]


def enable_appointment_questionnaire_descending_sort_order() -> bool:
    return feature_flags.bool_variation(
        CARE_DELIVERY_RELEASE.ENABLE_APPOINTMENT_QUESTIONNAIRE_DESCENDING_SORT_ORDER,
        default=False,
    )


def enable_hide_post_session_notes_draft_from_members() -> bool:
    return feature_flags.bool_variation(
        "release-hide-post-session-notes-draft-from-members",
        default=False,
    )


class UserInAppointmentSchema(UserSchema):
    class Meta:
        exclude = (
            # fields that have been confirmed to not be used by any
            # client.
            # ...
            # fields that are required to exist but not accessed by any
            # client. for these we will set an acceptable default value
            # in the data_handler below
            "care_coordinators",
        )


# A data handler is used to apply post-serialize overrides. This is required due
# to marshmallow_v1's property load behavior which loads data for all fields on
# the model that are not ignored. This prevents us from loading useless and
# costly data.
@UserInAppointmentSchema.data_handler
def user_in_channel_data_handler(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    self: UserInAppointmentSchema,
    data: dict,
    obj: User,
):
    # define overrides in func scope to protect from downstream modifications
    # being reflected in future instances. Pass-by-ref protection.
    overrides = {
        # Not accessed but required to exist by legacy clients.
        "care_coordinators": [],
    }
    # ensure we respect any `only` fields passed to the schema
    if self.only:
        filtered = {k: v for k, v in overrides.items() if k in self.only}
        overrides = filtered

    # inject all overrides listed above
    if data and isinstance(data, dict):
        data.update(overrides)
    return data


class ScheduleEventSchema(Schema):
    id = fields.Integer()
    starts_at = MavenDateTime()
    ends_at = MavenDateTime()
    description = fields.String()
    created_at = MavenDateTime()


class PotentialAppointmentSchema(Schema):
    scheduled_start = MavenDateTime()
    scheduled_end = MavenDateTime()
    total_credits = fields.Integer()


class SessionPrescriptionInfoSchema(MavenSchema):
    pharmacy_id = fields.String()
    pharmacy_info = fields.Nested(DoseSpotPharmacySchema, default=None, nullable=True)
    enabled = BooleanField()


class CancelledByTypes(str, enum.Enum):
    MEMBER = "member"
    PROVIDER = "provider"
    OTHER = "other"


class AppointmentSchema(MavenSchema):
    id = fields.Method("get_obfuscated_id")
    privacy = PrivacyOptionsField()
    schedule_event_id = fields.Integer()
    scheduled_start = MavenDateTime()
    scheduled_end = MavenDateTime()
    member_started_at = MavenDateTime()
    member_ended_at = MavenDateTime()
    phone_call_at = MavenDateTime()
    practitioner_started_at = MavenDateTime()
    practitioner_ended_at = MavenDateTime()
    disputed_at = MavenDateTime()
    cancelled_at = MavenDateTime()
    cancelled_by = fields.Method("get_cancelled_by")
    cancelled_note = fields.String()
    rx_written_at = MavenDateTime()
    rx_written_via = fields.String(choices=["call", "dosespot"])
    state = fields.String()
    purpose = fields.String()
    pre_session = fields.Nested(SessionMetaInfoSchema)
    post_session = fields.Method("get_post_session_notes")
    cancellation_policy = fields.Method("get_cancellation_policy")
    product = fields.Nested(ProductSchema)
    member = fields.Method("get_member")
    video = fields.Method("get_video_info")
    ratings = fields.Raw()
    prescription_info = fields.Method("get_prescription_info")
    structured_internal_note = fields.Method("get_structured_internal_note")
    provider_addenda = fields.Method("get_provider_addenda")
    member_rating = fields.Method("get_member_rating")
    repeat_patient = fields.Boolean()
    rx_enabled = fields.Boolean(default=False)
    rx_reason = fields.String()
    privilege_type = fields.Method("get_privilege_type")
    state_match_type = fields.Method("get_state_match_type")
    appointment_type = fields.Method("get_appointment_type")
    need_id = fields.Integer(default=None)  # type: ignore[arg-type] # Argument "default" to "Integer" has incompatible type "None"; expected "int"
    need = fields.Nested(NeedLiteSchema, required=False, default=None)
    surveys = fields.Method("get_surveys")
    rescheduled_from_previous_appointment_time = fields.Method(
        "get_rescheduled_from_previous_apt_time"
    )

    def get_obfuscated_id(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return obfuscate_appointment_id(obj.id)

    def get_privilege_type(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return obj.privilege_type

    def get_state_match_type(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # guard accessing `value` exception when state_match_type is None
        if obj.state_match_type is None:
            return None

        return obj.state_match_type.value

    def get_member(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with ddtrace.tracer.trace(name=f"{__name__}.get_member"):
            cu = context.get("user")
            if (cu == obj.practitioner and not obj.is_anonymous) or cu == obj.member:
                schema = UserInAppointmentSchema()
            else:
                schema = UserInAppointmentSchema(only=["profiles", "country"])
            schema.context["user"] = context.get("user")
            schema.context["include_profile"] = True
            schema.context["include_country_info"] = True
            schema.context["appointment"] = obj
            return schema.dump(obj.member).data

    def get_video_info(self, obj, context) -> dict:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        return VideoSchema().dump(obj.video).data

    def get_cancelled_by(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if obj.cancelled_by_user_id is None:
            return None
        elif obj.cancelled_by_user_id == obj.member_id:
            return CancelledByTypes.MEMBER
        elif obj.cancelled_by_user_id == obj.practitioner_id:
            return CancelledByTypes.PROVIDER
        else:
            return CancelledByTypes.OTHER

    def get_cancellation_policy(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return obj.cancellation_policy.name

    def get_appointment_type(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return obj.appointment_type.value

    def get_prescription_info(self, obj: Appointment) -> dict | None:
        if obj.is_anonymous:
            return {}

        member_profile = obj.member.member_profile
        if member_profile:
            prescription_info = member_profile.get_prescription_info()

            # default to false
            provider_can_prescribe = False
            # if the provider is present then check
            if obj.practitioner:
                provider_can_prescribe = ProviderService().enabled_for_prescribing(
                    obj.practitioner.id,
                    obj.practitioner.practitioner_profile,
                )

            prescription_info["enabled"] = (
                member_profile.enabled_for_prescription and provider_can_prescribe
            )

            schema = SessionPrescriptionInfoSchema()
            return schema.dump(prescription_info).data
        else:
            log.warning(f"Non-member user {obj.member} in appointment {obj.id}.")
        return None

    def get_post_session_notes(self, obj: Appointment, context):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        user = context.get("user")
        if user is None:
            raise ValueError("User missing from context")

        if enable_hide_post_session_notes_draft_from_members() and user == obj.member:
            # We only pass down the post session note to a member if it's not a draft
            latest_post_session_note = (
                db.session.query(AppointmentMetaData)
                .filter(
                    (AppointmentMetaData.appointment_id == obj.id)
                    & (AppointmentMetaData.draft.is_(False))
                )
                .order_by(AppointmentMetaData.created_at.desc())
                .first()
            )
            if latest_post_session_note is None:
                return {
                    "draft": None,
                    "notes": "",
                    "created_at": None,
                    "modified_at": None,
                }
            else:
                return {
                    "draft": latest_post_session_note.draft,
                    "notes": latest_post_session_note.content,
                    "created_at": latest_post_session_note.created_at.isoformat(),
                    "modified_at": latest_post_session_note.modified_at.isoformat(),
                }
        else:
            return SessionMetaInfoSchema().dump(obj.post_session).data

    def get_structured_internal_note(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with ddtrace.tracer.trace(name=f"{__name__}.get_structured_internal_note"):
            question_sets_json, recorded_answers_json = [], []
            questionnaire_json, recorded_answer_set_json = None, None

            (
                recorded_answer_set,
                questionnaire,
            ) = self._get_recorded_answer_set_questionnaire(
                appointment_id=obj.id, user_id=obj.practitioner_id
            )

            if recorded_answer_set:
                recorded_answer_set_json = (
                    RecordedAnswerSetSchema().dump(recorded_answer_set).data
                )

                recorded_answers_json = (
                    RecordedAnswerSchema(many=True)
                    .dump(recorded_answer_set.recorded_answers)
                    .data
                )
            else:
                # Recorded answers that were created before the concept of recorded answer sets
                # being linked to appointments will be directly attached to the appointment themselves
                user = context.get("user")
                recorded_answers = self._get_legacy_recorded_answers(
                    appointment_id=obj.id, user_id=user.id
                )

                recorded_answers_json = (
                    RecordedAnswerSchema(many=True).dump(recorded_answers).data
                )

            if questionnaire is None:
                questionnaire = Questionnaire.get_structured_internal_note_for_pract(
                    obj.practitioner
                )

            if questionnaire:
                questionnaire_json = QuestionnaireSchema().dump(questionnaire).data
                question_sets_json = (
                    QuestionSetSchema(many=True).dump(questionnaire.question_sets).data
                )

            return {
                # TODO: get rid of this once clients are all using questionnaire instead
                "question_sets": question_sets_json,
                # TODO: get rid of this once clients are all using recorded_answer_set instead
                "recorded_answers": recorded_answers_json,
                "questionnaire": questionnaire_json,
                "recorded_answer_set": recorded_answer_set_json,
            }

    @staticmethod
    @ddtrace.tracer.wrap()
    def _get_recorded_answer_set_questionnaire(appointment_id, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        result = (
            db.session.query(RecordedAnswerSet, Questionnaire)
            .filter(
                (RecordedAnswerSet.appointment_id == appointment_id)
                & (RecordedAnswerSet.source_user_id == user_id)
            )
            .outerjoin(
                Questionnaire, RecordedAnswerSet.questionnaire_id == Questionnaire.id
            )
            .order_by(RecordedAnswerSet.submitted_at.desc())
            .first()
        )
        if result is None:
            return None, None
        return result

    @staticmethod
    @ddtrace.tracer.wrap()
    def _get_legacy_recorded_answers(appointment_id, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        recorded_answers = (
            db.session.query(RecordedAnswer)
            .filter(
                and_(
                    RecordedAnswer.appointment_id == appointment_id,
                    RecordedAnswer.user_id == user_id,
                )
            )
            .all()
        )
        return recorded_answers

    def get_provider_addenda(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with ddtrace.tracer.trace(name=f"{__name__}.get_provider_addenda"):
            user = context.get("user")
            provider_addenda_enabled = feature_flags.bool_variation(
                "release-mpractice-practitioner-addenda",
                user_context(user),
                default=False,
            )
            if not provider_addenda_enabled:
                return {}

            questionnaire = (
                db.session.query(Questionnaire)
                .filter(Questionnaire.oid == PROVIDER_ADDENDA_QUESTIONNAIRE_OID)
                .one_or_none()
            )
            if questionnaire is None:
                return {}
            provider_addenda = (
                db.session.query(ProviderAddendum)
                .filter(
                    (ProviderAddendum.appointment_id == obj.id)
                    & (ProviderAddendum.user_id == obj.practitioner_id)
                    & (ProviderAddendum.questionnaire_id == questionnaire.id)
                )
                .order_by(ProviderAddendum.submitted_at.asc())
            ).all()
            questionnaire_json = QuestionnaireSchema().dump(questionnaire).data
            provider_addenda_json = (
                ProviderAddendumSchema(many=True).dump(provider_addenda).data
            )
            return {
                "questionnaire": questionnaire_json,
                "provider_addenda": provider_addenda_json,
            }

    def get_member_rating(self, obj: Appointment, context: Dict[Any, Any]):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        with ddtrace.tracer.trace(name=f"{__name__}.get_member_rating"):
            questionnaires, recorded_answers = self._get_member_rating_data(
                appointment=obj,
                context=context,
            )
            questionnaires_json = (
                QuestionnaireSchema(many=True).dump(questionnaires).data
            )
            recorded_answers_json = (
                RecordedAnswerSchema(many=True).dump(recorded_answers).data
            )

            return {
                "questionnaires": questionnaires_json,
                "recorded_answers": recorded_answers_json,
            }

    @staticmethod
    @ddtrace.tracer.wrap()
    def _get_member_rating_data(
        appointment: Appointment, context: Dict[Any, Any]
    ) -> Tuple[List[Questionnaire], List[RecordedAnswer]]:
        survey_metric_name = "api.appointments.schemas.appointments.survey"
        user: User = context.get("user")  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Optional[Any]", variable has type "User")
        if user is None:
            raise ValueError("User missing from context")

        if appointment is None:
            raise ValueError("Appointment required to get member rating data")

        # will hold an array of the questionnaires to be returned to the user
        questionnaires: List[Questionnaire] = []

        if can_show_questionnaire_by_appt_vertical(user):
            stats.increment(
                metric_name=survey_metric_name,
                tags=[
                    "survey_type:matching_vertical",
                    "variant:post_appointment_questionnaire_from_vertical",
                ],
                pod_name=stats.PodNames.VIRTUAL_CARE,
            )
            log.info(
                "sourcing questionnaires by vertical",
                appointment_id=appointment.id,
                user_id=user.id,
            )

            # find the questionnaires that has verticals field set to be the same value
            # as the appointment product vertical id.
            # TODO: clean up the code after the flag is enabled and confirmed safe
            if enable_appointment_questionnaire_descending_sort_order():
                questionnaires = (
                    db.session.query(Questionnaire)
                    .filter(Questionnaire.roles.any(Role.name == ROLES.member))
                    .filter(
                        Questionnaire.verticals.any(id=appointment.product.vertical_id)
                    )
                    .options(selectinload(Questionnaire.roles))
                    .order_by(Questionnaire.sort_order)
                    .all()
                )
            else:
                questionnaires = (
                    db.session.query(Questionnaire)
                    .filter(Questionnaire.roles.any(Role.name == ROLES.member))
                    .filter(
                        Questionnaire.verticals.any(id=appointment.product.vertical_id)
                    )
                    .options(selectinload(Questionnaire.roles))
                    .order_by(Questionnaire.sort_order.desc())
                    .all()
                )

        # If we couldn't find a questionnaire with the selected vertical, we fall back to
        # the questionnaires with oid member_rating_v2 and member_rating_followup_v2.
        if not questionnaires:
            stats.increment(
                metric_name=survey_metric_name,
                tags=[
                    "survey_type:cancellation_survey",
                    "variant:member_rating",
                ],
                pod_name=stats.PodNames.VIRTUAL_CARE,
            )

            # TODO: clean up the code after the flag is enabled and confirmed safe
            if enable_appointment_questionnaire_descending_sort_order():
                questionnaires = (
                    db.session.query(Questionnaire)
                    .filter(Questionnaire.oid.in_(MEMBER_RATING_OIDS))
                    .order_by(Questionnaire.sort_order)
                    .all()
                )
            else:
                questionnaires = (
                    db.session.query(Questionnaire)
                    .filter(Questionnaire.oid.in_(MEMBER_RATING_OIDS))
                    .order_by(Questionnaire.sort_order)
                    .order_by(Questionnaire.sort_order.desc())
                    .all()
                )

        # if no questionnaires were found in the above steps, fall back to
        # a default match against a member role.
        if not questionnaires:
            log.info(
                "sourcing questionnaires fallback",
                appointment_id=appointment.id,
                user_id=user.id,
            )
            questionnaires = (
                db.session.query(Questionnaire)
                .filter(Questionnaire.roles.any(Role.name == ROLES.member))
                .options(selectinload(Questionnaire.roles))
                .order_by(desc(Questionnaire.id))
                .all()
            )

        recorded_answers: List[RecordedAnswer] = (
            db.session.query(RecordedAnswer)
            .filter(
                RecordedAnswer.appointment_id == appointment.id,
                Questionnaire.id.in_([q.id for q in questionnaires]),
            )
            .join(Question)
            .join(QuestionSet)
            .join(Questionnaire)
            .all()
        )

        return questionnaires, recorded_answers

    def get_surveys(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        obj: api.appointments.models.appointment.Appointment
        context: a dictionary that contains "user" : User
        """
        with ddtrace.tracer.trace(name=f"{__name__}.get_surveys"):
            user = context.get("user")

            # Only return the cancellation survey when a member cancels the appointment
            if obj.cancelled_at is None or user == obj.practitioner:
                return {}

            stats.increment(
                metric_name="api.appointments.schemas.appointments.cancellation_survey",
                tags=["variant:surveys_cancellation_survey"],
                pod_name=stats.PodNames.VIRTUAL_CARE,
            )

            questionnaires = self._get_cancellation_survey_data()
            questionnaires_json = (
                QuestionnaireSchema(many=True).dump(questionnaires).data
            )

            log.info(f"Cancellation survey queried for appointment id {obj.id}.")

            return {
                CANCELLATION_SURVEY_QUESTIONNAIRE_OID: {
                    "questionnaires": questionnaires_json,
                    "recorded_answers": [],
                }
            }

    @ddtrace.tracer.wrap()
    def get_rescheduled_from_previous_apt_time(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with ddtrace.tracer.trace(
            name=f"{__name__}.get_rescheduled_from_previous_appointment_time_appointment_schema"
        ):
            dd_metric_name = "api.appointments.schemas.appointments.reschedule_history_appointment_schema"
            return get_rescheduled_from_previous_appointment_time(
                obj, context, dd_metric_name
            )

    @staticmethod
    @ddtrace.tracer.wrap()
    def _get_cancellation_survey_data():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        questionnaires = (
            db.session.query(Questionnaire)
            .filter(Questionnaire.oid == CANCELLATION_SURVEY_QUESTIONNAIRE_OID)
            .all()
        )
        return questionnaires


class PatchAppointmentRequestSchema(Schema_v3):
    need_id = fields_v3.Integer(required=False, allow_none=True)
    client_notes = fields_v3.String(data_key="notes", required=False)
    rx_written_at = fields_v3.DateTime(required=False, allow_none=True)
    rx_written_via = fields_v3.String(
        validate=validate_v3.OneOf(["call", "dosespot"]), required=False
    )


# despite name, does not include member profile 😶
class MinimalUserProfilesSchema(Schema):
    practitioner = fields.Method("get_practitioner_profile")

    def get_practitioner_profile(self, _profiles, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        schema = PractitionerProfileSchema(only=["verticals"])
        if "user" not in context:
            return {}
        profiles = context["user"].profiles_map

        if not profiles.get(ROLES.practitioner):
            return {}

        profile = profiles[ROLES.practitioner]

        return schema.dump(profile).data


class MinimalPractitionerSchema(Schema):
    id = fields.Integer()
    profiles = fields.Method("get_profiles")
    first_name = fields.String()
    last_name = fields.String()
    name = fields.Method("get_name")
    image_url = fields.Method("get_image_url")

    def get_profiles(self, user, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        profiles = user.profiles_map
        schema = MinimalUserProfilesSchema(context={"user": user})
        return schema.dump(profiles).data

    def get_name(self, user, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return user.full_name

    def get_image_url(self, user, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return user.avatar_url


class MinimalProductSchema(Schema):
    practitioner = fields.Nested(
        MinimalPractitionerSchema(only=["profiles", "name", "image_url"])
    )


class MinimalAppointmentSchema(Schema):
    id = fields.Method("get_obfuscated_id")
    appointment_id = fields.Method("get_appointment_id")
    privacy = PrivacyOptionsField()
    scheduled_start = MavenDateTime()
    scheduled_end = MavenDateTime()
    cancelled_at = MavenDateTime()
    product = fields.Nested(MinimalProductSchema)
    member = fields.Method("get_member")
    pre_session = fields.Nested(SessionMetaInfoSchema)
    post_session = fields.Nested(SessionMetaInfoSchema)
    repeat_patient = fields.Boolean()
    state = fields.String()
    privilege_type = fields.Method("get_privilege_type")
    state_match_type = fields.Method("get_state_match_type")
    need = fields.Nested(NeedLiteSchema)
    rescheduled_from_previous_appointment_time = fields.Method(
        "get_rescheduled_from_previous_apt_time"
    )

    def get_appointment_id(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return obj.id

    def get_privilege_type(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return obj.privilege_type

    def get_state_match_type(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return obj.state_match_type.value

    def get_obfuscated_id(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return obfuscate_appointment_id(obj.id)

    def get_member(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        cu = context.get("user")
        fields = []

        if cu == obj.practitioner:
            fields.append("country")
            if not obj.is_anonymous:
                fields.extend(("image_url", "name", "created_at"))
        elif cu == obj.member:
            fields.extend(("name", "image_url", "country"))

        if any(fields):
            schema = UserInAppointmentSchema(
                only=fields, context=dict(include_country_info=True)
            )
            return schema.dump(obj.member).data
        else:
            return {}

    @ddtrace.tracer.wrap()
    def get_rescheduled_from_previous_apt_time(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with ddtrace.tracer.trace(
            name=f"{__name__}.get_rescheduled_from_previous_appointment_time_minimal_appointment_schema"
        ):
            dd_metric_name = "api.appointments.schemas.appointments.reschedule_history_minimal_appointment_schema"
            return get_rescheduled_from_previous_appointment_time(
                obj, context, dd_metric_name
            )


class MinimalAdminAppointmentSchema(Schema):
    id = fields.Integer()
    scheduled_start = MavenDateTime()
    scheduled_end = MavenDateTime()
    member = fields.Method("get_member")
    cancelled_at = MavenDateTime()
    rescheduled_from_previous_appointment_time = fields.Method(
        "get_rescheduled_from_previous_apt_time"
    )
    is_intro = fields.Boolean()

    def get_member(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return UserInAppointmentSchema(only=["full_name", "id"]).dump(obj.member).data

    @ddtrace.tracer.wrap()
    def get_rescheduled_from_previous_apt_time(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with ddtrace.tracer.trace(
            name=f"{__name__}.get_rescheduled_from_previous_appointment_time_appointment_schema"
        ):
            dd_metric_name = "api.appointments.schemas.appointments.reschedule_history_appointment_schema"
            return get_rescheduled_from_previous_appointment_time(
                obj, context, dd_metric_name
            )


class PractitionerNotesProductSchema(Schema):
    practitioner = fields.Nested(MinimalPractitionerSchema)


class PractitionerNotesAppointmentSchema(MavenSchema):
    id = fields.Method("get_obfuscated_id")
    product = fields.Nested(PractitionerNotesProductSchema)
    pre_session = fields.Nested(SessionMetaInfoSchema)
    post_session = fields.Nested(SessionMetaInfoSchema)
    scheduled_start = MavenDateTime()
    scheduled_end = MavenDateTime()
    state = fields.String()
    cancelled_by = fields.Method("get_cancelled_by")
    need = fields.Nested(NeedLiteSchema)
    structured_internal_note = fields.Method("get_structured_internal_note")
    provider_addenda = fields.Method("get_provider_addenda")

    def get_obfuscated_id(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return obfuscate_appointment_id(obj.id)

    def get_cancelled_by(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if obj.cancelled_by_user_id is None:
            return None
        elif obj.cancelled_by_user_id == obj.member_id:
            return CancelledByTypes.MEMBER
        elif obj.cancelled_by_user_id == obj.practitioner_id:
            return CancelledByTypes.PROVIDER
        else:
            return CancelledByTypes.OTHER

    def get_structured_internal_note(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with ddtrace.tracer.trace(name=f"{__name__}.get_structured_internal_note"):
            question_sets_json, recorded_answers_json = [], []
            questionnaire_json, recorded_answer_set_json = None, None

            appointment_id = obj.id
            data = context.get("structured_internal_note", {}).get(appointment_id, {})

            recorded_answer_set = data.get("recorded_answer_set")
            recorded_answers = data.get("recorded_answers")
            if recorded_answer_set:
                recorded_answer_set_json = (
                    RecordedAnswerSetSchema().dump(recorded_answer_set).data
                )

                if recorded_answer_set.recorded_answers:
                    recorded_answers_json = (
                        RecordedAnswerSchema(many=True)
                        .dump(recorded_answer_set.recorded_answers)
                        .data
                    )
            elif recorded_answers:
                # Recorded answers that were created before the concept of recorded answer sets
                # being linked to appointments will be directly attached to the appointment themselves
                recorded_answers_json = (
                    RecordedAnswerSchema(many=True).dump(recorded_answers).data
                )

            questionnaire = data.get("questionnaire")
            if questionnaire:
                questionnaire_json = QuestionnaireSchema().dump(questionnaire).data
                question_sets_json = (
                    QuestionSetSchema(many=True).dump(questionnaire.question_sets).data
                )

            return {
                "question_sets": question_sets_json,
                "recorded_answers": recorded_answers_json,
                "questionnaire": questionnaire_json,
                "recorded_answer_set": recorded_answer_set_json,
            }

    def get_provider_addenda(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with ddtrace.tracer.trace(name=f"{__name__}.get_provider_addenda"):
            user = context.get("user")
            provider_addenda_enabled = feature_flags.bool_variation(
                "release-mpractice-practitioner-addenda",
                user_context(user),
                default=False,
            )
            if not provider_addenda_enabled:
                return {}

            questionnaire = (
                db.session.query(Questionnaire)
                .filter(Questionnaire.oid == PROVIDER_ADDENDA_QUESTIONNAIRE_OID)
                .one_or_none()
            )
            if questionnaire is None:
                return {}
            provider_addenda = (
                db.session.query(ProviderAddendum)
                .filter(
                    (ProviderAddendum.appointment_id == obj.id)
                    & (ProviderAddendum.user_id == obj.practitioner_id)
                    & (ProviderAddendum.questionnaire_id == questionnaire.id)
                )
                .order_by(ProviderAddendum.submitted_at.asc())
            ).all()
            questionnaire_json = QuestionnaireSchema().dump(questionnaire).data
            provider_addenda_json = (
                ProviderAddendumSchema(many=True).dump(provider_addenda).data
            )
            return {
                "questionnaire": questionnaire_json,
                "provider_addenda": provider_addenda_json,
            }


class AppointmentsMetaSchema(Schema):
    schedule_event_ids = CSVIntegerField()
    scheduled_start = MavenDateTime()
    scheduled_end = MavenDateTime()


class AppointmentsSchema(PaginableOutputSchema):
    data = fields.Nested(AppointmentSchema, many=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchema" defined the type as "Raw")
    meta = fields.Nested(AppointmentsMetaSchema)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchema" defined the type as "Raw")


class MinimalAppointmentsSchema(PaginableOutputSchema):
    meta = fields.Nested(AppointmentsMetaSchema)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchema" defined the type as "Raw")
    data = fields.Nested(MinimalAppointmentSchema, many=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchema" defined the type as "Raw")


class AppointmentGetSchema(PaginableArgsSchema):
    schedule_event_ids = CSVIntegerField(required=False)
    scheduled_start = MavenDateTime()
    scheduled_start_before = MavenDateTime()
    scheduled_end = MavenDateTime()
    member_id = fields.Integer()
    practitioner_id = fields.Integer()
    exclude_statuses = CSVStringField(required=False)
    purposes = CSVStringField(required=False)
    order_direction = OrderDirectionField(default="asc", required=False)
    minimal = fields.Boolean(required=False)


class AppointmentCreateSchema(AppointmentSchema):
    product_id = fields.Integer(required=True)
    scheduled_start = MavenDateTime(required=True)
    need_id = fields.Integer(required=False)

    class Meta:
        only = ("product_id", "scheduled_start", "privacy", "pre_session")


class CancellationPolicySchema(Schema):
    name = fields.String()
    refund_0_hours = fields.Integer()
    refund_2_hours = fields.Integer()
    refund_6_hours = fields.Integer()
    refund_12_hours = fields.Integer()
    refund_24_hours = fields.Integer()
    refund_48_hours = fields.Integer()


class CancellationPoliciesSchema(PaginableOutputSchema):
    data = fields.Nested(CancellationPolicySchema, many=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchema" defined the type as "Raw")


class PrivacyType(str, enum.Enum):
    ANONYMOUS = PRIVACY_CHOICES.anonymous
    BASIC = PRIVACY_CHOICES.basic
    FULL_ACCESS = PRIVACY_CHOICES.full_access
