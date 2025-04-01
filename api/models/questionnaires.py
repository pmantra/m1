from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import ddtrace
from dateutil.parser import parse
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    event,
    func,
)
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.orm import backref, relationship, validates
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.sql.expression import desc

from authn.models.user import User
from authz.models.roles import ROLES, Role
from models.base import TimeLoggedSnowflakeModelBase, db
from models.profiles import practitioner_verticals
from models.tracks import TrackName
from utils.data import JSONAlchemy
from utils.exceptions import DraftUpdateAttemptException, log_exception_message
from utils.foreign_key_metric import increment_metric
from utils.log import logger

log = logger(__name__)

HEALTH_BINDER_QUESTIONNAIRE_OID = "health_binder"
PROVIDER_ADDENDA_QUESTIONNAIRE_OID = "addendum_notes"
SINGLE_EMBRYO_TRANSFER_QUESTIONNAIRE_OID = "embryo_data_collection"
COACHING_NOTES_COACHING_PROVIDERS_OID = "coaching_notes_coaching_providers"
ASYNC_ENCOUNTER_QUESTIONNAIRE_OID = "async_encounters"

DOB_QUESTION_OID = "dob"
WEIGHT_QUESTION_OID = "weight"
HEIGHT_QUESTION_OID = "height"
GENDER_MULTISELECT_QUESTION_OID = "gender_select"
GENDER_FREETEXT_QUESTION_OID = "gender_describe"
GENDER_OTHER_ANSWER_OID = "other"

questionnaire_vertical = db.Table(
    "questionnaire_vertical",
    Column("questionnaire_id", BigInteger, ForeignKey("questionnaire.id")),
    Column("vertical_id", Integer, ForeignKey("vertical.id")),
)

questionnaire_trigger_answer = db.Table(
    "questionnaire_trigger_answer",
    Column("questionnaire_id", BigInteger, ForeignKey("questionnaire.id")),
    Column("answer_id", Integer, ForeignKey("answer.id")),
)

questionnaire_role = db.Table(
    "questionnaire_role",
    Column("questionnaire_id", BigInteger, ForeignKey("questionnaire.id")),
    Column("role_id", Integer, ForeignKey("role.id")),
)


