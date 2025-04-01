from datetime import datetime
from typing import Type

from flask import flash, redirect, request, url_for
from flask_admin import expose
from flask_admin.actions import action
from flask_admin.contrib.sqla import tools
from flask_admin.contrib.sqla.filters import (
    FilterEmpty,
    IntEqualFilter,
    IntGreaterFilter,
    IntInListFilter,
    IntNotEqualFilter,
    IntNotInListFilter,
    IntSmallerFilter,
)
from flask_admin.form import Select2Field, fields
from flask_admin.helpers import get_redirect_target
from sqlalchemy.sql import or_

from admin.common import strip_textfield
from admin.views.base import AdminCategory, AdminViewT, MavenAuditedView
from appointments.models.appointment import Appointment
from appointments.models.schedule import Schedule
from models.questionnaires import (
    Answer,
    Question,
    Questionnaire,
    QuestionSet,
    RecordedAnswerSet,
)
from models.tracks import TrackName
from storage.connection import RoutingSQLAlchemy, db
from utils.log import logger

log = logger(__name__)


class SoftDeletableView(MavenAuditedView):
    @action(
        "soft_delete",
        "Soft-delete",
        "Are you sure you want to soft-delete these records (you should probably only be doing one at a time, if any)?",
    )
    def action_soft_delete(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        now = datetime.now()

        records = self.model.query.filter(self.model.id.in_(ids)).all()
        for record in records:
            if record.soft_deleted_at is None:
                record.soft_deleted_at = now
                db.session.add(record)
                flash(f"Soft-deleting record {record.id}.")
            else:
                flash(
                    f"Cannot update soft_deleted_at for record {record.id}, value already set."
                )
        db.session.commit()


class QuestionnaireView(MavenAuditedView):
    read_permission = "read:questionnaire"
    delete_permission = "delete:questionnaire"
    create_permission = "create:questionnaire"
    edit_permission = "edit:questionnaire"

    column_list = (
        "id",
        "oid",
        "title_text",
        "description_text",
        "sort_order",
        "trigger_answers",
        "verticals",
        "roles",
        "question_sets",
        "intro_appointment_only",
        "track_name",
    )
    column_filters = ["intro_appointment_only", "track_name"]
    form_columns = (
        "verticals",
        "roles",
        "trigger_answers",
        "oid",
        "title_text",
        "description_text",
        "sort_order",
        "intro_appointment_only",
    )
    form_excluded_columns = "track_name"

    def on_form_prefill(self, form, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_form_prefill(form, id)

        track_name = db.session.query(self.model.track_name).filter_by(id=id).scalar()
        if track_name is None:
            return

        form.track.data = track_name

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()
        form_class.track = Select2Field(
            label="Track Name",
            choices=[(track.value, track.value) for track in TrackName],
            allow_blank=True,
        )
        return form_class

    def on_model_change(self, form, questionnaire, is_created):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        questionnaire.oid = strip_textfield(questionnaire.oid)
        questionnaire.title_text = strip_textfield(questionnaire.title_text)
        questionnaire.description_text = strip_textfield(questionnaire.description_text)
        super().on_model_change(form, questionnaire, is_created)
        questionnaire.track_name = request.form.get("track")

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            Questionnaire,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class QuestionSetView(SoftDeletableView):
    read_permission = "read:question-set"
    delete_permission = "delete:question-set"
    create_permission = "create:question-set"
    edit_permission = "edit:question-set"

    edit_template = "questionset_edit_template.html"

    column_list = (
        "id",
        "oid",
        "questionnaire_id",
        "sort_order",
        "prerequisite_answer_id",
        "questions",
        "soft_deleted_at",
    )
    column_filters = ("id", "oid", "questionnaire_id", "prerequisite_answer_id")
    form_columns = (
        "questionnaire",
        "oid",
        "sort_order",
        "prerequisite_answer_id",
        "soft_deleted_at",
    )
    form_widget_args = {"soft_deleted_at": {"disabled": True}}

    def on_model_change(self, form, question_set, is_created):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        question_set.oid = strip_textfield(question_set.oid)
        super().on_model_change(form, question_set, is_created)

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            QuestionSet,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )

    @expose("/duplicate", methods=["POST"])
    def duplicate_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return_url = (
            request.form.get("return_url")
            or get_redirect_target()
            or self.get_url(".index_view")
        )
        if not self.can_create:
            flash(
                "You do not have the permissions required to create question sets.",
                "error",
            )
            return redirect(return_url)

        try:
            id = int(request.form.get("record_id"))  # type: ignore[arg-type] # Argument 1 to "int" has incompatible type "Optional[Any]"; expected "Union[str, Buffer, SupportsInt, SupportsIndex, SupportsTrunc]"
        except ValueError:
            flash("Cannot find the id for the question set.", "error")
            return redirect(return_url)

        try:
            question_set = (
                db.session.query(QuestionSet).filter(QuestionSet.id == id).one()
            )
        except Exception:
            flash(f"Question set with id {id} not found.", "error")
            return redirect(return_url)

        question_set_copy = QuestionSet(
            sort_order=question_set.sort_order,
            oid=question_set.oid,
            questionnaire_id=question_set.questionnaire_id,
            questions=[
                Question(
                    answers=[
                        Answer(
                            oid=answer.oid,
                            soft_deleted_at=answer.soft_deleted_at,
                            sort_order=answer.sort_order,
                            text=answer.text,
                        )
                        for answer in question.answers
                        if not answer.soft_deleted_at
                    ],
                    label=question.label,
                    non_db_answer_options_json=question.non_db_answer_options_json,
                    oid=question.oid,
                    question_set_id=question.question_set_id,
                    required=question.required,
                    soft_deleted_at=question.soft_deleted_at,
                    sort_order=question.sort_order,
                    type=question.type,
                )
                for question in question_set.questions
                if not question.soft_deleted_at
            ],
        )

        db.session.add(question_set_copy)
        db.session.commit()
        flash(
            f"You have successfully duplicated the question set, the new question set has id {question_set_copy.id}.",
            "success",
        )
        return redirect(url_for("questionset.edit_view", id=question_set_copy.id))


class QuestionView(SoftDeletableView):
    read_permission = "read:question"
    delete_permission = "delete:question"
    create_permission = "create:question"
    edit_permission = "edit:question"

    edit_template = "question_edit_template.html"

    column_list = (
        "id",
        "question_set",
        "sort_order",
        "type",
        "label",
        "required",
        "oid",
        "soft_deleted_at",
    )
    column_filters = ["question_set", "type", "required"]
    column_sortable_list = ("question_set", "sort_order")
    form_columns = (
        "question_set",
        "sort_order",
        "type",
        "label",
        "required",
        "oid",
        "non_db_answer_options_json",
        "soft_deleted_at",
    )

    form_overrides = {"non_db_answer_options_json": fields.JSONField}
    form_widget_args = {"soft_deleted_at": {"disabled": True}}

    def on_model_change(self, form, question, is_created):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        question.label = strip_textfield(question.label)
        question.oid = strip_textfield(question.oid)
        question.non_db_answer_options_json = strip_textfield(
            question.non_db_answer_options_json
        )
        super().on_model_change(form, question, is_created)

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            Question,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )

    @expose("/duplicate", methods=["POST"])
    def duplicate_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return_url = (
            request.form.get("return_url")
            or get_redirect_target()
            or self.get_url(".index_view")
        )
        if not self.can_create:
            flash(
                "You do not have the permissions required to create questions.", "error"
            )
            return redirect(return_url)

        try:
            id = int(request.form.get("record_id"))  # type: ignore[arg-type] # Argument 1 to "int" has incompatible type "Optional[Any]"; expected "Union[str, Buffer, SupportsInt, SupportsIndex, SupportsTrunc]"
        except ValueError:
            flash("Cannot find the id for the question.", "error")
            return redirect(return_url)

        try:
            question = db.session.query(Question).filter(Question.id == id).one()
        except Exception:
            flash(f"Question with id {id} not found.", "error")
            return redirect(return_url)

        question_copy = Question(
            answers=[
                Answer(
                    oid=answer.oid,
                    soft_deleted_at=answer.soft_deleted_at,
                    sort_order=answer.sort_order,
                    text=answer.text,
                )
                for answer in question.answers
                if not answer.soft_deleted_at
            ],
            label=question.label,
            non_db_answer_options_json=question.non_db_answer_options_json,
            oid=question.oid,
            question_set_id=question.question_set_id,
            required=question.required,
            sort_order=question.sort_order,
            type=question.type,
        )

        db.session.add(question_copy)
        db.session.commit()
        flash(
            f"You have successfully duplicated the question, the new question has id {question_copy.id}.",
            "success",
        )
        return redirect(url_for("question.edit_view", id=question_copy.id))


