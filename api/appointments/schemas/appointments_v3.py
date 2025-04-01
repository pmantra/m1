from __future__ import annotations

from typing import Any, Dict, List, Tuple

import ddtrace
from marshmallow import fields as marshmallow_fields
from maven import feature_flags
from sqlalchemy import and_
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.expression import desc

from appointments.models.appointment import Appointment
from appointments.models.appointment_meta_data import AppointmentMetaData
from appointments.schemas.appointments import (
    CANCELLATION_SURVEY_QUESTIONNAIRE_OID,
    MEMBER_RATING_OIDS,
    CancelledByTypes,
    enable_appointment_questionnaire_descending_sort_order,
    enable_hide_post_session_notes_draft_from_members,
    obfuscate_appointment_id,
)
from appointments.schemas.booking_v3 import NeedLiteSchemaV3
from appointments.schemas.utils.reschedule_appointment import (
    get_rescheduled_from_previous_appointment_time,
)
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
from utils.launchdarkly import user_context
from utils.log import logger
from views.questionnaires import (
    ProviderAddendumSchemaV3,
    QuestionnaireSchemaV3,
    QuestionSetSchemaV3,
    RecordedAnswerSchemaV3,
    RecordedAnswerSetSchemaV3,
)
from views.schemas.base import (
    BooleanWithDefault,
    IntegerWithDefaultV3,
    MavenSchemaV3,
    NestedWithDefaultV3,
    PaginableOutputSchemaV3,
    PractitionerProfileSchemaV3,
    SchemaV3,
    StringWithDefaultV3,
)
from views.schemas.common_v3 import (
    CSVIntegerField,
    CSVStringField,
    DoseSpotPharmacySchemaV3,
    MavenDateTime,
    OrderDirectionField,
    PaginableArgsSchemaV3,
    PrivacyOptionsField,
    ProductSchemaV3,
    SessionMetaInfoSchemaV3,
    UserSchemaV3,
    V3BooleanField,
    VideoSchemaV3,
)

log = logger(__name__)


class AppointmentV3Schema(MavenSchemaV3):
    appointment_id = marshmallow_fields.Integer(required=True)
    product_id = marshmallow_fields.Integer(required=True)
    member_id = marshmallow_fields.Integer(required=True)
    provider_id = marshmallow_fields.Integer(required=True)
    scheduled_start = marshmallow_fields.DateTime(required=True)
    scheduled_end = marshmallow_fields.DateTime(required=True)


class SessionPrescriptionInfoSchemaV3(MavenSchemaV3):
    pharmacy_id = StringWithDefaultV3(default="")
    pharmacy_info = marshmallow_fields.Nested(
        DoseSpotPharmacySchemaV3, default=None, nullable=True
    )
    enabled = V3BooleanField()


class UserInAppointmentSchemaV3(UserSchemaV3):
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