class Questionnaire(TimeLoggedSnowflakeModelBase):
    __tablename__ = "questionnaire"

    def __repr__(self) -> str:
        return f"Questionnaire id: {self.id} oid: {self.oid}"

    sort_order = Column(Integer, nullable=False)
    oid = Column(
        String(255), doc="Object identifier for querying purposes", nullable=False
    )

    @validates("oid")
    def validate_oid(self, key, oid):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if oid.strip() == "":
            raise ValueError("oid cannot be empty or whitespace only")
        return oid

    title_text = Column(String)
    description_text = Column(String)
    intro_appointment_only = Column(Boolean, nullable=False)
    track_name = Column(
        String,
        nullable=False,
        doc="""
        Track Name used here to categorize questionnaires, showing them only to members who are on that track.
        """,
    )

    verticals = relationship(
        "Vertical", backref="questionnaires", secondary=questionnaire_vertical
    )
    question_sets = relationship(
        "QuestionSet",
        backref="questionnaire",
        primaryjoin="and_(QuestionSet.questionnaire_id == Questionnaire.id, QuestionSet.soft_deleted_at == None)",
        lazy="selectin",
    )
    trigger_answers = relationship(
        "Answer", secondary=questionnaire_trigger_answer, lazy="selectin"
    )
    roles = relationship("Role", backref="questionnaires", secondary=questionnaire_role)

    def question_ids(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        qs = (
            db.session.query(Question.id)
            .join(QuestionSet)
            .join(Questionnaire)
            .filter(Questionnaire.id == self.id)
            .all()
        )
        return [q.id for q in qs]

    @validates("track_name")
    def validate_track_name(self, _key, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value == "__None":
            return True
        if value and not TrackName.isvalid(value):
            raise ValueError(f"'{value}' is not a valid track name")
        return value

    @classmethod
    @ddtrace.tracer.wrap()
    def get_structured_internal_note_for_pract(
        cls, practitioner: User
    ) -> Optional[Questionnaire]:
        questionnaires = (
            Questionnaire.query.join(questionnaire_vertical)
            .join(
                practitioner_verticals,
                questionnaire_vertical.c.vertical_id
                == practitioner_verticals.c.vertical_id,
            )
            .filter(practitioner_verticals.c.user_id == practitioner.id)
            .filter(~Questionnaire.roles.any(Role.name == ROLES.member))
            .group_by(Questionnaire.id)
            .order_by(desc(Questionnaire.id))
            .all()
        )
        # Exclude async encounter prefixed questionnaires from being used as clinical notes in encounter summary
        questionnaires = [
            q
            for q in questionnaires
            if not q.oid
            or (q.oid and not (q.oid.startswith(ASYNC_ENCOUNTER_QUESTIONNAIRE_OID)))
        ]
        if questionnaires:
            return questionnaires[0]

        # fall back to generic COACHING_NOTES_COACHING_PROVIDERS Questionnaire
        try:
            return Questionnaire.query.filter_by(
                oid=COACHING_NOTES_COACHING_PROVIDERS_OID
            ).one()
        except NoResultFound:
            log_exception_message(
                "No COACHING_NOTES_COACHING_PROVIDERS questionnaire is configured for this environment"
            )
        return None


class QuestionSet(TimeLoggedSnowflakeModelBase):
    __tablename__ = "question_set"

    sort_order = Column(Integer, nullable=False)
    oid = Column(
        String(255), doc="Object identifier for querying purposes", nullable=False
    )

    @validates("oid")
    def validate_oid(self, key, oid):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if oid.strip() == "":
            raise ValueError("oid cannot be empty or whitespace only")
        return oid

    prerequisite_answer_id = Column(
        BigInteger,
        ForeignKey("answer.id", use_alter=True),
        nullable=True,
        doc="""
            Answer which must have been entered by a user as a prerequisite
            to displaying this question set to the user.  Optional.
        """,
    )
    questionnaire_id = Column(
        BigInteger, ForeignKey("questionnaire.id"), nullable=False
    )
    soft_deleted_at = Column(DateTime, default=None)

    questions = relationship(
        "Question",
        backref="question_set",
        primaryjoin="and_(Question.question_set_id == QuestionSet.id, Question.soft_deleted_at == None)",
        lazy="selectin",
    )
    prerequisite_answer = relationship("Answer")


@event.listens_for(QuestionSet.soft_deleted_at, "set", named=True)
def question_set_soft_deletion_cascade(**kw):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if isinstance(kw["value"], datetime):
        for q in kw["target"].questions:
            if q.soft_deleted_at is None:
                q.soft_deleted_at = kw["value"]


class QuestionTypes(enum.Enum):
    RADIO = "RADIO"
    CHECKBOX = "CHECKBOX"
    TEXT = "TEXT"
    STAR = "STAR"
    MEDICATION = "MEDICATION"
    ALLERGY_INTOLERANCE = "ALLERGY_INTOLERANCE"
    CONDITION = "CONDITION"
    DATE = "DATE"
    MULTISELECT = "MULTISELECT"
    SINGLE_SELECT = "SINGLE_SELECT"


class Question(TimeLoggedSnowflakeModelBase):
    __tablename__ = "question"

    def __repr__(self) -> str:
        return f"Question id: {self.id} label: {self.label}"

    question_set_id = Column(BigInteger, ForeignKey("question_set.id"), nullable=False)
    sort_order = Column(Integer, nullable=False)
    label = Column(String(1000), nullable=False)
    type = Column(Enum(QuestionTypes), nullable=False)
    required = Column(Boolean, nullable=False)
    oid = Column(
        String(255), doc="Object identifier for querying purposes", nullable=False
    )

    @validates("oid")
    def validate_oid(self, key, oid):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if oid.strip() == "":
            raise ValueError("oid cannot be empty or whitespace only")
        return oid

    non_db_answer_options_json = Column(
        JSONAlchemy(Text),
        nullable=True,
        doc="""
            Answer options that are represented here as json rather than as
            records in the `answer` table.  Needed only for complex question
            types (MEDICATION, ALLERGY_INTOLERANCE, CONDITION)
        """,
    )
    soft_deleted_at = Column(DateTime, default=None)
    answers = relationship(
        "Answer",
        primaryjoin="and_(Answer.question_id == Question.id, Answer.soft_deleted_at == None)",
        lazy="selectin",
    )

    def expected_json_option_keys_for_type(self) -> List:
        json_option_keys = {
            QuestionTypes.MEDICATION: ["options"],
            QuestionTypes.CONDITION: ["options"],
            QuestionTypes.ALLERGY_INTOLERANCE: [
                "medicine_options",
                "food_other_options",
            ],
        }
        return json_option_keys[self.type] if self.type in json_option_keys else []  # type: ignore[index] # Invalid index type "str" for "Dict[QuestionTypes, List[str]]"; expected type "QuestionTypes"

    @validates("non_db_answer_options_json")
    def validate_non_db_answer_options_json(self, _, json):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        option_keys = self.expected_json_option_keys_for_type()
        if option_keys:
            for key_name in option_keys:
                assert key_name in json, f"Must contain {key_name} key"
                assert isinstance(json[key_name], list), "options must be an array"
        return json


@event.listens_for(Question.soft_deleted_at, "set", named=True)
def question_soft_deletion_cascade(**kw):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if isinstance(kw["value"], datetime):
        for a in kw["target"].answers:
            if a.soft_deleted_at is None:
                a.soft_deleted_at = kw["value"]


class Answer(TimeLoggedSnowflakeModelBase):
    __tablename__ = "answer"

    def __repr__(self) -> str:
        return f"Answer id: {self.id} text: {self.text}"

    question_id = Column(BigInteger, ForeignKey("question.id"), nullable=False)
    sort_order = Column(Integer, nullable=False)
    text = Column(String(6000), nullable=False)
    oid = Column(
        String(255), doc="Object identifier for querying purposes", nullable=False
    )

    @validates("oid")
    def validate_oid(self, key, oid):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if oid.strip() == "":
            raise ValueError("oid cannot be empty or whitespace only")
        return oid

    soft_deleted_at = Column(DateTime, default=None)

    question = relationship("Question", lazy="joined")


class RecordedAnswer(TimeLoggedSnowflakeModelBase):
    __tablename__ = "recorded_answer"

    # appointment_id is not a FK in the alchemy model, but a FK in the table schema, since we
    # remove the fk at the application level first.
    appointment_id = Column(Integer, nullable=True)
    question_id = Column(BigInteger, ForeignKey("question.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    recorded_answer_set_id = Column(BigInteger, ForeignKey("recorded_answer_set.id"))
    text = Column(
        String(6000),
        nullable=True,
        doc="""
            Response to freetext question; will be null if associated question
            is not of type 'text'.
        """,
    )
    date = Column(
        Date,
        nullable=True,
        doc="""
            Response to Date question; will be null if associated question is not of type 'DATE'
        """,
    )
    answer_id = Column(
        BigInteger,
        ForeignKey("answer.id"),
        nullable=True,
        doc="""
            Id of associated answer option; will be null if associated question
            is of type 'text'.
        """,
    )
    payload = Column(
        JSONAlchemy(Text),
        nullable=True,
        doc="""
            JSON column for complex answer types; may also be used as an alternative
            to the text column
        """,
    )

    question = relationship("Question", lazy="joined")
    answer = relationship("Answer", lazy="joined")

    @property
    def appointment(self):  # type: ignore[no-untyped-def]
        from appointments.utils.appointment_utils import get_appointments_by_ids

        model = f"{self.__tablename__}.appointment"
        try:
            appointments = get_appointments_by_ids([self.appointment_id])  # type: ignore[list-item]
            increment_metric(read=True, model_name=model)
            return appointments[0] if len(appointments) > 0 else None
        except Exception as e:
            error_message = "Error in getting appointment in RecordedAnswer"
            log.error(error_message, error_type=e.__class__.__name__, error_msg=str(e))
            increment_metric(read=True, model_name=model, failure=error_message)
            raise e

    @appointment.setter
    def appointment(self, appointment):  # type: ignore[no-untyped-def]
        from appointments.utils.appointment_utils import upsert_appointment

        model = f"{self.__tablename__}.appointment"
        log.warn(
            "This approach of upserting appointment is not allowed. Use a different way to do so",
            model=model,
        )

        try:
            self.appointment_id = appointment.id
            db.session.add(self)
            upsert_appointment(appointment)
            increment_metric(read=False, model_name=model)
        except Exception as e:
            error_message = "Error in upserting appointment in RecordedAnswer"
            log.error(error_message, error_type=e.__class__.__name__, error_msg=str(e))
            increment_metric(read=False, model_name=model, failure=error_message)
            raise e

    @classmethod
    def create(cls, attrs: dict, user_id: int = None, appointment_id: int = None):  # type: ignore[no-untyped-def,assignment] # Function is missing a return type annotation #type: ignore[assignment] # Incompatible default for argument "user_id" (default has type "None", argument has type "int") #type: ignore[assignment] # Incompatible default for argument "appointment_id" (default has type "None", argument has type "int")
        from appointments.utils.appointment_utils import check_appointment_by_ids

        check_appointment_by_ids([appointment_id], True)
        return RecordedAnswer(
            user_id=user_id,
            appointment_id=appointment_id,
            question_id=integer_id_or_none(attrs, "question_id"),
            answer_id=integer_id_or_none(attrs, "answer_id"),
            text=attrs.get("text"),
            date=parse(attrs.get("date")).date() if attrs.get("date") else None,  # type: ignore[arg-type] # Argument 1 to "parse" has incompatible type "Optional[Any]"; expected "Union[bytes, str, IO[str], IO[Any]]"
            payload=attrs.get("payload"),
        )


@event.listens_for(RecordedAnswer, "init")
def convert_string_ids_to_ints(target, args, kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if "question_id" in kwargs:
        if kwargs["question_id"] and isinstance(kwargs["question_id"], str):
            kwargs["question_id"] = int(kwargs["question_id"])
    if "answer_id" in kwargs:
        if kwargs["answer_id"] and isinstance(kwargs["answer_id"], str):
            kwargs["answer_id"] = int(kwargs["answer_id"])


@dataclass
class CompositeRecordedAnswerSet:
    __slots__ = (
        "submitted_at",
        "source_user_id",
        "questionnaire_id",
        "recorded_answers",
    )
    submitted_at: datetime
    source_user_id: int
    questionnaire_id: int
    recorded_answers: List[RecordedAnswer]


class RecordedAnswerSet(TimeLoggedSnowflakeModelBase):
    __tablename__ = "recorded_answer_set"

    submitted_at = Column(DateTime, nullable=False)
    source_user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    questionnaire_id = Column(
        BigInteger, ForeignKey("questionnaire.id"), nullable=False
    )
    draft = Column(Boolean, default=False)

    # appointment_id is not a FK in the alchemy model, but a FK in the table schema, since we
    # remove the fk at the application level first.
    appointment_id = Column(Integer, nullable=True)

    recorded_answers = relationship(
        "RecordedAnswer", lazy="selectin", backref="recorded_answer_set"
    )
    questionnaire = relationship("Questionnaire", lazy="joined")

    @property
    def appointment(self):  # type: ignore[no-untyped-def]
        from appointments.utils.appointment_utils import get_appointments_by_ids

        model = f"{self.__tablename__}.appointment"
        try:
            appointments = get_appointments_by_ids([self.appointment_id])  # type: ignore[list-item]
            increment_metric(read=True, model_name=model)
            return appointments[0] if len(appointments) > 0 else None
        except Exception as e:
            error_message = "Error in getting appointment in RecordedAnswerSet"
            log.error(error_message, error_type=e.__class__.__name__, error_msg=str(e))
            increment_metric(read=True, model_name=model, failure=error_message)
            raise e

    @appointment.setter
    def appointment(self, appointment):  # type: ignore[no-untyped-def]
        from appointments.utils.appointment_utils import upsert_appointment

        model = f"{self.__tablename__}.appointment"
        log.warn(
            "This approach of upserting appointment is not allowed. Use a different way to do so",
            model=model,
        )

        try:
            self.appointment_id = appointment.id
            db.session.add(self)
            upsert_appointment(appointment)
            increment_metric(read=False, model_name=model)
        except Exception as e:
            error_message = "Error in upserting appointment in RecordedAnswerSet"
            log.error(error_message, error_type=e.__class__.__name__, error_msg=str(e))
            increment_metric(read=False, model_name=model, failure=error_message)
            raise e

    @classmethod
    def _log_attr_mismatches(cls, rac, attrs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not rac:
            return
        scrubbed_attrs = {}
        mismatches = []
        for attr in ["id", "questionnaire_id", "appointment_id", "source_user_id"]:
            scrubbed_attrs[attr] = attrs.get(attr)
            if attr in attrs and int(getattr(rac, attr)) != int(attrs[attr]):
                mismatches.append(
                    f"looking for {attr} {attrs[attr]}, got {getattr(rac, attr)}"
                )

        if mismatches:
            log.warning(
                f"Mismatches found in RecordedAnswerSet lookup with attrs {scrubbed_attrs}, "
                f"{','.join(mismatches)}"
            )
        return mismatches

    @classmethod
    def find_by_id_or_attrs(cls, attrs: dict, id_=None) -> RecordedAnswerSet | None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        if id_:
            rac = RecordedAnswerSet.query.filter(
                RecordedAnswerSet.id == id_
            ).one_or_none()
        elif attrs.get("id", None):
            rac = RecordedAnswerSet.query.filter(
                RecordedAnswerSet.id == attrs["id"]
            ).one_or_none()

        elif attrs.get("questionnaire_id") and attrs.get("appointment_id"):
            rac = RecordedAnswerSet.query.filter(
                RecordedAnswerSet.questionnaire_id == attrs["questionnaire_id"],
                RecordedAnswerSet.appointment_id == attrs["appointment_id"],
            ).one_or_none()
        else:
            filters = {
                key: int(attrs[key])
                for key in (
                    "id",
                    "source_user_id",
                    "questionnaire_id",
                    "appointment_id",
                )
                if key in attrs and attrs.get(key)
            }
            rac = (
                RecordedAnswerSet.query.filter_by(**filters)
                .order_by(RecordedAnswerSet.submitted_at.desc())
                .first()
            )
        cls._log_attr_mismatches(rac, attrs)
        return rac

    @classmethod
    def create(cls, attrs: dict) -> RecordedAnswerSet:
        """Create a recorded answer set with answers attached (without commit)."""
        from appointments.utils.appointment_utils import check_appointment_by_ids

        check_appointment_by_ids([integer_id_or_none(attrs, "appointment_id")], True)  # type: ignore[list-item]

        if not attrs.get("questionnaire_id") or not attrs.get("source_user_id"):
            raise ValueError(
                "questionnaire id and source user id cannot be empty in recorded_answer_set!"
            )

        user_id = integer_id_or_none(attrs, "source_user_id")

        rec_answer_set = RecordedAnswerSet(
            submitted_at=attrs.get("submitted_at", datetime.utcnow()),
            source_user_id=integer_id_or_none(attrs, "source_user_id"),
            draft=attrs.get("draft"),
            questionnaire_id=integer_id_or_none(attrs, "questionnaire_id"),
            appointment_id=integer_id_or_none(attrs, "appointment_id"),
        )

        db.session.add(rec_answer_set)

        # append answers to answer set
        for ra in attrs["recorded_answers"]:
            rec_answer_set.recorded_answers.append(
                RecordedAnswer.create(attrs=ra, user_id=user_id)
            )
        db.session.add(rec_answer_set)

        # flush to database so the answer set can be found to satisfy foreign key constraint
        db.session.flush()

        return rec_answer_set

    @classmethod
    def create_or_update(cls, attrs: dict, id_=None) -> RecordedAnswerSet | None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        user_id = integer_id_or_none(attrs, "source_user_id")
        existing_rec_answer_set: RecordedAnswerSet | None = cls.find_by_id_or_attrs(
            attrs=attrs, id_=id_
        )
        appointment_id = integer_id_or_none(attrs, "appointment_id")
        if existing_rec_answer_set:
            if existing_rec_answer_set.draft:
                # The only two columns that can/should be updated
                existing_rec_answer_set.submitted_at = attrs.get(
                    "submitted_at", datetime.utcnow()
                )
                if "draft" in attrs:
                    existing_rec_answer_set.draft = attrs["draft"]
                if "recorded_answers" in attrs:
                    # For simplicity, just delete all recorded answers and recreate.
                    # This does assume it's not receiving a partial list of answers--
                    # maybe dangerous but reasonable to expect when used in a PUT route.
                    # Confirm with clients before using.
                    for ra in existing_rec_answer_set.recorded_answers:
                        log.info(f"Recorded Answer to delete: {ra.id}")
                        db.session.delete(ra)
                    existing_rec_answer_set.recorded_answers.clear()
                    for ra in attrs["recorded_answers"]:
                        log.info(f"Recorded Answer to add: {ra}")
                        existing_rec_answer_set.recorded_answers.append(
                            RecordedAnswer.create(
                                attrs=ra, user_id=user_id, appointment_id=appointment_id
                            )
                        )
                db.session.add(existing_rec_answer_set)
            else:
                # return error message if trying to set the draft via endpoints instead of admin
                # for consistency with previous code
                old_draft_value = existing_rec_answer_set.draft
                if old_draft_value is False and attrs["draft"] is not False:
                    raise DraftUpdateAttemptException(
                        f"Cannot set RecordedAnswerSet {appointment_id} draft from false to true"
                    )
            return existing_rec_answer_set
        else:
            # In this case we want to create a new RecordedAnswerSet, but we still need to guard
            # against the case where the same user issues a very similar PUT while we are still processing.
            # To protect against that, we will do an upsert here.

            # NOTE: Since we reused questionnaires and recorded_answer_sets for treatment procedure questionnaires
            # there are now legitimate scenarios where an appointment_id is not present
            if not attrs.get("questionnaire_id"):
                raise ValueError(
                    "questionnaire_id cannot be empty in recorded_answer_set!"
                )

            upsert_stmt = (
                insert(RecordedAnswerSet.__table__)
                .values(
                    source_user_id=integer_id_or_none(attrs, "source_user_id"),
                    submitted_at=attrs.get("submitted_at", datetime.utcnow()),
                    draft=attrs.get("draft"),
                    questionnaire_id=integer_id_or_none(attrs, "questionnaire_id"),
                    appointment_id=appointment_id,
                )
                .on_duplicate_key_update(
                    source_user_id=integer_id_or_none(attrs, "source_user_id"),
                    submitted_at=attrs.get("submitted_at", datetime.utcnow()),
                    draft=attrs.get("draft"),
                )
            )
            db.session.execute(upsert_stmt)
            db.session.commit()

            # We actually need to go back and look for the result of the UPSERT so we can attach some answers to it.
            rec_answer_set: RecordedAnswerSet | None = cls.find_by_id_or_attrs(
                attrs=attrs, id_=id_
            )
            if not rec_answer_set:
                # NOTE: 2024-02-01
                # We were observing 500s in production due to rec_answer_set
                # being none. this signals a mismatch in the find_by_id_or_attrs
                # and the values saved
                log.warning(
                    "rec_answer_set not found after upsert",
                    source_user_id=integer_id_or_none(attrs, "source_user_id"),
                    questionnaire_id=integer_id_or_none(attrs, "questionnaire_id"),
                    appointment_id=appointment_id,
                    draft=attrs.get("draft"),
                    recorded_answer_set_id=id_,
                )
                return None

            ra: list[RecordedAnswer] | None  # type: ignore[no-redef] # Name "ra" already defined on line 524
            for ra in attrs["recorded_answers"]:
                rec_answer_set.recorded_answers.append(
                    RecordedAnswer.create(
                        attrs=ra, user_id=user_id, appointment_id=appointment_id
                    )
                )
            db.session.add(rec_answer_set)
            return rec_answer_set

    @classmethod
    @ddtrace.tracer.wrap()
    def create_composite_answer_set_of_latest_answers(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls, user_id, questionnaire
    ) -> CompositeRecordedAnswerSet:
        # Necessary because answer sets may not contain answers to all questions.
        # Yes, we're getting them all, which makes one wonder what the point was
        # of separating them into answer sets in the first place...
        # In almost all cases, there shouldn't be very many, which is good,
        # because there's a small chance we have to iterate through all of them.
        ra_subq = (
            db.session.query(
                func.max(RecordedAnswer.id).label("latest_recorded_answer_id"),
                func.max(RecordedAnswerSet.submitted_at).label("latest_submitted_at"),
                RecordedAnswer.question_id,
                RecordedAnswerSet.questionnaire_id,
                RecordedAnswerSet.source_user_id,
            )
            .join(RecordedAnswerSet)
            .filter(
                RecordedAnswerSet.source_user_id == user_id,
                RecordedAnswerSet.questionnaire_id == questionnaire.id,
            )
            .group_by(
                RecordedAnswer.question_id,
                RecordedAnswerSet.questionnaire_id,
                RecordedAnswerSet.source_user_id,
            )
            .subquery()
        )
        composite_answers = (
            db.session.query(
                RecordedAnswer, ra_subq.c.latest_submitted_at.label("submitted_at")
            )
            .join(ra_subq, ra_subq.c.latest_recorded_answer_id == RecordedAnswer.id)
            .order_by(desc(ra_subq.c.latest_submitted_at))
            .all()
        )
        if not composite_answers:
            return  # type: ignore[return-value] # Return value expected

        return CompositeRecordedAnswerSet(
            submitted_at=composite_answers[0].submitted_at,
            source_user_id=user_id,
            questionnaire_id=questionnaire.id,
            recorded_answers=[ra.RecordedAnswer for ra in composite_answers],
        )


class ProviderAddendumAnswer(TimeLoggedSnowflakeModelBase):
    __tablename__ = "provider_addendum_answer"

    addendum_id = Column(Integer, ForeignKey("provider_addendum.id"), nullable=False)
    question_id = Column(BigInteger, ForeignKey("question.id"), nullable=False)
    text = Column(String(6000), nullable=True)
    date = Column(Date, nullable=True)
    answer_id = Column(BigInteger, ForeignKey("answer.id"), nullable=True)

    question = relationship("Question", lazy="joined")
    answer = relationship("Answer", lazy="joined")
    provider_addendum = relationship(
        "ProviderAddendum",
        lazy="joined",
        backref=backref(
            "provider_addendum_answers", order_by="ProviderAddendumAnswer.question_id"
        ),
    )

    @classmethod
    def create(cls, attrs: dict):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return ProviderAddendumAnswer(
            addendum_id=integer_id_or_none(attrs, "addendum_id"),
            question_id=integer_id_or_none(attrs, "question_id"),
            answer_id=integer_id_or_none(attrs, "answer_id"),
            text=attrs.get("text"),
            date=parse(attrs.get("date")).date() if attrs.get("date") else None,  # type: ignore[arg-type] # Argument 1 to "parse" has incompatible type "Optional[Any]"; expected "Union[bytes, str, IO[str], IO[Any]]"
        )


class ProviderAddendum(TimeLoggedSnowflakeModelBase):
    __tablename__ = "provider_addendum"

    submitted_at = Column(DateTime, nullable=False)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    questionnaire_id = Column(
        BigInteger, ForeignKey("questionnaire.id"), nullable=False
    )
    appointment_id = Column(Integer, nullable=False)
    associated_answer_id = Column(
        Integer, ForeignKey("recorded_answer.id"), nullable=True
    )

    questionnaire = relationship("Questionnaire", lazy="joined")
    user = relationship("User", lazy="joined")

    @property
    def appointment(self):  # type: ignore[no-untyped-def]
        from appointments.utils.appointment_utils import get_appointments_by_ids

        model = f"{self.__tablename__}.appointment"
        try:
            appointments = get_appointments_by_ids([self.appointment_id])
            increment_metric(True, model)
            return appointments[0] if len(appointments) > 0 else None
        except Exception as e:
            error_message = "Error in getting appointment in ProviderAddendum"
            log.error(error_message, error_type=e.__class__.__name__, error_msg=str(e))
            increment_metric(True, model, error_message)
            raise e

    @appointment.setter
    def appointment(self, appointment):  # type: ignore[no-untyped-def]
        from appointments.utils.appointment_utils import upsert_appointment

        model = f"{self.__tablename__}.appointment"
        log.warn(
            "This approach of upserting appointment is not allowed. Use a different way to do so",
            model=model,
        )
        try:
            upsert_appointment(appointment)
            increment_metric(False, model)
        except Exception as e:
            error_message = "Error in upserting appointment in ProviderAddendum"
            log.error(error_message, error_type=e.__class__.__name__, error_msg=str(e))
            increment_metric(False, model, error_message)
            raise e

    # Does not commit changes to DB
    @classmethod
    def create(cls, attrs, id_=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from appointments.utils.appointment_utils import check_appointment_by_ids

        appointment_id = integer_id_or_none(attrs, "appointment_id")
        appointment_id_list = [appointment_id] if appointment_id else []

        check_appointment_by_ids(appointment_id_list, True)  # type: ignore
        provider_addendum = ProviderAddendum(
            user_id=integer_id_or_none(attrs, "user_id"),
            submitted_at=attrs.get("submitted_at", datetime.utcnow()),
            questionnaire_id=integer_id_or_none(attrs, "questionnaire_id"),
            appointment_id=appointment_id,
            associated_answer_id=integer_id_or_none(attrs, "associated_answer_id"),
        )
        db.session.add(provider_addendum)
        for ans in attrs["provider_addendum_answers"]:
            provider_addendum.provider_addendum_answers.append(
                ProviderAddendumAnswer.create(attrs=ans)
            )
        db.session.add(provider_addendum)
        return provider_addendum


def integer_id_or_none(ra: dict, key: str) -> int | None:
    if ra.get(f"string_{key}"):
        return int(ra.get(f"string_{key}"))  # type: ignore[arg-type] # Argument 1 to "int" has incompatible type "Optional[Any]"; expected "Union[str, Buffer, SupportsInt, SupportsIndex, SupportsTrunc]"
    elif ra.get(key):
        return int(ra.get(key))  # type: ignore[arg-type] # Argument 1 to "int" has incompatible type "Optional[Any]"; expected "Union[str, Buffer, SupportsInt, SupportsIndex, SupportsTrunc]"
    else:
        return None