class AnswerView(SoftDeletableView):
    read_permission = "read:answer"
    create_permission = "create:answer"
    edit_permission = "edit:answer"

    column_list = ("id", "question", "sort_order", "text", "oid", "soft_deleted_at")
    column_filters = ["question_id"]
    column_sortable_list = ["sort_order"]
    form_columns = ("question", "sort_order", "text", "oid", "soft_deleted_at")
    form_widget_args = {"soft_deleted_at": {"disabled": True}}

    def on_model_change(self, form, answer, is_created):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        answer.oid = strip_textfield(answer.oid)
        answer.text = strip_textfield(answer.text)
        super().on_model_change(form, answer, is_created)

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            Answer,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class SchedulerUserIdIntEqualFilter(IntEqualFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def]
        subquery = (
            db.session.query(Appointment.id)
            .join(Schedule)
            .filter(self.get_column(alias) == value)
            .subquery()
        )
        return query.filter(RecordedAnswerSet.appointment_id.in_(subquery))


class SchedulerUserIdIntNotEqualFilter(IntNotEqualFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def]
        subquery = (
            db.session.query(Appointment.id)
            .join(Schedule)
            .filter(self.get_column(alias) != value)
            .subquery()
        )
        return query.filter(RecordedAnswerSet.appointment_id.in_(subquery))


