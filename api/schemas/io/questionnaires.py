from sqlalchemy.orm import joinedload

from authz.models.roles import Role
from models.questionnaires import (
    Answer,
    Question,
    Questionnaire,
    QuestionSet,
    questionnaire_role,
    questionnaire_trigger_answer,
    questionnaire_vertical,
)
from models.verticals_and_specialties import Vertical
from storage.connection import db


def export():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    questionnaires = (
        db.session.query(Questionnaire)
        .options(
            joinedload(Questionnaire.trigger_answers),
            joinedload(Questionnaire.verticals),
            joinedload(Questionnaire.roles),
            joinedload(Questionnaire.question_sets)
            .joinedload(QuestionSet.questions)
            .joinedload(Question.answers),
        )
        .all()
    )

    return [
        dict(
            sort_order=questionnaire.sort_order,
            oid=questionnaire.oid,
            title_text=questionnaire.title_text,
            description_text=questionnaire.description_text,
            trigger_answers=_trigger_answers(questionnaire.trigger_answers),
            verticals=[v.name for v in questionnaire.verticals],
            roles=[r.name for r in questionnaire.roles],
            question_sets=[
                dict(
                    sort_order=qs.sort_order,
                    oid=qs.oid,
                    prerequisite_answer=_prerequisite_answer_or_none(
                        qs.prerequisite_answer
                    ),
                    questions=[
                        dict(
                            sort_order=q.sort_order,
                            label=q.label,
                            type=q.type.value,
                            required=q.required,
                            oid=q.oid,
                            non_db_answer_options_json=q.non_db_answer_options_json,
                            answers=[
                                dict(sort_order=a.sort_order, text=a.text, oid=a.oid)
                                for a in q.answers
                            ],
                        )
                        for q in qs.questions
                    ],
                )
                for qs in questionnaire.question_sets
            ],
        )
        for questionnaire in questionnaires
    ]


def _trigger_answers(trigger_answers):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if trigger_answers:
        return [
            trigger_answer.question.oid + "," + trigger_answer.oid
            for trigger_answer in trigger_answers
        ]
    else:
        return trigger_answers


def _prerequisite_answer_or_none(prereq_answer):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if prereq_answer:
        return prereq_answer.question.oid + "," + prereq_answer.oid
    else:
        return None


def restore(questionnaire_dicts):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    questionnaires_with_trigger_answers = {}
    question_sets_with_prerequisite_answers = {}
    vertical_id_by_name = {
        v.name: v.id for v in db.session.query(Vertical.name, Vertical.id).all()
    }
    role_id_by_name = {r.name: r.id for r in db.session.query(Role.name, Role.id).all()}
    db.session.bulk_insert_mappings(Questionnaire, questionnaire_dicts)
    questionnaire_id_by_oid = {
        q.oid: q.id for q in db.session.query(Questionnaire.oid, Questionnaire.id).all()
    }
    questionnaires_verticals = []
    questionnaires_roles = []
    question_sets = []
    questions = []
    answers = []
    # Simulating an autoinc so we can easily keep our relationships in one pass.
    q_set_inc = 0
    q_inc = 0
    for questionnaire in questionnaire_dicts:
        questionnaire_id = questionnaire_id_by_oid[questionnaire["oid"]]
        if questionnaire["trigger_answers"]:
            questionnaires_with_trigger_answers[questionnaire_id] = questionnaire[
                "trigger_answers"
            ]
        questionnaires_verticals.extend(
            {
                "questionnaire_id": questionnaire_id,
                "vertical_id": vertical_id_by_name[v],
            }
            for v in {*questionnaire["verticals"]} & vertical_id_by_name.keys()
        )
        questionnaires_roles.extend(
            {"questionnaire_id": questionnaire_id, "role_id": role_id_by_name[r]}
            for r in {*questionnaire["roles"]} & role_id_by_name.keys()
        )
        for q_set in questionnaire["question_sets"]:
            q_set_inc += 1
            q_set.update(id=q_set_inc, questionnaire_id=questionnaire_id)
            if q_set["prerequisite_answer"]:
                question_sets_with_prerequisite_answers[q_set_inc] = q_set[
                    "prerequisite_answer"
                ]
            for question in q_set["questions"]:
                q_inc += 1
                question.update(id=q_inc, question_set_id=q_set_inc)
                for answer in question["answers"]:
                    answer.update(question_id=q_inc)
                answers.extend(question["answers"])
            questions.extend(q_set["questions"])
        question_sets.extend(questionnaire["question_sets"])
    # Create all the child objects
    db.session.execute(questionnaire_vertical.insert(), questionnaires_verticals)
    db.session.execute(questionnaire_role.insert(), questionnaires_roles)
    db.session.bulk_insert_mappings(QuestionSet, question_sets)
    db.session.bulk_insert_mappings(Question, questions)
    db.session.bulk_insert_mappings(Answer, answers)
    # Get a mapping of key to answer id
    answer_id_by_key = {
        (a.q_oid, a.oid): a.id
        for a in db.session.query(Question.oid.label("q_oid"), Answer.oid, Answer.id)
        .select_from(Answer)
        .join(Question)
        .all()
    }
    # Update objects with dependent relationships
    # Trigger answers
    if questionnaires_with_trigger_answers:
        questionnaires_trigger_answers = []
        for (
            questionnaire_id,
            trigger_answers,
        ) in questionnaires_with_trigger_answers.items():
            questionnaires_trigger_answers.extend(
                {
                    "questionnaire_id": questionnaire_id,
                    "answer_id": answer_id_by_key[tuple(ta.split(","))],
                }
                for ta in trigger_answers
            )
        db.session.execute(
            questionnaire_trigger_answer.insert(), questionnaires_trigger_answers
        )
    # Prereq answers
    if question_sets_with_prerequisite_answers:
        question_sets_prereq_answers = [
            {
                "id": q_set_id,
                "prerequisite_answer_id": answer_id_by_key[tuple(akey.split(","))],
            }
            for q_set_id, akey in question_sets_with_prerequisite_answers.items()
        ]
        db.session.bulk_update_mappings(QuestionSet, question_sets_prereq_answers)
