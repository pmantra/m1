from datetime import datetime
from typing import Optional, Union

from flask import request
from flask_restful import abort
from marshmallow import Schema
from marshmallow import fields as fields_v3
from marshmallow_v1 import fields
from sqlalchemy.orm.exc import NoResultFound

from assessments.utils.assessment_exporter import (
    AssessmentExporter,
    AssessmentExportTopic,
)
from authn.models.user import User
from common import stats
from common.services.api import AuthenticatedResource, PermissionedCareTeamResource
from models.enterprise import (
    Assessment,
    AssessmentLifecycle,
    NeedsAssessment,
    NeedsAssessmentTypes,
)
from storage.connection import db
from utils.data import calculate_bmi
from utils.log import logger
from views.schemas.common import (
    CSVStringField,
    MavenSchema,
    PaginableArgsSchema,
    PaginableOutputSchema,
)

log = logger(__name__)


def bmi_overweight(answer) -> Optional[bool]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    bmi = bmi_from_height_weight(answer)
    return bmi and 25.0 <= bmi < 30.0


def bmi_obesity(answer) -> Optional[bool]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    bmi = bmi_from_height_weight(answer)
    return bmi and 30.0 <= bmi


def bmi_from_height_weight(a):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    weight = int(a.get("weight") or 0)
    height = int(a.get("height") or 0)
    if weight and height:
        return calculate_bmi(weight=weight, height=height)


class QuestionSchema(MavenSchema):
    body = fields.String()
    subtext = fields.List(fields.String, allow_none=True)
    id = fields.Integer()
    next = fields.Raw()
    widget = fields.Raw()
    healthbinder = fields.Raw()
    required = fields.Boolean()


class QuizBodySchema(MavenSchema):
    attrs = fields.Raw()
    questions = fields.Nested(QuestionSchema, many=True)