class AppointmentSchemaV3(MavenSchemaV3):
    id = marshmallow_fields.Method("get_obfuscated_id")
    privacy = PrivacyOptionsField(required=False)
    schedule_event_id = IntegerWithDefaultV3(default=0)
    scheduled_start = MavenDateTime()
    scheduled_end = MavenDateTime()
    member_started_at = MavenDateTime()
    member_ended_at = MavenDateTime()
    phone_call_at = MavenDateTime()
    practitioner_started_at = MavenDateTime()
    practitioner_ended_at = MavenDateTime()
    disputed_at = MavenDateTime()
    cancelled_at = MavenDateTime()
    cancelled_by = marshmallow_fields.Method("get_cancelled_by")
    cancelled_note = StringWithDefaultV3(default="")
    rx_written_at = MavenDateTime()
    rx_written_via = StringWithDefaultV3(choices=["call", "dosespot"], default="")
    state = StringWithDefaultV3(default="")
    purpose = StringWithDefaultV3(default="")
    pre_session = marshmallow_fields.Nested(SessionMetaInfoSchemaV3)
    post_session = marshmallow_fields.Method("get_post_session_notes")
    cancellation_policy = marshmallow_fields.Method("get_cancellation_policy")
    product = marshmallow_fields.Nested(ProductSchemaV3)
    member = marshmallow_fields.Method("get_member")
    video = marshmallow_fields.Method("get_video_info")
    ratings = marshmallow_fields.Raw()
    prescription_info = marshmallow_fields.Method("get_prescription_info")
    structured_internal_note = marshmallow_fields.Method("get_structured_internal_note")
    provider_addenda = marshmallow_fields.Method("get_provider_addenda")
    member_rating = marshmallow_fields.Method("get_member_rating")
    repeat_patient = marshmallow_fields.Boolean()
    rx_enabled = BooleanWithDefault(default=False)
    rx_reason = StringWithDefaultV3(default="")
    privilege_type = marshmallow_fields.Method("get_privilege_type")
    state_match_type = marshmallow_fields.Method("get_state_match_type")
    appointment_type = marshmallow_fields.Method("get_appointment_type")
    need_id = marshmallow_fields.Integer(default=None)  # type: ignore[arg-type] # Argument "default" to "Integer" has incompatible type "None"; expected "int"
    need = marshmallow_fields.Nested(NeedLiteSchemaV3, required=False, default=None)
    surveys = marshmallow_fields.Method("get_surveys")
    rescheduled_from_previous_appointment_time = marshmallow_fields.Method(
        "get_rescheduled_from_previous_apt_time"
    )

    def get_obfuscated_id(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not hasattr(obj, "id"):
            return None
        return obfuscate_appointment_id(obj.id)

    def get_privilege_type(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not hasattr(obj, "privilege_type"):
            return None
        return obj.privilege_type

    def get_state_match_type(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # guard accessing `value` exception when state_match_type is None
        if not hasattr(obj, "privilege_type") or obj.state_match_type is None:
            return None
        if not hasattr(obj.state_match_type, "value"):
            return None
        return obj.state_match_type.value

    def get_member(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with ddtrace.tracer.trace(name=f"{__name__}.get_member"):
            cu = self.context.get("user")
            if (
                hasattr(obj, "practitioner")
                and cu == obj.practitioner
                and not obj.is_anonymous
            ) or (hasattr(obj, "member") and cu == obj.member):
                schema = UserInAppointmentSchemaV3()
            else:
                schema = UserInAppointmentSchemaV3(only=["profiles", "country"])
            schema.context["user"] = self.context.get("user")
            schema.context["include_profile"] = True
            schema.context["include_country_info"] = True
            schema.context["appointment"] = obj
            if not hasattr(obj, "member"):
                return None
            return schema.dump(obj.member)

    def get_video_info(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        if not hasattr(obj, "video"):
            return None
        return VideoSchemaV3().dump(obj.video)

    def get_cancelled_by(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not hasattr(obj, "cancelled_by_user_id") or obj.cancelled_by_user_id is None:
            return None
        elif obj.cancelled_by_user_id == obj.member_id:
            return CancelledByTypes.MEMBER
        elif obj.cancelled_by_user_id == obj.practitioner_id:
            return CancelledByTypes.PROVIDER
        else:
            return CancelledByTypes.OTHER

    def get_cancellation_policy(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not hasattr(obj, "cancellation_policy"):
            return None
        return obj.cancellation_policy.name

    def get_appointment_type(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not hasattr(obj, "appointment_type"):
            return None
        return obj.appointment_type.value

    def get_prescription_info(self, obj: Appointment) -> dict | None:
        if hasattr(obj, "is_anonymous") and obj.is_anonymous:
            return {}

        if hasattr(obj, "member"):
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

                schema = SessionPrescriptionInfoSchemaV3()
                return schema.dump(prescription_info)
            else:
                log.warning(f"Non-member user {obj.member} in appointment {obj.id}.")
        return None

    def get_post_session_notes(self, obj: Appointment):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        user = self.context.get("user")
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
                return None
            else:
                return {
                    "draft": latest_post_session_note.draft,
                    "notes": latest_post_session_note.content,
                    "created_at": latest_post_session_note.created_at.isoformat(),
                    "modified_at": latest_post_session_note.modified_at.isoformat(),
                }
        else:
            return SessionMetaInfoSchemaV3().dump(obj.post_session)

    def get_structured_internal_note(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with ddtrace.tracer.trace(name=f"{__name__}.get_structured_internal_note"):
            question_sets_json, recorded_answers_json = [], []
            questionnaire_json, recorded_answer_set_json = None, None
            if not hasattr(obj, "id") or hasattr(obj, "practitioner_id"):
                return None
            (
                recorded_answer_set,
                questionnaire,
            ) = self._get_recorded_answer_set_questionnaire(
                appointment_id=obj.id, user_id=obj.practitioner_id
            )

            if recorded_answer_set:
                recorded_answer_set_json = RecordedAnswerSetSchemaV3().dump(
                    recorded_answer_set
                )

                recorded_answers_json = RecordedAnswerSchemaV3(many=True).dump(
                    recorded_answer_set.recorded_answers
                )
            else:
                # Recorded answers that were created before the concept of recorded answer sets
                # being linked to appointments will be directly attached to the appointment themselves
                user = self.context.get("user")
                recorded_answers = self._get_legacy_recorded_answers(
                    appointment_id=obj.id, user_id=user.id  # type: ignore[union-attr]
                )

                recorded_answers_json = RecordedAnswerSchemaV3(many=True).dump(
                    recorded_answers
                )

            if questionnaire is None:
                questionnaire = Questionnaire.get_structured_internal_note_for_pract(
                    obj.practitioner
                )

            if questionnaire:
                questionnaire_json = QuestionnaireSchemaV3().dump(questionnaire)
                question_sets_json = QuestionSetSchemaV3(many=True).dump(
                    questionnaire.question_sets
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

    def get_provider_addenda(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with ddtrace.tracer.trace(name=f"{__name__}.get_provider_addenda"):
            user = self.context.get("user")
            if not hasattr(user, "esp_id"):
                return None

            provider_addenda_enabled = feature_flags.bool_variation(
                "release-mpractice-practitioner-addenda",
                user_context(user),  # type: ignore[arg-type]
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
            questionnaire_json = QuestionnaireSchemaV3().dump(questionnaire)
            provider_addenda_json = ProviderAddendumSchemaV3(many=True).dump(
                provider_addenda
            )
            return {
                "questionnaire": questionnaire_json,
                "provider_addenda": provider_addenda_json,
            }

    def get_member_rating(self, obj: Appointment):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        with ddtrace.tracer.trace(name=f"{__name__}.get_member_rating"):
            questionnaires, recorded_answers = self._get_member_rating_data(
                appointment=obj,
                context=self.context,
            )
            questionnaires_json = QuestionnaireSchemaV3(many=True).dump(questionnaires)
            recorded_answers_json = RecordedAnswerSchemaV3(many=True).dump(
                recorded_answers
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

    def get_surveys(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        obj: api.appointments.models.appointment.Appointment
        context: a dictionary that contains "user" : User
        """
        with ddtrace.tracer.trace(name=f"{__name__}.get_surveys"):
            user = self.context.get("user")

            # Only return the cancellation survey when a member cancels the appointment
            if (hasattr(obj, "cancelled_at") and obj.cancelled_at is None) or (
                hasattr(obj, "practitioner") and user == obj.practitioner
            ):
                return {}

            stats.increment(
                metric_name="api.appointments.schemas.appointments.cancellation_survey",
                tags=["variant:surveys_cancellation_survey"],
                pod_name=stats.PodNames.VIRTUAL_CARE,
            )

            questionnaires = self._get_cancellation_survey_data()
            questionnaires_json = QuestionnaireSchemaV3(many=True).dump(questionnaires)

            if hasattr(obj, "id"):
                log.info(f"Cancellation survey queried for appointment id {obj.id}.")

            if not questionnaires_json:
                return None
            return {
                CANCELLATION_SURVEY_QUESTIONNAIRE_OID: {
                    "questionnaires": questionnaires_json,
                    "recorded_answers": [],
                }
            }

    @ddtrace.tracer.wrap()
    def get_rescheduled_from_previous_apt_time(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with ddtrace.tracer.trace(
            name=f"{__name__}.get_rescheduled_from_previous_appointment_time_appointment_schema"
        ):
            dd_metric_name = "api.appointments.schemas.appointments.reschedule_history_appointment_schema"
            return get_rescheduled_from_previous_appointment_time(
                obj, self.context, dd_metric_name
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


class AppointmentCreateSchemaV3(AppointmentSchemaV3):
    product_id = marshmallow_fields.Integer(required=True)
    scheduled_start = MavenDateTime(required=True)
    need_id = IntegerWithDefaultV3(dump_default=0, load_default=0, required=False)


class AppointmentRescheduleSchemaV3(AppointmentSchemaV3):
    product_id = marshmallow_fields.Integer(required=False)
    scheduled_start = MavenDateTime(required=True)
    need_id = IntegerWithDefaultV3(dump_default=0, load_default=0, required=False)


class MinimalUserProfilesSchemaV3(SchemaV3):
    practitioner = marshmallow_fields.Method("get_practitioner_profile")

    def get_practitioner_profile(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        schema = PractitionerProfileSchemaV3(only=["verticals"])
        if "user" not in self.context:
            return {}
        profiles = self.context["user"].profiles_map

        if not profiles.get(ROLES.practitioner):
            return {}

        profile = profiles[ROLES.practitioner]

        return schema.dump(profile)


class MinimalPractitionerSchemaV3(SchemaV3):
    id = IntegerWithDefaultV3(default=0)
    profiles = marshmallow_fields.Method("get_profiles")
    first_name = StringWithDefaultV3(default="")
    last_name = StringWithDefaultV3(default="")
    name = marshmallow_fields.Method("get_name")
    image_url = marshmallow_fields.Method("get_image_url")

    def get_profiles(self, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not hasattr(user, "profiles_map"):
            return None
        profiles = user.profiles_map
        schema = MinimalUserProfilesSchemaV3(context={"user": user})
        return schema.dump(profiles)

    def get_name(self, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not hasattr(user, "full_name"):
            return None
        return user.full_name

    def get_image_url(self, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not hasattr(user, "avatar_url"):
            return None
        return user.avatar_url


class MinimalProductSchemaV3(SchemaV3):
    practitioner = marshmallow_fields.Nested(
        MinimalPractitionerSchemaV3(only=["profiles", "name", "image_url"])
    )


class AppointmentsMetaSchemaV3(SchemaV3):
    schedule_event_ids = CSVIntegerField()
    scheduled_start = MavenDateTime()
    scheduled_end = MavenDateTime()


class MinimalAppointmentSchemaV3(SchemaV3):
    id = marshmallow_fields.Method("get_obfuscated_id")
    appointment_id = marshmallow_fields.Method("get_appointment_id")
    privacy = PrivacyOptionsField()
    scheduled_start = MavenDateTime()
    scheduled_end = MavenDateTime()
    cancelled_at = MavenDateTime()
    product = marshmallow_fields.Nested(MinimalProductSchemaV3)
    member = marshmallow_fields.Method("get_member")
    pre_session = marshmallow_fields.Nested(SessionMetaInfoSchemaV3)
    post_session = marshmallow_fields.Nested(SessionMetaInfoSchemaV3)
    repeat_patient = marshmallow_fields.Boolean()
    state = StringWithDefaultV3(default="")
    privilege_type = marshmallow_fields.Method("get_privilege_type")
    state_match_type = marshmallow_fields.Method("get_state_match_type")
    need = marshmallow_fields.Nested(NeedLiteSchemaV3)
    rescheduled_from_previous_appointment_time = marshmallow_fields.Method(
        "get_rescheduled_from_previous_apt_time"
    )

    def get_appointment_id(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not hasattr(obj, "id"):
            return None
        return obj.id

    def get_privilege_type(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not hasattr(obj, "privilege_type"):
            return None
        return obj.privilege_type

    def get_state_match_type(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not hasattr(obj, "state_match_type") or obj.state_match_type is None:
            return None
        return obj.state_match_type.value

    def get_obfuscated_id(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not hasattr(obj, "id"):
            return None
        return obfuscate_appointment_id(obj.id)

    def get_member(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        cu = self.context.get("user")
        fields = []

        if not hasattr(obj, "practitioner"):
            return None

        if cu == obj.practitioner:
            fields.append("country")
            if not obj.is_anonymous:
                fields.extend(("image_url", "name", "created_at"))
        elif cu == obj.member:
            fields.extend(("name", "image_url", "country"))

        if any(fields):
            schema = UserInAppointmentSchemaV3(
                only=fields, context=dict(include_country_info=True)
            )
            return schema.dump(obj.member)
        else:
            return {}

    @ddtrace.tracer.wrap()
    def get_rescheduled_from_previous_apt_time(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with ddtrace.tracer.trace(
            name=f"{__name__}.get_rescheduled_from_previous_appointment_time_minimal_appointment_schema"
        ):
            dd_metric_name = "api.appointments.schemas.appointments.reschedule_history_minimal_appointment_schema"
            return get_rescheduled_from_previous_appointment_time(
                obj, self.context, dd_metric_name
            )


class MinimalAppointmentsSchemaV3(PaginableOutputSchemaV3):
    meta = marshmallow_fields.Nested(AppointmentsMetaSchemaV3)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchema" defined the type as "Raw")
    data = NestedWithDefaultV3(MinimalAppointmentSchemaV3, many=True, default=[])  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchema" defined the type as "Raw")


class AppointmentsSchemaV3(PaginableOutputSchemaV3):
    data = NestedWithDefaultV3(AppointmentSchemaV3, many=True, default=[])  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchema" defined the type as "Raw")
    meta = marshmallow_fields.Nested(AppointmentsMetaSchemaV3)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchema" defined the type as "Raw")


class AppointmentGetSchemaV3(PaginableArgsSchemaV3):
    schedule_event_ids = CSVIntegerField(required=False)
    scheduled_start = MavenDateTime()
    scheduled_start_before = MavenDateTime()
    scheduled_end = MavenDateTime()
    member_id = IntegerWithDefaultV3(default=0)
    practitioner_id = IntegerWithDefaultV3(default=0)
    exclude_statuses = CSVStringField(required=False)
    purposes = CSVStringField(required=False)
    order_direction = OrderDirectionField(
        default="asc", required=False, dump_default="asc", load_default="asc"
    )
    minimal = marshmallow_fields.Boolean(required=False)


class PractitionerNotesProductSchemaV3(SchemaV3):
    practitioner = NestedWithDefaultV3(MinimalPractitionerSchemaV3, dump_default=[])  # type: ignore[assignment]


class PractitionerNotesAppointmentSchemaV3(MavenSchemaV3):
    id = marshmallow_fields.Method("get_obfuscated_id")
    product = NestedWithDefaultV3(PractitionerNotesProductSchemaV3)
    pre_session = NestedWithDefaultV3(SessionMetaInfoSchemaV3)
    post_session = NestedWithDefaultV3(SessionMetaInfoSchemaV3)
    scheduled_start = MavenDateTime()
    scheduled_end = MavenDateTime()
    state = marshmallow_fields.String()
    cancelled_by = marshmallow_fields.Method("get_cancelled_by")
    need = NestedWithDefaultV3(NeedLiteSchemaV3, default="")
    structured_internal_note = marshmallow_fields.Method("get_structured_internal_note")
    provider_addenda = marshmallow_fields.Method("get_provider_addenda")

    def get_obfuscated_id(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not hasattr(obj, "id"):
            return None
        return obfuscate_appointment_id(obj.id)

    def get_cancelled_by(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not hasattr(obj, "cancelled_by_user_id"):
            return None
        if obj.cancelled_by_user_id is None:
            return None
        elif obj.cancelled_by_user_id == obj.member_id:
            return CancelledByTypes.MEMBER
        elif obj.cancelled_by_user_id == obj.practitioner_id:
            return CancelledByTypes.PROVIDER
        else:
            return CancelledByTypes.OTHER

    def get_structured_internal_note(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with ddtrace.tracer.trace(name=f"{__name__}.get_structured_internal_note"):
            question_sets_json, recorded_answers_json = [], []
            questionnaire_json, recorded_answer_set_json = None, None

            if not hasattr(obj, "id"):
                return None

            appointment_id = obj.id
            data = self.context.get("structured_internal_note", {}).get(
                appointment_id, {}
            )

            recorded_answer_set = data.get("recorded_answer_set")
            recorded_answers = data.get("recorded_answers")
            if recorded_answer_set:
                recorded_answer_set_json = RecordedAnswerSetSchemaV3().dump(
                    recorded_answer_set
                )

                if recorded_answer_set.recorded_answers:
                    recorded_answers_json = RecordedAnswerSchemaV3(many=True).dump(
                        recorded_answer_set.recorded_answers
                    )
            elif recorded_answers:
                # Recorded answers that were created before the concept of recorded answer sets
                # being linked to appointments will be directly attached to the appointment themselves
                recorded_answers_json = RecordedAnswerSchemaV3(many=True).dump(
                    recorded_answers
                )

            questionnaire = data.get("questionnaire")
            if questionnaire:
                questionnaire_json = QuestionnaireSchemaV3().dump(questionnaire)
                question_sets_json = QuestionSetSchemaV3(many=True).dump(
                    questionnaire.question_sets
                )

            return {
                "question_sets": question_sets_json,
                "recorded_answers": recorded_answers_json,
                "questionnaire": questionnaire_json,
                "recorded_answer_set": recorded_answer_set_json,
            }

    def get_provider_addenda(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        with ddtrace.tracer.trace(name=f"{__name__}.get_provider_addenda"):
            user = self.context.get("user")
            if not user:
                return None

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
            questionnaire_json = QuestionnaireSchemaV3().dump(questionnaire)
            provider_addenda_json = ProviderAddendumSchemaV3(many=True).dump(
                provider_addenda
            )
            return {
                "questionnaire": questionnaire_json,
                "provider_addenda": provider_addenda_json,
            }
