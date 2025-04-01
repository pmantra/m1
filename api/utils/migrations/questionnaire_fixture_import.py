"""
questionnaire_fixture_import.py

Import a data_admin formatted questionnaire fixture into an environment without data_admin.
Used on Prod to get around the lack of data admin in one specific import case.
If there have been changes to the fixture schemas, this script and the export will need updates.
Try: kubectl exec -it <api shell pod> -- python ./utils/migrations/questionnaire_fixture_import.py --fixture=

Usage:
  questionnaire_fixture_import.py --fixture=<json_spec_string>

Options:
  --fixture=<json_spec_string>  Give the script the relevant json fixture as a string.
  -h --help                     Show this screen.
"""
import enum
import json

from docopt import docopt
from marshmallow_v1 import fields

from app import create_app
from models.questionnaires import (
    Answer,
    Question,
    Questionnaire,
    QuestionSet,
    QuestionTypes,
)
from models.verticals_and_specialties import Vertical
from storage.connection import db
from views.schemas.common import MavenDateTime, MavenSchema


class QuestionnaireSchema(MavenSchema):
    sort_order = fields.Integer()
    oid = fields.String()
    title_text = fields.String()
    description_text = fields.String()


class QuestionSetSchema(MavenSchema):
    sort_order = fields.Integer()
    oid = fields.String()
    prerequisite_answer_id = fields.Integer()
    questionnaire_id = fields.Integer()
    soft_deleted_at = MavenDateTime()


class QuestionSchema(MavenSchema):
    question_set_id = fields.Integer()
    sort_order = fields.Integer()
    label = fields.String()
    # Had to write this as question_type to not conflict with maker
    question_type = fields.Enum(
        choices=[t.value for t in QuestionTypes], default=QuestionTypes.TEXT.value
    )
    required = fields.Boolean(default=False)
    oid = fields.String()
    soft_deleted_at = MavenDateTime()


class AnswerSchema(MavenSchema):
    question_id = fields.Integer()
    sort_order = fields.Integer()
    text = fields.String()
    oid = fields.String()
    soft_deleted_at = MavenDateTime()


class _MakerBase(object):
    spec_class = None


