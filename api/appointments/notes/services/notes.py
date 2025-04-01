from __future__ import annotations

import datetime
from typing import Any, Mapping, Union

import ddtrace
from flask_restful import abort
from sqlalchemy import exc
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from appointments.models.appointment import Appointment
from appointments.models.appointment_meta_data import PostAppointmentNoteUpdate
from appointments.repository.appointment_metadata import AppointmentMetaDataRepository
from appointments.tasks.appointments import send_post_appointment_message
from authn.models.user import User
from common import stats
from models.questionnaires import (
    COACHING_NOTES_COACHING_PROVIDERS_OID,
    PROVIDER_ADDENDA_QUESTIONNAIRE_OID,
    ProviderAddendum,
    Questionnaire,
    RecordedAnswer,
    RecordedAnswerSet,
)
from storage.connection import db
from utils.exceptions import DraftUpdateAttemptException, UserInputValidationError
from utils.log import logger

MAX_CHAR_LENGTH = 6000

log = logger(__name__)


@ddtrace.tracer.wrap()
def _log_answer_sets(
    questionnaire: Union[Questionnaire, None], deprecated_client: bool
) -> None:
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


@ddtrace.tracer.wrap()
def update_internal_note(args: Mapping[str, Any], user: User, appointment: Appointment):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Updates the structured internal note.
    """

    if args.get("structured_internal_note") and user == appointment.practitioner:
        recorded_answer_set_attrs = args["structured_internal_note"].get(
            "recorded_answer_set"
        )
        if recorded_answer_set_attrs:
            recorded_answer_set_attrs["appointment_id"] = appointment.id

            if "recorded_answers" in recorded_answer_set_attrs and any(
                len(ra.get("text", "")) > MAX_CHAR_LENGTH
                for ra in recorded_answer_set_attrs["recorded_answers"]
                if ra.get("text")
            ):
                abort(
                    422,
                    message=f"Text cannot be greater than {MAX_CHAR_LENGTH} characters",
                )

            try:
                RecordedAnswerSet.create_or_update(recorded_answer_set_attrs)
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
            questionnaire_id = recorded_answer_set_attrs.get("questionnaire_id", None)
            questionnaire = (
                Questionnaire.query.filter(Questionnaire.id == questionnaire_id).first()
                if questionnaire_id
                else None
            )
            log.debug("structured_internal_note", q=questionnaire)
            _log_answer_sets(questionnaire=questionnaire, deprecated_client=False)

        else:
            # The client hasn't updated and is sending answers the old way
            # (on their own rather than part of a recorded answer set).
            recorded_answers = args["structured_internal_note"].get("recorded_answers")

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
                        user_id=user.id,
                    )
                    coaching_notes_coaching_providers = Questionnaire.query.filter(
                        Questionnaire.oid == COACHING_NOTES_COACHING_PROVIDERS_OID
                    ).first()
                    # Should always exist, but just being cautious.
                    if coaching_notes_coaching_providers:
                        attrs = {
                            "submitted_at": datetime.datetime.utcnow(),
                            "source_user_id": user.id,
                            "draft": False,
                            "appointment_id": appointment.id,
                            "recorded_answers": recorded_answers,
                            "questionnaire_id": coaching_notes_coaching_providers.id,
                        }
                        RecordedAnswerSet.create_or_update(attrs)
                        _log_answer_sets(
                            questionnaire=coaching_notes_coaching_providers,
                            deprecated_client=True,
                        )
    return


@ddtrace.tracer.wrap()
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=2),
    retry=retry_if_exception_type(exc.SQLAlchemyError),
)
def update_internal_note_v2(
    args: Mapping[str, Any], user: User, appointment_id: int
) -> None:
    """
    Updates the structured internal note.
    """
    try:
        recorded_answer_set_attrs = args["structured_internal_note"].get(
            "recorded_answer_set"
        )
        if recorded_answer_set_attrs:
            recorded_answer_set_attrs["appointment_id"] = appointment_id

            if "recorded_answers" in recorded_answer_set_attrs and any(
                len(ra.get("text", "")) > MAX_CHAR_LENGTH
                for ra in recorded_answer_set_attrs["recorded_answers"]
                if ra.get("text")
            ):
                raise UserInputValidationError(
                    f"Text cannot be greater than {MAX_CHAR_LENGTH} characters"
                )

            RecordedAnswerSet.create_or_update(recorded_answer_set_attrs)
            db.session.commit()
            questionnaire_id = recorded_answer_set_attrs.get("questionnaire_id", None)
            questionnaire = (
                Questionnaire.query.filter(Questionnaire.id == questionnaire_id).first()
                if questionnaire_id
                else None
            )
            log.debug("structured_internal_note", q=questionnaire)
            _log_answer_sets(questionnaire=questionnaire, deprecated_client=False)
            log.info(
                "Structured internal note create/update successfully",
                appointment_id=appointment_id,
            )
        else:
            # The client hasn't updated and is sending answers the old way
            # (on their own rather than part of a recorded answer set).
            recorded_answers = args["structured_internal_note"].get("recorded_answers")

            if recorded_answers:
                appointment_recorded_answers = RecordedAnswer.query.filter(
                    RecordedAnswer.appointment_id == appointment_id
                ).all()
                parentless_recorded_answers = appointment_recorded_answers

                # If recorded answers exist but no recorded answer sets exist,
                # they're from before draft capabilities were added.
                # Maybe weird UX, but silently fail to update.
                # In the (hopefully very near) future, we'll run a migration to give
                # them parents with draft=false.
                if not parentless_recorded_answers:
                    log.info(
                        "Constructing recorded answer set from deprecated recorded_answers attribute",
                        user_id=user.id,
                    )
                    coaching_notes_coaching_providers = Questionnaire.query.filter(
                        Questionnaire.oid == COACHING_NOTES_COACHING_PROVIDERS_OID
                    ).first()
                    # Should always exist, but just being cautious.
                    if coaching_notes_coaching_providers:
                        attrs = {
                            "submitted_at": datetime.datetime.utcnow(),
                            "source_user_id": user.id,
                            "draft": False,
                            "appointment_id": appointment_id,
                            "recorded_answers": recorded_answers,
                            "questionnaire_id": coaching_notes_coaching_providers.id,
                        }
                        RecordedAnswerSet.create_or_update(attrs)
                        db.session.commit()
                        log.info(
                            "Structured internal note is created/updated successfully",
                            appointment_id=appointment_id,
                        )
                        _log_answer_sets(
                            questionnaire=coaching_notes_coaching_providers,
                            deprecated_client=True,
                        )
        return
    except DraftUpdateAttemptException:
        raise
    except exc.SQLAlchemyError as sqlalchemy_error:
        log.error(
            "Error with SQLAlchemy",
            error=sqlalchemy_error.__class__.__name__,
            exception=sqlalchemy_error,
            appointment_id=appointment_id,
        )
        raise


@ddtrace.tracer.wrap()
def update_post_session_send_appointment_note_message(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    args: Mapping[str, Any], user: User, appointment: Appointment
):
    """
    Updates the client notes and calls function to update post session.

    May send the post appointment note message if applicable.
    """
    post_session_draft = args.get("post_session", {}).get("draft", False)
    post_session_notes = args.get("post_session", {}).get("notes")
    if (post_session_notes or post_session_draft) and user == appointment.practitioner:
        result = appointment.update_post_session(post_session_notes, post_session_draft)
        db.session.add(result.post_session)
        db.session.commit()

        log.info(
            "Start send_post_appointment_message in v1",
            should_send=result.should_send,
            appointment_id=appointment.id,
        )

        if result.should_send:
            # Asynchronously process and send an email about the post appointment message
            send_post_appointment_message.delay(
                appointment_id=appointment.id,
                appointment_metadata_id=result.post_session.id,
                team_ns="virtual_care",
            )
    return


@ddtrace.tracer.wrap()
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=2),
    retry=retry_if_exception_type(exc.SQLAlchemyError),
)
def update_post_session_send_appointment_note_message_v2(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    args: Mapping[str, Any], appointment_id
) -> None:
    """
    Updates the client notes and calls function to update post session.

    May send the post appointment note message if applicable.
    """
    try:
        post_session_draft = args.get("post_session", {}).get("draft", False)
        post_session_notes = args.get("post_session", {}).get("notes")
        if post_session_notes or post_session_draft:
            result: PostAppointmentNoteUpdate = AppointmentMetaDataRepository(
                session=db.session
            ).create_or_update(appointment_id, post_session_notes, post_session_draft)
            db.session.add(result.post_session)
            db.session.commit()
            log.info(
                "Post Appointment Note is created/updated successfully",
                appointment_id=appointment_id,
            )

            log.info(
                "Start send_post_appointment_message in v2",
                should_send=result.should_send,
                appointment_id=appointment_id,
            )
            if result.should_send:
                # Asynchronously process and send an email about the post appointment message
                send_post_appointment_message.delay(
                    appointment_id=appointment_id,
                    appointment_metadata_id=result.post_session.id,
                    team_ns="virtual_care",
                )
        return
    except exc.SQLAlchemyError as sqlalchemy_error:
        log.error(
            "Error with SQLAlchemy",
            error=sqlalchemy_error.__class__.__name__,
            exception=sqlalchemy_error,
            appointment_id=appointment_id,
        )
        raise


@ddtrace.tracer.wrap()
def add_provider_addendum(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    args: dict[str, Any],
    user: User,
    appointment: Appointment,
):
    """
    Adds a provider addendum to the appointment.
    """
    if user != appointment.practitioner:
        abort(
            422,
            message="Only the appointment practitioner can submit an addendum",
        )

    completed_encounter_summary = (
        db.session.query(RecordedAnswerSet.id, RecordedAnswerSet.draft)
        .join(Questionnaire)
        .filter(
            (RecordedAnswerSet.appointment_id == appointment.id)
            & (RecordedAnswerSet.source_user_id == user.id)
        )
        .order_by(RecordedAnswerSet.submitted_at.desc())
        .first()
    )
    if not completed_encounter_summary or completed_encounter_summary.draft:
        abort(
            422,
            message="An addendum can only be added if the encounter summary has been completed",
        )

    provider_addenda_attrs = args.get("provider_addenda")

    if (
        not provider_addenda_attrs
        or not provider_addenda_attrs.get("provider_addenda")
        or len(provider_addenda_attrs["provider_addenda"]) != 1
    ):
        abort(
            422,
            message="An addendum submission must contain one completed provider addendum",
        )
        return

    provider_addendum = provider_addenda_attrs["provider_addenda"][0]
    provider_addendum["appointment_id"] = appointment.id

    if not provider_addendum.get("associated_answer_id") and provider_addendum.get(
        "associated_question_id"
    ):
        associated_answer_id = (
            db.session.query(RecordedAnswer.id)
            .join(RecordedAnswerSet)
            .filter(
                (
                    RecordedAnswer.question_id
                    == int(provider_addendum["associated_question_id"])
                )
                & (RecordedAnswerSet.id == completed_encounter_summary.id)
            )
            .scalar()
        )
        provider_addendum["associated_answer_id"] = associated_answer_id

    addendum_questionnaire_id = (
        db.session.query(Questionnaire.id)
        .filter(Questionnaire.oid == PROVIDER_ADDENDA_QUESTIONNAIRE_OID)
        .scalar()
    )
    if not addendum_questionnaire_id or str(
        addendum_questionnaire_id
    ) != provider_addendum.get("questionnaire_id"):
        abort(
            422,
            message="The answers are not for the correct questionnaire",
        )

    if any(
        len(a.get("text", "")) > MAX_CHAR_LENGTH
        for a in provider_addendum.get("provider_addendum_answers", [])
        if a.get("text")
    ):
        abort(
            422,
            message=f"Text cannot be greater than {MAX_CHAR_LENGTH} characters",
        )

    try:
        ProviderAddendum.create(provider_addendum)
        db.session.commit()
    except DraftUpdateAttemptException as e:
        log.error(
            "Error creating provider addendum",
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
        abort(
            409,
            message="Something went wrong when recording your addendum, please try again.",
        )

    return


@ddtrace.tracer.wrap()
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=2),
    retry=retry_if_exception_type(exc.SQLAlchemyError),
)
def add_provider_addendum_v2(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    args: dict[str, Any],
    user: User,
    appointment_id: int,
):
    """
    Adds a provider addendum to the appointment.
    """
    try:
        completed_encounter_summary = (
            db.session.query(RecordedAnswerSet.id, RecordedAnswerSet.draft)
            .join(Questionnaire)
            .filter(
                (RecordedAnswerSet.appointment_id == appointment_id)
                & (RecordedAnswerSet.source_user_id == user.id)
            )
            .order_by(RecordedAnswerSet.submitted_at.desc())
            .first()
        )
        if not completed_encounter_summary or completed_encounter_summary.draft:
            raise UserInputValidationError(
                "An addendum can only be added if the encounter summary has been completed"
            )

        provider_addenda_attrs = args.get("provider_addenda")

        if (
            not provider_addenda_attrs
            or not provider_addenda_attrs.get("provider_addenda")
            or len(provider_addenda_attrs["provider_addenda"]) != 1
        ):
            raise UserInputValidationError(
                "An addendum submission must contain one completed provider addendum"
            )

        provider_addendum = provider_addenda_attrs["provider_addenda"][0]  # type: ignore[index] # Value of type "Optional[Any]" is not indexable
        provider_addendum["appointment_id"] = appointment_id

        if not provider_addendum.get("associated_answer_id") and provider_addendum.get(
            "associated_question_id"
        ):
            associated_answer_id = (
                db.session.query(RecordedAnswer.id)
                .join(RecordedAnswerSet)
                .filter(
                    (
                        RecordedAnswer.question_id
                        == int(provider_addendum["associated_question_id"])
                    )
                    & (RecordedAnswerSet.id == completed_encounter_summary.id)
                )
                .scalar()
            )
            provider_addendum["associated_answer_id"] = associated_answer_id

        addendum_questionnaire_id = (
            db.session.query(Questionnaire.id)
            .filter(Questionnaire.oid == PROVIDER_ADDENDA_QUESTIONNAIRE_OID)
            .scalar()
        )
        if not addendum_questionnaire_id or str(
            addendum_questionnaire_id
        ) != provider_addendum.get("questionnaire_id"):
            raise UserInputValidationError(
                "The answers are not for the correct questionnaire"
            )

        if any(
            len(a.get("text", "")) > MAX_CHAR_LENGTH
            for a in provider_addendum.get("provider_addendum_answers", [])
            if a.get("text")
        ):
            raise UserInputValidationError(
                f"Text cannot be greater than {MAX_CHAR_LENGTH} characters"
            )

        ProviderAddendum.create(provider_addendum)
        db.session.commit()
        log.info(
            "Provider Addendum is created successfully", appointment_id=appointment_id
        )
    except exc.SQLAlchemyError as sqlalchemy_error:
        log.error(
            "Error with SQLAlchemy",
            error=sqlalchemy_error.__class__.__name__,
            exception=sqlalchemy_error,
            appointment_id=appointment_id,
        )
        raise

    return
