from __future__ import annotations

import copy
import datetime
from collections.abc import Iterable
from typing import Any, Dict, Mapping, Union

from dateutil.parser import parse
from flask import request
from flask_babel import lazy_gettext
from flask_restful import abort
from maven import feature_flags
from redset.exceptions import LockTimeout
from sqlalchemy import exc
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.orm.exc import NoResultFound

import configuration
from appointments.models.appointment import Appointment
from appointments.models.appointment_meta_data import AppointmentMetaData
from appointments.models.constants import APPOINTMENT_STATES, PRIVACY_CHOICES
from appointments.models.needs_and_categories import Need, NeedAppointment
from appointments.schemas.appointments import (
    AppointmentSchema,
    PatchAppointmentRequestSchema,
)
from appointments.services.common import deobfuscate_appointment_id, get_platform
from appointments.services.schedule import update_practitioner_profile_next_availability
from appointments.tasks.appointment_notifications import (
    notify_rx_info_entered,
    send_slack_cancellation,
)
from appointments.tasks.appointments import appointment_completion
from appointments.utils.flask_redis_ext import (
    APPOINTMENT_DEFAULT_TTL,
    APPOINTMENT_REDIS,
    cache_response,
    invalidate_cache,
)
from appointments.utils.redis_util import invalidate_cache as invalidate
from authz.models.roles import ROLES, Role
from authz.services.permission import only_member_or_practitioner
from common import stats
from common.services.api import AuthenticatedResource
from dosespot.constants import (
    DOSESPOT_GLOBAL_CLINIC_ID_V2,
    DOSESPOT_GLOBAL_CLINIC_KEY_V2,
)
from dosespot.resources.dosespot_api import DoseSpotAPI
from l10n.utils import message_with_enforced_locale
from messaging.models.messaging import Channel, Message
from messaging.services.zendesk import PostSessionZendeskTicket
from models.profiles import MemberProfile
from models.questionnaires import (
    COACHING_NOTES_COACHING_PROVIDERS_OID,
    Question,
    Questionnaire,
    QuestionSet,
    RecordedAnswer,
    RecordedAnswerSet,
    integer_id_or_none,
)
from providers.service.provider import ProviderService
from storage.connection import db
from utils import braze_events, cache
from utils.exceptions import DraftUpdateAttemptException
from utils.flag_groups import APPOINTMENT_ALLOW_RX_OVERWRITE
from utils.launchdarkly import user_context
from utils.log import logger
from utils.marshmallow_experiment import marshmallow_experiment_enabled
from utils.service_owner_mapper import service_ns_team_mapper

log = logger(__name__)

APPOINTMENT_CANCELLED_EDIT_ERROR_MESSAGE = lazy_gettext(
    "appointment_cancelled_edit_error_message"
)
APPOINTMENT_CANNOT_CANCEL_ERROR_MESSAGE = lazy_gettext(
    "appointment_cannot_cancel_error_message"
)
APPOINTMENT_DISCONNECTED_AT_PROCESSING_ERROR_MESSAGE = lazy_gettext(
    "appointment_disconnected_at_processing_error_message"
)
APPOINTMENT_SURVEY_DISCONNECTED_AT_PROCESSING_ERROR_MESSAGE = lazy_gettext(
    "appointment_servey_disconnected_at_processing_error_message"
)
PRESCRIPTION_MISSING_DATA_ERROR_MESSAGE = lazy_gettext(
    "prescription_missing_data_error_message"
)
ANONYMOUS_APPOINTMENT_PHARMACY_ERROR_MESSAGE = lazy_gettext(
    "anonymous_appointment_pharmacy_error_message"
)
PRACTITIONER_NOT_ENABLED_ERROR_MESSAGE = lazy_gettext(
    "practitioner_not_enabled_error_message"
)