class QuestionnaireMaker(_MakerBase):
    spec_class = QuestionnaireSchema()  # type: ignore[assignment] # Incompatible types in assignment (expression has type "QuestionnaireSchema", base class "_MakerBase" defined the type as "None")

    def create_object(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        spec_data = self.spec_class.load(spec).data  # type: ignore[has-type] # Cannot determine type of "spec_class"
        questionnaire = Questionnaire(
            sort_order=spec_data.get("sort_order"),
            oid=spec_data.get("oid"),
            title_text=spec_data.get("title_text"),
            description_text=spec_data.get("description_text"),
        )

        if "verticals" in spec and isinstance(spec.get("verticals"), list):
            for vertical_name in spec.get("verticals"):
                vertical = Vertical.query.filter_by(name=vertical_name).first()
                if vertical:
                    questionnaire.verticals.append(vertical)
                else:
                    print("No vertical exists with name: '%s'" % vertical_name, "error")

        db.session.add(questionnaire)
        db.session.commit()

        if "question_sets" in spec and isinstance(spec.get("question_sets"), list):
            for qs_spec in spec.get("question_sets"):
                QuestionSetMaker().create_object(qs_spec, questionnaire.id)

        return questionnaire


class QuestionSetMaker(_MakerBase):
    spec_class = QuestionSetSchema()  # type: ignore[assignment] # Incompatible types in assignment (expression has type "QuestionSetSchema", base class "_MakerBase" defined the type as "None")

    def create_object(self, spec, questionnaire_id=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        spec_data = self.spec_class.load(spec).data  # type: ignore[has-type] # Cannot determine type of "spec_class"
        question_set = QuestionSet(
            sort_order=spec_data.get("sort_order"),
            oid=spec_data.get("oid"),
            prerequisite_answer=spec_data.get("prerequisite_answer"),
            questionnaire_id=spec_data.get("questionnaire_id", questionnaire_id),
            soft_deleted_at=spec_data.get("soft_deleted_at"),
        )

        db.session.add(question_set)
        db.session.commit()

        if "questions" in spec and isinstance(spec.get("questions"), list):
            for q_spec in spec.get("questions"):
                QuestionMaker().create_object(q_spec, question_set.id)

        return question_set


class QuestionMaker(_MakerBase):
    spec_class = QuestionSchema()  # type: ignore[assignment] # Incompatible types in assignment (expression has type "QuestionSchema", base class "_MakerBase" defined the type as "None")

    def create_object(self, spec, question_set_id=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        spec_data = self.spec_class.load(spec).data  # type: ignore[has-type] # Cannot determine type of "spec_class"

        question = Question(
            question_set_id=spec_data.get("question_set_id", question_set_id),
            sort_order=spec_data.get("sort_order"),
            label=spec_data.get("label"),
            type=spec_data.get("question_type"),
            required=spec_data.get("required"),
            oid=spec_data.get("oid"),
            soft_deleted_at=spec_data.get("soft_deleted_at"),
        )

        db.session.add(question)
        db.session.commit()

        if "answers" in spec and isinstance(spec.get("answers"), list):
            for answer_spec in spec.get("answers"):
                AnswerMaker().create_object(answer_spec, question.id)

        return question


class AnswerMaker(_MakerBase):
    spec_class = AnswerSchema()  # type: ignore[assignment] # Incompatible types in assignment (expression has type "AnswerSchema", base class "_MakerBase" defined the type as "None")

    def create_object(self, spec, question_id=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        spec_data = self.spec_class.load(spec).data  # type: ignore[has-type] # Cannot determine type of "spec_class"
        answer = Answer(
            question_id=spec_data.get("question_id", question_id),
            sort_order=spec_data.get("sort_order"),
            text=spec_data.get("text"),
            oid=spec_data.get("oid"),
            soft_deleted_at=spec_data.get("soft_deleted_at"),
        )

        db.session.add(answer)
        db.session.commit()

        return answer


class FixtureSpecs(enum.Enum):
    # Map a type string to a class
    questionnaire = QuestionnaireMaker
    question_set = QuestionSetMaker
    question = QuestionMaker
    answer = AnswerMaker


class FixtureDataMaker:
    spec_class = None

    def __init__(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not spec:
            raise ValueError("No spec!")

        # spec is the dictionary of data translated from the JSON
        self.spec = spec

        # raise a KeyError if 'type' not in spec
        _obj_type = self.spec["type"]

        # raise a KeyError if 'type' is bad
        self.maker = FixtureSpecs[_obj_type].value()

    def validate(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            errors = self.maker.spec_class.validate(spec)
        except Exception as e:
            print("Schema errors: %s" % e, "error")
            return
        else:
            if errors:
                print("Schema errors: %s" % errors, "error")
                return

    def create(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self.maker.spec_class:
            _bad = self.validate(self.spec)
            if _bad:
                return _bad

        return self.maker.create_object(self.spec)


def import_fixture(json_list_of_specs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    with db.session.begin_nested():
        for spec in json_list_of_specs:
            if spec.get("type") not in [fs.name for fs in FixtureSpecs]:
                print("Invalid spec type: %s" % spec.get("type"), "error")
                break
            try:
                with db.session.begin_nested():
                    result = FixtureDataMaker(spec).create()
            except Exception as e:
                print(f"Got error applying fixture: {str(e)}")
                db.session.rollback()
                break
            if not result:
                break
    print("Done")
    return


if __name__ == "__main__":
    args = docopt(__doc__)
    with create_app().app_context():
        json_spec = args["--fixture"]
        import_fixture(json.loads(json_spec))
