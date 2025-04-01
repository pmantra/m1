from __future__ import annotations

from collections import defaultdict

from appointments.utils import query_utils
from clinical_documentation.models.questionnaire import (
    AnswerStruct,
    QuestionnaireStruct,
    QuestionSetStruct,
    QuestionStruct,
)


class MemberQuestionnaireRepository:
    def __init__(self, session):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.session = session
        queries = query_utils.load_queries_from_file(
            "clinical_documentation/repository/queries/member_questionnaires.sql"
        )
        self._get_questionnaires_query = queries[0]
        self._get_questionnaire_oids_by_product_ids_query = queries[1]
        self._get_questionnaire_trigger_answers = queries[2]

    def get_questionnaires(self) -> list[QuestionnaireStruct]:
        results = self.session.execute(self._get_questionnaires_query)
        trigger_answer_results = self.session.execute(
            self._get_questionnaire_trigger_answers
        ).fetchall()
        # The results come back as a flattened list with the question sets and questions
        # embedded alongside the questionnaires, but we want to restore a hierarchical structure here.
        # For example:
        # [{'questionnaire_1', 'question_set_1', 'question_1'},
        #  {'questionnaire_1', 'question_set_2', 'question_2'}, ...]
        #
        # should be transformed into:
        # [{oid: questionnaire_1,
        #   question_sets: [
        #        {oid: question_set_1,
        #         questions: [
        #           {...},
        #           {...}, ...
        #         ]
        #        }, ...
        #   ]}, ...
        # ]
        questionnaires = {}
        question_sets = {}
        questions = {}
        answers = {}
        for result in results:
            questionnaire_id = result.questionnaire_id
            if questionnaire_id not in questionnaires:
                trigger_answer_ids = [
                    trigger_answer_result.trigger_answer_id
                    for trigger_answer_result in trigger_answer_results
                    if trigger_answer_result.questionnaire_id == questionnaire_id
                ]
                questionnaires[questionnaire_id] = QuestionnaireStruct(
                    id_=result.questionnaire_id,
                    oid=result.questionnaire_oid,
                    sort_order=result.questionnaire_sort_order,
                    title_text=result.questionnaire_title_text,
                    description_text=result.questionnaire_description_text,
                    intro_appointment_only=result.questionnaire_intro_appointment_only,
                    track_name=result.questionnaire_track_name,
                    question_sets=[],
                    trigger_answer_ids=list(set(trigger_answer_ids)),
                )

            question_set_id = result.question_set_id
            if question_set_id not in question_sets:
                question_set = QuestionSetStruct(
                    questionnaire_id=questionnaire_id,
                    id_=result.question_set_id,
                    oid=result.question_set_oid,
                    sort_order=result.question_set_sort_order,
                    questions=[],
                )
                question_sets[question_set_id] = question_set
                questionnaires[questionnaire_id].question_sets.append(question_set)

            question_id = result.question_id
            if question_id not in questions:
                question = QuestionStruct(
                    question_set_id=question_set_id,
                    id_=question_id,
                    oid=result.question_oid,
                    sort_order=result.question_sort_order,
                    label=result.question_label,
                    type_=result.question_type,
                    required=result.question_required,
                    answers=[],
                )
                questions[question_id] = question
                question_sets[question_set_id].questions.append(question)

            # Not all questions have corresponding answers, they could require text entry.
            # But if they have them we still need to gather them under the right question.
            answer_id = result.answer_id
            if answer_id and answer_id not in answers:
                answer = AnswerStruct(
                    id_=answer_id,
                    oid=result.answer_oid,
                    text=result.answer_text,
                    sort_order=result.answer_sort_order,
                )
                answers[answer_id] = answer
                questions[question_id].answers.append(answer)

        # now sort all of the elements by their ascending sort order
        sort_order_fn = lambda obj: obj.sort_order

        sorted_questionnaires = list(questionnaires.values())
        sorted_questionnaires.sort(key=sort_order_fn)

        for questionnaire in sorted_questionnaires:
            questionnaire.question_sets.sort(key=sort_order_fn)
            for question_set in questionnaire.question_sets:
                question_set.questions.sort(key=sort_order_fn)
                for question in question_set.questions:
                    question.answers.sort(key=sort_order_fn)

        return sorted_questionnaires

    def get_vertical_specific_member_rating_questionnaire_oids_by_product_id(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, product_ids
    ) -> dict[int, list[str]]:
        if not product_ids:
            return {}

        rv = defaultdict(list)
        results = self.session.execute(
            self._get_questionnaire_oids_by_product_ids_query,
            {"product_ids": product_ids},
        )
        for result in results:
            rv[result.product_id].append(result.questionnaire_oid)

        return rv
