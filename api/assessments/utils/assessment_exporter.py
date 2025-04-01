from __future__ import annotations

import enum
import warnings
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Iterable, Iterator, List, Mapping, Optional

from sqlalchemy.orm import load_only

from models.enterprise import Assessment, NeedsAssessment
from utils.data import calculate_bmi
from utils.log import logger

if TYPE_CHECKING:
    from authn.models.user import User

    QuestionNames = Iterable[str]


log = logger(__name__)


class AssessmentExportTopic(enum.Enum):
    """Export topics allow assessment answers to be exported for use in multiple problem domains."""

    ANALYTICS = "ANALYTICS"
    FHIR = "FHIR"


class AssessmentExportLogic(enum.Enum):
    """Export logic allows answers to be processed before being used as part of a particular export topic."""

    RAW = "RAW"
    BMI = "BMI"
    YES_NO = "YES_NO"
    FILTER_NULLS = "FILTER_NULLS"
    TEMPLATE_LABEL = "TEMPLATE_LABEL"


def _assessment_export_raw(a):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return a


def _assessment_export_bmi(a):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    weight = int(a.get("weight") or 0)
    height = int(a.get("height") or 0)
    if weight and height:
        return calculate_bmi(weight=weight, height=height) >= 30


def _assessment_export_yes_no(a):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return a == "yes"


def _assessment_export_filter_nulls(aa):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return [a for a in aa if a]


def _assessment_export_template_reference(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    raw_answer, question_id: int, assessment_template: Assessment
):
    question = next(
        (
            question
            for question in assessment_template.quiz_body.get("questions")
            if question["id"] == question_id
        ),
        {"widget": {"options": []}},
    )
    answer_options = next(
        (
            option
            for option in question["widget"]["options"]
            if (
                str(option["value"]) == str(raw_answer)
                or (option["value"] == "0" and raw_answer == '"0"')
            )
        ),
        {},
    )
    return answer_options.get("label", raw_answer)


_ASSESSMENT_EXPORT_LOGIC_REGISTRY = {
    AssessmentExportLogic.RAW: _assessment_export_raw,
    AssessmentExportLogic.BMI: _assessment_export_bmi,
    AssessmentExportLogic.YES_NO: _assessment_export_yes_no,
    AssessmentExportLogic.FILTER_NULLS: _assessment_export_filter_nulls,
    AssessmentExportLogic.TEMPLATE_LABEL: _assessment_export_template_reference,
}
assert all(v in _ASSESSMENT_EXPORT_LOGIC_REGISTRY for v in AssessmentExportLogic)


@dataclass
class ExportedAnswer:
    """An answer retrieved from a needs assessment, exported with the configured logic for a particular topic."""

    __slots__ = (
        "assessment_id",
        "assessment_lifecycle_type",
        "question_id",
        "assessment_export_topic",
        "question_name",
        "assessment_export_logic",
        "user_id",
        "needs_assessment_id",
        "needs_assessment_modified_at",
        "raw_answer",
        "exported_answer",
        "flagged",
    )
    assessment_id: int
    assessment_lifecycle_type: str
    question_id: int

    assessment_export_topic: AssessmentExportTopic
    question_name: str
    assessment_export_logic: AssessmentExportLogic

    user_id: int
    needs_assessment_id: int
    needs_assessment_modified_at: datetime

    raw_answer: Any
    exported_answer: Any
    flagged: bool