class AssessmentSchema(MavenSchema):
    id = fields.Integer(required=True)
    title = fields.String(required=True)
    type = fields.Method("get_assessment_type")
    description = fields.String()
    icon = fields.String()
    slug = fields.String()
    estimated_time = fields.Integer()  # time in seconds
    module_names = fields.List(fields.String())
    meta = fields.Method("get_meta")
    question_json = fields.Method("get_question_json")

    def get_assessment_type(self, obj):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return obj.type.value if obj else ""

    def get_meta(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """Get User Metadata
        Note: currently completed flag is true if there is ever
        an associated NeedsAssessment that has been completed.
        Logic can change here to be determined by the latest NeedsAssessment's completed status.
        """
        if (
            db.session.query(NeedsAssessment)
            .filter(
                NeedsAssessment.user == context.get("user"),
                NeedsAssessment.assessment_template == obj,
                NeedsAssessment.completed.is_(True),
            )
            .count()
        ):
            completed = True
        else:
            completed = False

        return {"completed": completed, "version": obj.version}

    def get_question_json(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if context and context.get("include_json"):
            schema = QuizBodySchema(context=context)
            return schema.dump(obj.quiz_body).data


class AssessmentsSchema(PaginableOutputSchema):
    data = fields.Nested(AssessmentSchema, many=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Nested", base class "PaginableOutputSchema" defined the type as "Raw")


class AssessmentsGetArgsSchema(PaginableArgsSchema):
    type = CSVStringField(required=False)
    version = fields.String()
    module = fields.String()
    phase = fields.String()
    include_json = fields.Boolean()


class AssessmentsResource(AuthenticatedResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        args = AssessmentsGetArgsSchema().load(request.args).data
        types = args.get("type")
        version = args.get("version")
        module = args.get("module")
        phase = args.get("phase")
        alcs = db.session.query(AssessmentLifecycle)
        if types:
            valid_na_types = {t.value for t in NeedsAssessmentTypes}
            if not set(types).issubset(valid_na_types):
                abort(400, message="Wrong assessment type specified!")
            alcs = alcs.filter(AssessmentLifecycle.type.in_(args["type"]))

        data = [lc.current_assessment_for_user(self.user) for lc in alcs.all()]

        if version:
            data = [a for a in data if str(a.version) == version]

        if module:
            _module_filtered = []
            for a in data:
                if any(
                    (p.module and p.module.name == module) for p in a.lifecycle.phases
                ):
                    _module_filtered.append(a)
            data = _module_filtered

        if phase:
            _phase_filtered = []
            for a in data:
                if any(p.name == phase for p in a.lifecycle.phases):
                    _phase_filtered.append(a)
            data = _phase_filtered

        total = len(data)
        s, e = args["offset"], (args["offset"] + args["limit"])
        results = {
            "data": data[s:e],
            "pagination": {
                "total": total,
                "limit": args["limit"],
                "offset": args["offset"],
            },
        }
        return (
            AssessmentsSchema(
                context={"user": self.user, "include_json": args.get("include_json")}
            )
            .dump(results)
            .data
        )


class AssessmentResource(AuthenticatedResource):
    def get(self, assessment_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        args = AssessmentsGetArgsSchema().load(request.args).data
        assessment = Assessment.query.get(assessment_id)
        if not assessment:
            abort(404, message="Assessment Not Found")

        return (
            AssessmentSchema(
                context={"user": self.user, "include_json": args.get("include_json")}
            )
            .dump(assessment)
            .data
        )


class UserAssessmentAnswerSchema(Schema):
    assessment_id = fields_v3.Integer()
    assessment_lifecycle_type = fields_v3.String()
    question_id = fields_v3.Integer()
    question_name = fields_v3.String()
    modified_at = fields_v3.DateTime(attribute="needs_assessment_modified_at")
    raw_answer = fields_v3.Raw()
    body = fields_v3.Raw(attribute="exported_answer")
    flagged = fields_v3.Boolean()


class UserAssessmentAnswersResource(PermissionedCareTeamResource):
    def get(self, user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            user = db.session.query(User).filter(User.id == user_id).one()
        except NoResultFound:
            abort(404, message="User %d invalid." % user_id)
        self._user_has_access_to_user_or_403(self.user, user)

        if not user.is_enterprise:
            abort(403, message="Not authorized for marketplace Users")

        assessment_lifecycle_type = request.args.get("assessment_lifecycle_type")
        assessment_id = request.args.get("assessment_id")

        needs_assessments = NeedsAssessment.get_latest_by_user_id_and_lifecycle_type(
            user_id, assessment_id, assessment_lifecycle_type
        )

        if not needs_assessments:
            return []

        exporter = AssessmentExporter()
        exported_answers = [
            exporter.answers_from_needs_assessment(na, AssessmentExportTopic.ANALYTICS)
            for na in needs_assessments
        ]

        ret = []
        for ea in exported_answers:
            answer = UserAssessmentAnswerSchema().dump(ea, many=True)
            if answer:
                ret.extend(answer)

        return ret


def create_assessment_update_tagging(
    resource: str,
    action: str,
    init_needs_assessment: Union[NeedsAssessment, None],
    committed_needs_assessment: NeedsAssessment,
    completed: bool = None,  # type: ignore[assignment] # Incompatible default for argument "completed" (default has type "None", argument has type "bool")
) -> None:

    metric_name = f"api.views.assessements.{resource}.{action}"
    assessment_type = committed_needs_assessment.type.name

    if completed:
        current_status = "completed"
    else:
        current_status = committed_needs_assessment.status

    init_status = (
        "new_creation" if not init_needs_assessment else init_needs_assessment.status
    )

    stats.increment(
        metric_name=metric_name,
        pod_name=stats.PodNames.PERSONALIZED_CARE,
        tags=[
            f"assessment_type:{assessment_type}",
            f"assessment_current_status:{current_status}",
            f"assessment_init_status:{init_status}",
        ],
    )

    # Add log of time to complete assessment
    if init_needs_assessment:
        time_metric = metric_name + ".time_from_needs_assessment_creation"
        assessment_start = init_needs_assessment.created_at
        time_diff = datetime.utcnow() - assessment_start
        stats.histogram(
            metric_name=time_metric,
            pod_name=stats.PodNames.PERSONALIZED_CARE,
            tags=[
                f"assessment_type:{assessment_type}",
                f"assessment_current_status:{current_status}",
                f"assessment_init_status:{init_status}",
            ],
            metric_value=time_diff.total_seconds(),
        )