class SchedulerUserIdIntGreaterFilter(IntGreaterFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def]
        subquery = (
            db.session.query(Appointment.id)
            .join(Schedule)
            .filter(self.get_column(alias) > value)
            .subquery()
        )
        return query.filter(RecordedAnswerSet.appointment_id.in_(subquery))


class SchedulerUserIdIntSmallerFilter(IntSmallerFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def]
        subquery = (
            db.session.query(Appointment.id)
            .join(Schedule)
            .filter(self.get_column(alias) < value)
            .subquery()
        )
        return query.filter(RecordedAnswerSet.appointment_id.in_(subquery))


class SchedulerUserIdFilterEmpty(FilterEmpty):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def]
        subquery = (
            db.session.query(Appointment.id)
            .join(Schedule)
            .filter(
                self.get_column(alias) == None
                if value == "1"
                else self.get_column(alias) is not None
            )  # noqa: E711
            .subquery()
        )
        return query.filter(RecordedAnswerSet.appointment_id.in_(subquery))


class SchedulerUserIdIntInListFilter(IntInListFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def]
        subquery = (
            db.session.query(Appointment.id)
            .join(Schedule)
            .filter(self.get_column(alias).in_(value))
            .subquery()
        )
        return query.filter(RecordedAnswerSet.appointment_id.in_(subquery))


class SchedulerUserIdIntNotInListFilter(IntNotInListFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def]
        column = self.get_column(alias)
        subquery = (
            db.session.query(Appointment.id)
            .join(Schedule)
            .filter(or_(~column.in_(value), column == None))  # noqa: E711
            .subquery()
        )
        return query.filter(RecordedAnswerSet.appointment_id.in_(subquery))


class RecordedAnswerSetView(MavenAuditedView):
    read_permission = "read:structured-notes"
    delete_permission = "delete:structured-notes"
    create_permission = "create:structured-notes"
    edit_permission = "edit:structured-notes"

    edit_template = "recorded_answer_sets_edit_template.html"
    column_filters = [
        SchedulerUserIdIntEqualFilter(
            tools.get_columns_for_field(Schedule.user_id)[0], "Subject User Id"
        ),
        SchedulerUserIdIntNotEqualFilter(
            tools.get_columns_for_field(Schedule.user_id)[0], "Subject User Id"
        ),
        SchedulerUserIdIntGreaterFilter(
            tools.get_columns_for_field(Schedule.user_id)[0], "Subject User Id"
        ),
        SchedulerUserIdIntSmallerFilter(
            tools.get_columns_for_field(Schedule.user_id)[0], "Subject User Id"
        ),
        SchedulerUserIdFilterEmpty(
            tools.get_columns_for_field(Schedule.user_id)[0], "Subject User Id"
        ),
        SchedulerUserIdIntInListFilter(
            tools.get_columns_for_field(Schedule.user_id)[0], "Subject User Id"
        ),
        SchedulerUserIdIntNotInListFilter(
            tools.get_columns_for_field(Schedule.user_id)[0], "Subject User Id"
        ),
        "source_user_id",
        "appointment_id",
        "questionnaire.oid",
    ]
    column_list = (
        "appointment.member_schedule.user_id",
        "source_user_id",
        "appointment",
        "questionnaire.oid",
        "draft",
    )
    column_labels = {
        "appointment.member_schedule.user_id": "Subject User Id",
        "source_user_id": "Author User Id",
        "questionnaire.oid": "Questionnaire Type",
    }
    form_columns = ["submitted_at"]

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            RecordedAnswerSet,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