class AssessmentExporter:
    """AssessmentExporter provides an efficient mechanism for exporting answers from NeedsAssessments.

    In order to access assessment data using this class, questions must be configured with an export object, mapping an
    AssessmentExportTopic value to a question_name and export_logic. This structure allows the same question to be
    exported differently as needed for different topics:
    ```
    { 'questions': [
      { 'id': 1,
        'export': {
          'ANALYTICS': { 'question_name': 'some_name_a', 'export_logic': 'RAW' },
          'RISK_FACTOR': { 'question_name': 'some_name_b', 'export_logic': 'YES_NO' }
        }
      },
      { 'id': 2,
        'export': { 'question_name': 'some_name_c', 'export_logic': 'RAW' }  # Defaults to ANALYTICS topic
      }
    ]}
    ```
    AssessmentExporter parses the configuration data described above and maintains lookup tables used subsequently when
    exporting answers from needs assessments. Building lookup tables allows each assessment to be parsed no more than
    once - and provides us with an index of which assessments contain answers for a given question_name.
    """

    @classmethod
    def for_user_assessments(cls, user: User) -> AssessmentExporter:
        """Provides an exporter with the given user's assessments fetched and parsed."""
        return cls._populated_exporter(user=user)

    @classmethod
    def for_all_assessments(cls) -> AssessmentExporter:
        """Provides an exporter with all assessments fetched and parsed."""
        return cls._populated_exporter(user=None)

    @classmethod
    def _populated_exporter(cls, user: Optional[User]) -> AssessmentExporter:
        exporter = AssessmentExporter()
        query = Assessment.query.options(load_only(Assessment.id, Assessment.quiz_body))
        if user is not None:
            query = query.join(NeedsAssessment).filter(NeedsAssessment.user == user)
            exporter._prepopulated_user = True
        else:
            exporter._prepopulated_all = True
        for assessment in query:
            exporter._update_lookup_tables(assessment)
        return exporter

    def __init__(self) -> None:
        warnings.warn(  # noqa  B028  TODO:  No explicit stacklevel keyword argument found. The warn method from the warnings module uses a stacklevel of 1 by default. This will only show a stack trace for the line on which the warn method is called. It is therefore recommended to use a stacklevel of 2 or greater to provide more information to the user.
            """#pod-care-management This data type is now managed in the HDC service API.
            Try:
                X-Maven-User-Id={user_id}
                GET /api/hdc/v1/
            """,
            DeprecationWarning,
        )

        self._prepopulated_user = False
        self._prepopulated_all = False
        self._export_lookup = {topic: {} for topic in AssessmentExportTopic}
        self._assessment_ids_by_question_name = {
            topic: defaultdict(set) for topic in AssessmentExportTopic
        }

    def _update_lookup_tables(self, assessment: Assessment):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        aid = assessment.id
        log.debug("Updating lookup table from assessment.", assessment_id=aid)
        for topic_lookup in self._export_lookup.values():
            topic_lookup[aid] = {}

        questions = assessment.quiz_body and assessment.quiz_body.get("questions")
        if not isinstance(questions, list):
            log.error(
                "Could not establish exporters for assessment with no questions list.",
                assessment_id=aid,
            )
            return
        for question_index, question in enumerate(questions):
            # parse id:
            if "id" not in question:
                log.error(
                    "Could not establish exporter for question with no question id.",
                    assessment_id=aid,
                    question_index=question_index,
                )
                continue
            qid = question["id"]

            # parse export:
            if "export" not in question:
                log.debug(
                    "Will not export question without export field.",
                    assessment_id=aid,
                    question_index=question_index,
                )
                continue
            export = question["export"]

            for topic, topic_export in export.items():
                # parse topic:
                try:
                    topic = AssessmentExportTopic(topic)
                except ValueError as e:
                    log.error(
                        "Could not parse topic in export object.",
                        assessment_id=aid,
                        question_id=qid,
                        exception=e,
                    )
                    continue

                # parse question_name:
                question_name = topic_export.get("question_name")
                if not isinstance(question_name, str):
                    log.error(
                        "Could not establish exporter for question with no question_name string.",
                        assessment_id=aid,
                        question_id=qid,
                    )
                    continue

                # parse export_logic
                try:
                    logic = AssessmentExportLogic(topic_export.get("export_logic"))
                except ValueError:
                    log.error(
                        "Could not establish exporter for question with invalid export_logic.",
                        assessment_id=aid,
                        question_id=qid,
                    )
                    continue

                self._export_lookup[topic][aid][qid] = (question_name, logic)
                self._assessment_ids_by_question_name[topic][question_name].add(aid)

    def assessment_ids_by_topic(self, topic: AssessmentExportTopic) -> List[int]:
        """The set of assessment ids already found to export answers for the given topic."""
        assert self._prepopulated_all, (
            "The method you are calling relies on lookup tables being prepopulated with all assessments. Please "
            "instantiate this exporter using AssessmentExporter.for_all_assessments()."
        )
        return list(
            {aid for aid, lookup in self._export_lookup[topic].items() if lookup}
        )

    def _assessment_ids_by_question_names(
        self, topic: AssessmentExportTopic, question_names: QuestionNames
    ) -> List[int]:
        """The set of assessment ids already found to export answers for the given topic and question names."""
        assert self._prepopulated_user or self._prepopulated_all, (
            "The method you are calling relies on lookup tables being prepopulated with user assessments. Please "
            "instantiate this exporter using AssessmentExporter.for_user_assessments(user) for a specific user or "
            "AssessmentExporter.for_all_assessments() for processing multiple users' assessments."
        )
        return list(
            set().union(
                *(
                    self._assessment_ids_by_question_name[topic][question_name]
                    for question_name in question_names
                )
            )
        )

    def most_recent_answers_for(
        self, user: User, topic: AssessmentExportTopic, question_names: QuestionNames
    ) -> Mapping[str, Optional[ExportedAnswer]]:
        """Export the user's most current answers to the given topic and question_names.

        Args:
            user: The user for which we are establishing assessment answers.
            topic: The topic for which answers are being exported.
            question_names: The set of questions for which answers are being exported.

        Returns:
            A mapping of requested question_name values to the matching answer from the most recently modified needs
            assessment, or None if the User has not answered the requested question.
        """
        question_names = set(question_names)
        result = {q: None for q in question_names}
        for answer in self.all_answers_for(user, topic, question_names):
            result[answer.question_name] = answer  # type: ignore[assignment] # Incompatible types in assignment (expression has type "ExportedAnswer", target has type "None")
            # stop the generator from exporting more answers to this question
            question_names.remove(answer.question_name)
            if not question_names:
                break
        return result

    def all_answers_for(
        self,
        user: User,
        topic: AssessmentExportTopic,
        question_names: QuestionNames,
        after: datetime = None,  # type: ignore[assignment] # Incompatible default for argument "after" (default has type "None", argument has type "datetime")
        before: datetime = None,  # type: ignore[assignment] # Incompatible default for argument "before" (default has type "None", argument has type "datetime")
    ) -> Iterator[ExportedAnswer]:
        """Export all of the user's answers to the given topic and question_names.
        Use `after` and `before` arguments to filter by creation date.

        Args:
            user: The user for which we are establishing assessment answers.
            topic: The topic for which answers are being exported.
            question_names: The set of questions for which answers are being exported.
            after: Limit to needs assessments created on or after a datetime.
            before: Limit to needs assessments created before a datetime.

        Yields:
            The next matching answer starting from the most recently modified needs assessment.
        """
        assessment_ids = self._assessment_ids_by_question_names(topic, question_names)
        date_filters = []
        if after:
            date_filters.append(NeedsAssessment.created_at >= after)
        if before:
            date_filters.append(NeedsAssessment.created_at < before)

        needs_assessments = (
            NeedsAssessment.query.options(
                load_only(
                    NeedsAssessment.id,
                    NeedsAssessment.assessment_id,
                    NeedsAssessment.json,
                    NeedsAssessment.modified_at,
                )
            )
            .filter(
                NeedsAssessment.user == user,
                NeedsAssessment.assessment_id.in_(assessment_ids),
                *date_filters,
            )
            .order_by(NeedsAssessment.modified_at.desc())
        )
        for needs_assessment in needs_assessments:
            yield from self.answers_from_needs_assessment(
                needs_assessment, topic, question_names
            )

    def answers_from_needs_assessment(
        self,
        needs_assessment: NeedsAssessment,
        topic: AssessmentExportTopic,
        question_names: Optional[QuestionNames] = None,
    ) -> Iterator[ExportedAnswer]:
        """Export answers from needs_assessment for the given topic, optionally filtering by question_names.

        Args:
            needs_assessment: The source of user answers being exported.
            topic: The specific topic for which we are exporting answers.
            question_names: If provided, constrains exporting answers to the given questions.

        Yields:
            The next matching answer.
        """
        naid = needs_assessment.id
        aid = needs_assessment.assessment_id
        alc_type = needs_assessment.type and needs_assessment.type.value
        lookup_cache_hit = aid in self._export_lookup[topic]
        log.debug(
            "Exporting answers from needs assessment.",
            needs_assessment_id=naid,
            assessment_export_topic=topic.value,
            question_names=question_names and ", ".join(question_names),
            lookup_cache_hit=lookup_cache_hit,
        )
        if not lookup_cache_hit:
            self._update_lookup_tables(needs_assessment.assessment_template)

        lookup = self._export_lookup[topic][aid]
        if not lookup:
            log.error(
                "Could not export answers for needs assessment with no questions."
            )
            return  # there are no questions to export

        answers = needs_assessment.json and needs_assessment.json.get("answers")
        if not isinstance(answers, list):
            log.error(
                "Could not establish answers for needs assessment with no answers list.",
                needs_assessment_id=naid,
            )
            return

        for answer_index, answer in enumerate(answers):
            try:
                qid = answer["id"]
            except KeyError:
                log.error(
                    "Could not establish exporter for answer with no id.",
                    needs_assessment_id=naid,
                    answer_index=answer_index,
                )
                continue

            try:
                e_question_name, logic = lookup[qid]
            except KeyError:
                continue  # question not exported

            if question_names is not None and e_question_name not in question_names:
                continue  # question did not match target name

            try:
                raw_answer = answer["body"]
            except KeyError:
                log.error(
                    "Could not export answer with no body value.",
                    needs_assessment_id=naid,
                    answer_id=qid,
                )
                continue

            try:
                if logic == AssessmentExportLogic.TEMPLATE_LABEL:
                    exported_answer = _ASSESSMENT_EXPORT_LOGIC_REGISTRY[logic](
                        raw_answer, qid, needs_assessment.assessment_template
                    )
                else:
                    exported_answer = _ASSESSMENT_EXPORT_LOGIC_REGISTRY[logic](
                        raw_answer
                    )
            except Exception as e:
                log.error(
                    "Exception raised while exporting answer from needs assessment.",
                    needs_assessment_id=naid,
                    answer_id=qid,
                    assessment_export_logic=logic.value,
                    exception=e,
                )
                continue

            yield ExportedAnswer(
                assessment_id=aid,  # type: ignore[arg-type] # Argument "assessment_id" to "ExportedAnswer" has incompatible type "Optional[Any]"; expected "int"
                assessment_lifecycle_type=alc_type,
                question_id=qid,
                assessment_export_topic=topic,
                question_name=e_question_name,
                assessment_export_logic=logic,
                user_id=needs_assessment.user_id,  # type: ignore[arg-type] # Argument "user_id" to "ExportedAnswer" has incompatible type "Optional[Any]"; expected "int"
                needs_assessment_id=naid,
                needs_assessment_modified_at=needs_assessment.modified_at,
                raw_answer=raw_answer,
                exported_answer=exported_answer,
                flagged=answer.get("flagged", False),
            )