class AppointmentResource(AuthenticatedResource):
    def redis_cache_key(self, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return f"appointment_details:{self.user.id}:{kwargs.get('appointment_id')}"

    def redis_tags(self, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return [
            f"appointment_data:{kwargs.get('appointment_id')}",
            f"user_appointments:{self.user.id}",
        ]

    def experiment_enabled(self, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return marshmallow_experiment_enabled(
            "experiment-enable-appointments-redis-cache",
            self.user.esp_id,
            self.user.email,
            default=False,
        )

    @cache_response(
        ttl=APPOINTMENT_DEFAULT_TTL * 2,
        redis_name=APPOINTMENT_REDIS,
        namespace="appointment_detail",
    )
    def get(self, appointment_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        schema = AppointmentSchema()
        schema.context["user"] = self.user
        return schema.dump(self._get_appointment(appointment_id)).data

    @invalidate_cache(redis_name=APPOINTMENT_REDIS, namespace="appointment_detail")
    def put(self, appointment_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.init_timer()
        appointment = self._get_appointment(appointment_id)  # no joinedloads here
        request_json = request.json if request.is_json else None
        return self._update_appointment(appointment, request_json or request.form)

    @invalidate_cache(redis_name=APPOINTMENT_REDIS, namespace="appointment_detail")
    def patch(self, appointment_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        Partial update to a given appointment.

        Note that this endpoint does not accept many parameters, as its use right now
        is very limited in scope. For more robust edits to appointments, use  the
        corresponding PUT endpoint

        :param notes: pre_session notes, saved in database as `client_notes`
        :param need_id: the `need` that the appointment was booked with
        """
        self.init_timer()
        appointment = self._get_appointment(appointment_id)
        request_json = request.json if request.is_json else None
        patch_request = PatchAppointmentRequestSchema().load(request_json)
        to_update = copy.deepcopy(patch_request)

        if "need_id" in patch_request:
            # Remove need_id from to_update, as this field
            # is handled with a separate update
            del to_update["need_id"]

            if patch_request["need_id"] is None:
                appointment.need = None
            else:
                try:
                    (
                        db.session.query(Need)
                        .filter_by(id=patch_request["need_id"])
                        .one()
                    )
                except NoResultFound:
                    log.error(
                        "Invalid need_id in PATCH /appointments",
                        appointment_id=appointment.id,
                        need_id=patch_request["need_id"],
                    )
                    abort(404, message="Invalid need_id")

                log.info(
                    "Update appointment's need",
                    appointment_id=appointment.id,
                    need_id=patch_request["need_id"],
                )

                need_id = int(patch_request["need_id"])
                upsert_query = (
                    insert(NeedAppointment.__table__)
                    .values(need_id=need_id, appointment_id=appointment.id)
                    .on_duplicate_key_update(
                        need_id=need_id, appointment_id=appointment.id
                    )
                )
                # This write attempt is very vulnerable to deadlock for some reason,
                # perhaps due to the multiple uniqueness constraints on the table.
                # Attempt a few times before giving up
                MAX_ATTEMPTS = 5
                for attempt in range(MAX_ATTEMPTS):
                    try:
                        db.session.execute(upsert_query)
                        break
                    except exc.OperationalError as e:
                        if "Deadlock" not in str(e) or attempt == MAX_ATTEMPTS - 1:
                            raise
                        db.session.rollback()

        allow_rx_overwrite = feature_flags.bool_variation(
            flag_key=APPOINTMENT_ALLOW_RX_OVERWRITE,
            default=False,
        )
        allow_rx_update = allow_rx_overwrite or (appointment.rx_written_at is None)
        if (
            "rx_written_at" in patch_request
            and patch_request.get("rx_written_at") is not None
            and allow_rx_update
            and self.user == appointment.practitioner
        ):
            to_update["rx_written_at"] = datetime.datetime.utcnow()
            # TODO: consider checking whether provider is dosespot-enabled first
            appointment.json["rx_written_via"] = patch_request["rx_written_via"]
            to_update["json"] = appointment.json
            log.info(
                "Update rx_written_at and rx_written_via", appointment_id=appointment.id
            )
        elif "rx_written_at" in patch_request:
            # Remove rx_written_at from to_update if the previous if conditions are not
            # met: we don't want to update this field in the appointment model
            del to_update["rx_written_at"]

        # Remove rx_written_via from to_update, as this field will be updated
        # in json if this field exists
        if "rx_written_via" in patch_request:
            del to_update["rx_written_via"]

        with db.session.no_autoflush:
            # Update fields on `appointment` model directly
            if to_update:
                count_rows_affected = (
                    db.session.query(Appointment)
                    .filter_by(id=appointment.id)
                    .update(to_update, synchronize_session="fetch")
                )
                log.info(
                    "Updated appointment",
                    appointment_id=appointment.id,
                    to_update=to_update,
                    count_rows_affected=count_rows_affected,
                )

        db.session.commit()
        return {"success": True}

    def _get_appointment(self, appointment_id) -> Appointment:  # type: ignore[return,no-untyped-def] # Missing return statement #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        appointment_id = deobfuscate_appointment_id(appointment_id)

        try:
            appointment = (
                db.session.query(Appointment)
                .filter(Appointment.id == appointment_id)
                .one()
            )
        except NoResultFound:
            abort(404, message="Invalid appointment ID")

        appointment = only_member_or_practitioner(self.user, [appointment])

        if appointment:
            return appointment[0]
        else:
            abort(403, message="Cannot view that appointment!")

    def _update_timestamp(
        self,
        args: dict,
        fields: Iterable,
        appointment: Appointment,
    ) -> None:
        """
        Iterate over fields (e.g.) (`member_ended_at`, `member_started_at`)
        and set them to the updated value if the updated value is present and in
        the orginal appointment the value is null. If the `x_ended_at` value
        is present and the `x_started_at` value is not present, set the
        `x_started_at` value to be UTC now as the default value (x here is either
        member or practitioner).
        """
        for field in fields:
            if args.get(field) and getattr(appointment, field) is None:
                setattr(appointment, field, args.get(field))
                self._track_platform_info(appointment, field)

        if (
            self.user == appointment.member
            and (appointment.member_ended_at or args.get("member_ended_at"))
            and (appointment.member_started_at is None)
            and (args.get("member_started_at") is None)
        ):
            appointment.member_started_at = datetime.datetime.utcnow()
            self._track_platform_info(appointment, "member_started_at")

        if (
            self.user == appointment.practitioner
            and (appointment.practitioner_ended_at or args.get("practitioner_ended_at"))
            and (
                appointment.practitioner_started_at is None
                and args.get("practitioner_started_at") is None
            )
        ):
            appointment.practitioner_started_at = datetime.datetime.utcnow()
            self._track_platform_info(appointment, "practitioner_started_at")

    def _update_appointment(self, appointment: Appointment, incoming_changes: dict):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        AS = APPOINTMENT_STATES
        editable_states = (
            AS.scheduled,
            AS.overdue,
            AS.incomplete,
            AS.overflowing,
            AS.occurring,
        )
        cancellable_states = (AS.scheduled, AS.overdue)

        reconnecting_states = (
            AS.scheduled,
            AS.overdue,
            AS.occurring,
            AS.overflowing,
        )

        # TODO(MPC-3518): Remove code and feature flag
        deprecate_appointment_save_notes_enabled = feature_flags.bool_variation(
            "release-mpractice-deprecate-appointment-save-notes",
            user_context(self.user),
            default=False,
        )

        schema = AppointmentSchema()
        schema.context["user"] = self.user
        # the deserialized AppointmentSchema data for the incoming changes
        args = schema.load(incoming_changes).data

        remove_extra_commits = feature_flags.bool_variation(
            flag_key="experiment-remove-extra-appointments-commits",
            context=user_context(self.user),
            default=False,
        )

        if appointment.state == AS.cancelled and not (
            self._has_cancellation_survey_recorded_answers(args, appointment)
        ):
            log.info(
                "Attempt to update cancelled appointment rejected.",
                appointment_id=appointment.id,
                member_id=appointment.member.id,
                practitioner_id=appointment.practitioner.id,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "id"
            )
            abort(400, message=str(APPOINTMENT_CANCELLED_EDIT_ERROR_MESSAGE))

        if args.get("cancelled_at") and appointment.state in cancellable_states:
            try:
                appointment.cancel(
                    self.user.id,
                    args.get("cancelled_note"),
                    skip_commit=remove_extra_commits,
                )
            except Exception as e:
                log.error(
                    "Error cancelling appointment",
                    error=e.__class__.__name__,
                    exception=e,
                    appointment_id=appointment.id,
                )
                abort(400, message="Error cancelling appointment")

            if appointment.cancelled_at:
                if remove_extra_commits:
                    db.session.flush()
                else:
                    db.session.commit()
                self.audit("appointment_cancel", appointment_id=appointment.id)

                log.info("Cancelled appointment", appointment_id=appointment.id)

                # update practitioner availability
                profile = appointment.product.practitioner.practitioner_profile
                update_practitioner_profile_next_availability(
                    profile, skip_commit=remove_extra_commits
                )
                # notify #bookings
                send_slack_cancellation(appointment)
                self.timer("cancel_time")
            else:
                db.session.commit()
                log.warning(
                    "Appointment could not be cancelled", appointment_id=appointment.id
                )
                abort(400, message=str(APPOINTMENT_CANNOT_CANCEL_ERROR_MESSAGE))

        elif (
            incoming_changes.get("practitioner_disconnected_at", None)
            or incoming_changes.get("member_disconnected_at", None)
        ) and appointment.state in reconnecting_states:
            try:
                self._process_disconnected_data(incoming_changes, appointment)
            except Exception as e:
                log.warning(
                    "Error processing disconnected data",
                    error=e.__class__.__name__,
                    exception=e,
                    appointment_id=appointment.id,
                )
                abort(
                    400,
                    message=str(APPOINTMENT_DISCONNECTED_AT_PROCESSING_ERROR_MESSAGE),
                )

            try:
                self._process_member_rating_disconnections(args, appointment)
            except Exception as e:
                log.warning(
                    "Error processing disconnected data member survey results",
                    error=e.__class__.__name__,
                    exception=e,
                    appointment_id=appointment.id,
                )
                abort(
                    400,
                    message=str(
                        APPOINTMENT_SURVEY_DISCONNECTED_AT_PROCESSING_ERROR_MESSAGE
                    ),
                )

            db.session.add(appointment)
            if feature_flags.bool_variation(
                "release-appointments-multithreading-500s",
                default=False,
            ):
                db.session.flush()
                dumped = schema.dump(appointment).data
                self.audit("appointment_edit", appointment_id=appointment.id)
                db.session.commit()
                return dumped
            else:
                db.session.add(appointment)
                db.session.commit()
                self.audit("appointment_edit", appointment_id=appointment.id)
                return schema.dump(appointment).data

        elif appointment.state in editable_states:
            if self.user == appointment.member:
                self._update_timestamp(
                    args, Appointment.MEMBER_ALLOWED_TIMESTAMPS, appointment
                )
            if self.user == appointment.practitioner:
                self._update_timestamp(
                    args, Appointment.PRACTITIONER_ALLOWED_TIMESTAMPS, appointment
                )
                if (
                    args.get("phone_call_at") is not None
                    and appointment.phone_call_at is None
                ):
                    now = datetime.datetime.utcnow()
                    appointment.phone_call_at = now
                    appointment.member_ended_at = now
                    appointment.practitioner_ended_at = now

            # commit here to capture an appointment getting started or ended even if something else about the update fails.
            if remove_extra_commits:
                db.session.flush()
            else:
                db.session.commit()

        allow_rx_overwrite = feature_flags.bool_variation(
            flag_key=APPOINTMENT_ALLOW_RX_OVERWRITE,
            default=False,
        )
        allow_rx_update = allow_rx_overwrite or (appointment.rx_written_at is None)
        if (
            (args.get("rx_written_at") is not None)
            and allow_rx_update
            and (self.user == appointment.practitioner)
        ):
            appointment.rx_written_at = datetime.datetime.utcnow()

            # TODO: make sure practitioner is DS enables if its not call
            appointment.json["rx_written_via"] = args["rx_written_via"]

        # note: this silences some possible errors when trying to set a pharmacy on an invalid appointment
        # note: but it's consistent with the appointment_post_creation logic
        if args.get("prescription_info", {}).get(
            "pharmacy_id"
        ) and ProviderService().enabled_for_prescribing(appointment.practitioner_id):
            self._check_and_set_pharmacy(
                appointment, args["prescription_info"]["pharmacy_id"]
            )
            self.timer("prescription_time")

        self._update_post_session_send_appointment_note_message(
            args,
            appointment,
            deprecate_appointment_save_notes_enabled,
        )

        if args.get("ratings") is not None and (self.user == appointment.member):
            appointment.json["ratings"] = args["ratings"]

        if not deprecate_appointment_save_notes_enabled:
            # process the internal note
            self._update_internal_note(
                args, appointment, skip_commit=remove_extra_commits
            )

        # process the member survey results
        self._process_member_rating(args, appointment)

        # process the cancellation survey recorded_answers if there is any
        if self._has_cancellation_survey_recorded_answers(args, appointment):
            self._process_cancellation_survey_answers(args, appointment)
            stats.increment(
                metric_name="api.appointments.resource.appointment.cancellation_survey_recorded_answers",
                tags=["variant:recorded_answers"],
                pod_name=stats.PodNames.VIRTUAL_CARE,
            )

        db.session.add(appointment)
        # Explicitly handle bi-directional relationship for the appointment model
        invalidate(
            tags=[
                f"user_appointments:{appointment.member_id}",
                f"user_appointments:{appointment.practitioner_id}",
            ]
        )
        if feature_flags.bool_variation(
            "release-appointments-multithreading-500s",
            default=False,
        ):
            db.session.flush()
            self.timer("commit_time")
            dumped = schema.dump(appointment).data
            self.audit("appointment_edit", appointment_id=appointment.id)
            db.session.commit()
            # This is here so the DB commit is done when the task is started
            if appointment.state == APPOINTMENT_STATES.payment_pending:
                self._appointment_completion(
                    appointment=appointment,
                    user_id=self.user.id,
                )
            return dumped
        else:
            db.session.commit()
            self.timer("commit_time")

            # This is here so the DB commit is done when the task is started
            if appointment.state == APPOINTMENT_STATES.payment_pending:
                self._appointment_completion(
                    appointment=appointment,
                    user_id=self.user.id,
                )

            self.audit("appointment_edit", appointment_id=appointment.id)
            return schema.dump(appointment).data

    def _process_disconnected_data(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, args: Dict[str, Any], appointment: Appointment
    ):
        """
        Processes the disconnected payload data.
        """
        if self.user == appointment.practitioner:
            args_disconnected_at = args.get("practitioner_disconnected_at", None)
            key = "practitioner_disconnect_times"
        elif self.user == appointment.member:
            args_disconnected_at = args.get("member_disconnected_at", None)
            key = "member_disconnect_times"

        if args_disconnected_at:
            # check to see if the value is a string and if so parse it as datetime
            if isinstance(args_disconnected_at, str):
                disconnected_at = parse(args_disconnected_at)

            if not isinstance(disconnected_at, datetime.date) or not isinstance(
                disconnected_at, datetime.datetime
            ):
                log.error(
                    "Unable to update appointment with disconnected data - invalid type - expected date or datetime",
                    appointment_id=appointment.id,
                )
                raise TypeError(
                    "Unable to process disconnected data - value must be a date or datetime"
                )

            # use the x_disconnected_at values as the x_started_at values if the x_started_at values haven't been set
            if self.user == appointment.member and not appointment.member_started_at:
                appointment.member_started_at = disconnected_at
            if (
                self.user == appointment.practitioner
                and not appointment.practitioner_started_at
            ):
                appointment.practitioner_started_at = disconnected_at

            self._add_or_update_disconnect_times(
                appointment,
                key=key,
                value=disconnected_at,
            )

    def _process_member_rating_disconnections(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, args: Mapping[str, Any], appointment: Appointment
    ):
        """
        Processes the member survey ratings (e.g. survey results) for disconnections.

        Deletes all existing recorded answers and creates new ones.

        This is a special case in which we are going to delete all member survey results, regardless
        of whether we have received any member rating recorded answers!
        """
        if self.user != appointment.member:
            return

        log.info(
            "Processing member survey results . . . ",
            appointment_id=appointment.id,
            disconnections=True,
        )

        recorded_answers = []
        if args.get("member_rating"):
            recorded_answers = args["member_rating"]["recorded_answers"]

        # capture all of the question ids based on the questionnaires to ensure
        # all existing recorded answers are deleted
        # this should be able to get refactored out once we use recorded answer sets
        questions = (
            db.session.query(Question)
            .join(QuestionSet)
            .join(Questionnaire)
            .filter(Questionnaire.roles.any(Role.name == ROLES.member))
            .all()
        )

        question_ids = None
        if questions:
            question_ids = [question.id for question in questions]

        if not question_ids:
            log.warning(
                "Unable to process member survey results - question ids are not available",
                appointment_id=appointment.id,
            )
            return

        # delete the existing recorded answers so we can create new ones
        # currently unable to use RecordedAnswerSet
        # bug: RecordedAnswerSet is created but the child RecordedAnswer(s) have no appointment_id

        # filter by question_id so we do not delete unintended recorded answers
        RecordedAnswer.query.filter(
            RecordedAnswer.appointment_id == appointment.id,
            RecordedAnswer.user_id == appointment.member.id,
            RecordedAnswer.question_id.in_(question_ids),
        ).delete(synchronize_session="fetch")

        if recorded_answers:
            log.info(
                "Creating and adding new member recorded answers",
                appointment_id=appointment.id,
            )
            for ra in recorded_answers:
                db.session.add(
                    RecordedAnswer.create(
                        attrs=ra,
                        user_id=appointment.member.id,
                        appointment_id=appointment.id,
                    )
                )

    def _process_member_rating(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        args: Mapping[str, Any],
        appointment: Appointment,
    ):
        """
        Processes the member survey ratings (e.g. survey results).

        Due to the way some of the clients send in the member survey results, we
        have to maintain this way of persisting survey results (e.g. only save the recorded
        answers for questions that haven't had any recorded answers).

        Verify with clients before refactoring, especially iOS.
        """
        if self.user != appointment.member:
            return

        log.info(
            "Processing member survey results . . . ",
            appointment_id=appointment.id,
        )

        # check to see if this was a previously disconnected appointment
        # if so, process the member survey results as a disconnection
        if (
            args.get("member_ended_at", None)
            or args.get("member_disconnected_at", None)
        ) and appointment.json.get("member_disconnect_times", None):
            self._process_member_rating_disconnections(args, appointment)
            return

        if args.get("member_rating"):
            recorded_answers = args["member_rating"]["recorded_answers"]
            # only save the ones that haven't been recorded for a question before
            existing_recorded_answer_question_ids = [
                ra.question_id for ra in appointment.recorded_answers
            ]
            for ra in recorded_answers:
                if (
                    integer_id_or_none(ra, "question_id")
                    not in existing_recorded_answer_question_ids
                ):
                    db.session.add(
                        RecordedAnswer.create(
                            attrs=ra,
                            user_id=appointment.member.id,
                            appointment_id=appointment.id,
                        )
                    )

    def _process_cancellation_survey_answers(
        self, incoming_changes: dict[str, Any], appointment: Appointment
    ) -> None:
        """Process the cancellation survey recorded answers.

        Parameters
        ----------
        incoming_changes: dict[str, Any]
            The deserialized AppointmentSchema data for the incoming changes.

        appointment: Appointment
            The current appointment object read from the database.
        """
        appointment_id = appointment.id
        log.info(f"Processing cancellation survey results for {appointment_id}")

        surveys: dict[str, Any] | None = incoming_changes.get("surveys")
        if not surveys:
            return None

        cancellation_survey: dict[str, Any] | None = surveys.get("cancellation_survey")
        if not cancellation_survey:
            return None

        recorded_answers: list[dict] | None = cancellation_survey.get(
            "recorded_answers"
        )
        if not recorded_answers:
            return None

        for ra in recorded_answers:
            db.session.add(
                RecordedAnswer.create(
                    attrs=ra,
                    user_id=appointment.member.id,
                    appointment_id=appointment.id,
                )
            )

    def _appointment_completion(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        appointment: Appointment,
        user_id: int = None,  # type: ignore[assignment] # Incompatible default for argument "user_id" (default has type "None", argument has type "int")
    ):
        """
        Invokes a function that handles appointment completion activities.
        """
        self.audit(
            "appointment_completion", appointment_id=appointment.id, user_id=user_id
        )

        try:
            with cache.RedisLock(
                f"appointment_completion_{appointment.id}", timeout=0.1, expires=1
            ):
                service_ns_tag = "appointments"
                team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
                appointment_completion.delay(
                    appointment.id,
                    user_id=user_id,
                    service_ns=service_ns_tag,
                    team_ns=team_ns_tag,
                )
        except LockTimeout as e:
            log.warning(
                "Lock timeout while attempting to complete appointment",
                error=e.__class__.__name__,
                exception=e,
                appointment_id=appointment.id,
            )
        except Exception as e:
            log.warning(
                "Error completing appointment",
                error=e.__class__.__name__,
                exception=e,
                appointment_id=appointment.id,
            )

        self.timer("payment_time")

    def _update_internal_note(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        args: Mapping[str, Any],
        appointment: Appointment,
        skip_commit: bool = False,
    ):
        """
        Updates the structured internal note.
        """
        self.timer("notes_time")

        if (
            args.get("structured_internal_note")
            and self.user == appointment.practitioner
        ):
            recorded_answer_set_attrs = args["structured_internal_note"].get(
                "recorded_answer_set"
            )
            if recorded_answer_set_attrs:
                recorded_answer_set_attrs["appointment_id"] = appointment.id

                if "recorded_answers" in recorded_answer_set_attrs and any(
                    len(ra.get("text", "")) > 6000
                    for ra in recorded_answer_set_attrs["recorded_answers"]
                    if ra.get("text")
                ):
                    abort(
                        422,
                        message="Text cannot be greater than 6000 characters",
                    )

                try:
                    RecordedAnswerSet.create_or_update(recorded_answer_set_attrs)
                    if skip_commit:
                        db.session.flush()
                    else:
                        db.session.commit()
                except DraftUpdateAttemptException as e:
                    log.error(
                        "Error creating/updating recorded answer set",
                        error=e.__class__.__name__,
                        exception=e,
                        appointment_id=appointment.id,
                    )
                    abort(409, message=str(e))
                except exc.SQLAlchemyError as sqlalchemy_error:
                    log.error(
                        "Error with SQLAlchemy",
                        error=sqlalchemy_error.__class__.__name__,
                        exception=sqlalchemy_error,
                        appointment_id=appointment.id,
                    )
                    message = "Something went wrong when recording your answers, please try again."
                    abort(409, message=message)
                questionnaire_id = recorded_answer_set_attrs.get(
                    "questionnaire_id", None
                )
                questionnaire = (
                    Questionnaire.query.filter(
                        Questionnaire.id == questionnaire_id
                    ).first()
                    if questionnaire_id
                    else None
                )
                log.debug("structured_internal_note", q=questionnaire)
                log_answer_sets(questionnaire=questionnaire, deprecated_client=False)

            else:
                # The client hasn't updated and is sending answers the old way
                # (on their own rather than part of a recorded answer set).
                recorded_answers = args["structured_internal_note"].get(
                    "recorded_answers"
                )

                if recorded_answers:
                    parentless_recorded_answers = appointment.recorded_answers

                    # If recorded answers exist but no recorded answer sets exist,
                    # they're from before draft capabilities were added.
                    # Maybe weird UX, but silently fail to update.
                    # In the (hopefully very near) future, we'll run a migration to give
                    # them parents with draft=false.
                    if not parentless_recorded_answers:
                        log.info(
                            "Constructing recorded answer set from deprecated recorded_answers attribute",
                            user_id=self.user.id,
                        )
                        coaching_notes_coaching_providers = Questionnaire.query.filter(
                            Questionnaire.oid == COACHING_NOTES_COACHING_PROVIDERS_OID
                        ).first()
                        # Should always exist, but just being cautious.
                        if coaching_notes_coaching_providers:
                            attrs = {
                                "submitted_at": datetime.datetime.now(),
                                "source_user_id": self.user.id,
                                "draft": False,
                                "appointment_id": appointment.id,
                                "recorded_answers": recorded_answers,
                                "questionnaire_id": coaching_notes_coaching_providers.id,
                            }
                            RecordedAnswerSet.create_or_update(attrs)
                            log_answer_sets(
                                questionnaire=coaching_notes_coaching_providers,
                                deprecated_client=True,
                            )
        return

    # TODO(MPC-3518): Remove code and feature flag, keeping pre-session notes logic
    def _update_post_session_send_appointment_note_message(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        args: Mapping[str, Any],
        appointment: Appointment,
        deprecate_appointment_save_notes_enabled,
    ):
        """
        Updates the client notes and calls function to update post session.

        May send the post appointment note message if applicable.
        """
        if (
            args.get("pre_session", {}).get("notes") is not None
        ) and self.user == appointment.member:
            appointment.client_notes = args["pre_session"]["notes"]

        if not deprecate_appointment_save_notes_enabled:
            post_session_draft = args.get("post_session", {}).get("draft", False)
            post_session_notes = args.get("post_session", {}).get("notes")
            if (
                post_session_notes or post_session_draft
            ) and self.user == appointment.practitioner:
                result = appointment.update_post_session(
                    post_session_notes, post_session_draft
                )
                db.session.add(result.post_session)

                if result.should_send:
                    self._send_post_appointment_note_message(
                        appointment, result.post_session
                    )
        return

    # TODO(MPC-3518): Deprecate code with removal of DEPRECATE_APPOINTMENT_SAVE_NOTES feature flag
    # function recreated as send_post_appointment_message
    def _send_post_appointment_note_message(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, appointment: Appointment, post_session: AppointmentMetaData
    ):
        if post_session.draft:
            return

        config = configuration.get_api_config()
        channel = Channel.get_or_create_channel(
            appointment.practitioner, [appointment.member]  # type: ignore[arg-type] # Argument 1 to "get_or_create_channel" of "Channel" has incompatible type "Optional[User]"; expected "User"
        )

        message_body = message_with_enforced_locale(
            user=appointment.member,
            text_key="member_post_appointment_note_message",
        ).format(
            member_first_name=appointment.member.first_name,
            post_session_content=post_session.content,
            base_url=config.common.base_url,
        )
        message = Message(
            user=appointment.practitioner, channel=channel, body=message_body
        )
        post_session.message = message
        db.session.add(post_session)

        braze_events.post_session_note_added(appointment)
        pszt = PostSessionZendeskTicket(
            appointment.practitioner,
            message,
            user_need_when_solving_ticket="customer-need-member-proactive-outreach-post-appointment-note",
        )
        pszt.update_zendesk()

        return message

    def _track_platform_info(self, appointment, field):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user_agent = request.headers.get("User-Agent")
        platform_info = {}

        if (self.user == appointment.member) and (field == "member_started_at"):
            platform_info = {
                "member_started": get_platform(user_agent),
                "member_started_raw": user_agent,
            }
        elif (self.user == appointment.practitioner) and (
            field == "practitioner_started_at"
        ):
            platform_info = {
                "practitioner_started": get_platform(user_agent),
                "practitioner_started_raw": user_agent,
            }

        platforms = appointment.json.get("platforms", {})
        platforms.update(platform_info)
        appointment.json["platforms"] = platforms

    def _check_and_set_pharmacy(self, appointment: Appointment, pharmacy_id: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        mp: MemberProfile = appointment.member.member_profile
        existing_pharmacy = mp.get_prescription_info()

        # a previous appt with practitioner or already setting on a previous
        # API call means we don't need to talk to DoseSpot here...
        if existing_pharmacy.get("pharmacy_id") and int(
            existing_pharmacy.get("pharmacy_id")
        ) == int(pharmacy_id):
            log.info(
                "Pharmacy already set to ID.",
                existing_id=existing_pharmacy.get("pharmacy_id"),
                new_id=pharmacy_id,
            )
            return

        log.info(
            "Pharmacy to be set to new ID.",
            existing_id=existing_pharmacy.get("pharmacy_id"),
            new_id=pharmacy_id,
        )

        if not mp.enabled_for_prescription:
            log.warning(
                "Pharmacy cannot be set for member not enabled for prescription."
            )
            abort(400, message=str(PRESCRIPTION_MISSING_DATA_ERROR_MESSAGE))

        if appointment.privacy == PRIVACY_CHOICES.anonymous:
            log.warning("Pharmacy cannot be set for member in anonymous appointment.")
            abort(400, message=str(ANONYMOUS_APPOINTMENT_PHARMACY_ERROR_MESSAGE))

        profile = appointment.practitioner.practitioner_profile  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "practitioner_profile"
        if not ProviderService().enabled_for_prescribing(appointment.practitioner_id):
            log.warning(
                "Pharmacy cannot be set for member in appointment with practitioner not enabled for prescription."
            )
            abort(400, message=str(PRACTITIONER_NOT_ENABLED_ERROR_MESSAGE))
        dosespot = DoseSpotAPI(
            clinic_id=DOSESPOT_GLOBAL_CLINIC_ID_V2,
            clinic_key=DOSESPOT_GLOBAL_CLINIC_KEY_V2,
            user_id=profile.dosespot["user_id"],
            maven_user_id=appointment.practitioner.id,  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "id"
        )

        pharmacy = dosespot.validate_pharmacy(pharmacy_id)
        if pharmacy.get("PharmacyId"):
            mp.set_prescription_info(
                pharmacy_id=pharmacy["PharmacyId"], pharmacy_info=pharmacy
            )
            db.session.add(mp)

            service_ns_tag = "appointments"
            team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
            notify_rx_info_entered.delay(
                appointment.id, service_ns=service_ns_tag, team_ns=team_ns_tag
            )
        else:
            log.warning(
                "New pharmacy id '%s' could not be validated with the DoseSpot api.",
                pharmacy_id,
            )
            # do not abort the request in the case that the pharmacy cannot be validated

    def _add_or_update_disconnect_times(
        self, appointment: Appointment, key: str, value: datetime.datetime
    ) -> None:
        """
        Adds or updates the disconnect times.
        """
        if appointment.json.get(key, None):
            # append by concatenating the two lists
            appointment.json[key] = appointment.json[key] + [value.isoformat()]
        else:
            appointment.json[key] = [value.isoformat()]

    def _has_cancellation_survey_recorded_answers(
        self, incoming_changes: Mapping[str, Any], appointment: Appointment
    ) -> bool:
        return (
            incoming_changes.get("surveys") is not None
            and incoming_changes.get("surveys", {}).get("cancellation_survey")
            is not None
            and len(
                incoming_changes.get("surveys", {})
                .get("cancellation_survey", {})
                .get("recorded_answers")
            )
            != 0
            and self.user == appointment.member
        )


# TODO: As part of MPC-3326, to surround this in feature flag to eventually deprecate after moving
def log_answer_sets(questionnaire: Union[Questionnaire, None], deprecated_client: bool):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    questionnaire_title = (
        questionnaire.oid if questionnaire else "no_associated_questionnaire"
    )
    client_status = "deprecated_client" if deprecated_client else "updated_client"
    stats.increment(
        metric_name="api.appointments.resources.appointment.appointment_resource.update_appointment.structured_internal_note",
        pod_name=stats.PodNames.PERSONALIZED_CARE,
        tags=[
            f"recorded_answer_set_client_status:{client_status}",
            f"recorded_answer_set_questionnaire_title:{questionnaire_title}",
        ],
    )
