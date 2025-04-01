import json

from models.questionnaires import (
    HEALTH_BINDER_QUESTIONNAIRE_OID,
    Answer,
    Question,
    Questionnaire,
    QuestionSet,
    QuestionTypes,
)
from storage.connection import db


def allergy_options_json():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    with open(
        "utils/migrations/create_health_binder_questionnaire_allergy_options.json"
    ) as f:
        return json.load(f)


def create_health_binder_questionnaire(dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    questionnaire = Questionnaire(oid=HEALTH_BINDER_QUESTIONNAIRE_OID, sort_order=0)

    # Basic info!!!!!!!!
    basic_info_question_set = QuestionSet(oid="basic_info", sort_order=0)
    basic_info_question_set.questions.append(
        Question(
            oid="dob",
            label="Date of birth",
            type=QuestionTypes.TEXT.value,
            sort_order=0,
            required=False,
        )
    )
    basic_info_question_set.questions.append(
        Question(
            oid="height",
            label="Height",
            type=QuestionTypes.TEXT.value,
            sort_order=1,
            required=False,
        )
    )
    basic_info_question_set.questions.append(
        Question(
            oid="weight",
            label="Weight",
            type=QuestionTypes.TEXT.value,
            sort_order=2,
            required=False,
        )
    )
    gender_multiselect_question = Question(
        oid="gender_select",
        label="Gender",
        type=QuestionTypes.CHECKBOX.value,
        sort_order=3,
        question_set_id=basic_info_question_set.id,
        required=False,
    )
    basic_info_question_set.questions.append(gender_multiselect_question)
    gender_multiselect_question.answers.append(
        Answer(oid="female", text="Female", sort_order=0)
    )
    gender_multiselect_question.answers.append(
        Answer(oid="male", text="Male", sort_order=1)
    )
    gender_multiselect_question.answers.append(
        Answer(oid="nonbinary", text="Nonbinary", sort_order=2)
    )
    gender_multiselect_question.answers.append(
        Answer(oid="other", text="Other", sort_order=3)
    )
    basic_info_question_set.questions.append(
        Question(
            oid="gender_describe",
            label="Please describe",
            type=QuestionTypes.TEXT.value,
            sort_order=4,
            required=False,
        )
    )
    questionnaire.question_sets.append(basic_info_question_set)
    print("Constructed basic info question set!")

    ##### Medication! #####
    medication_question_set = QuestionSet(
        oid="medication", questionnaire_id=questionnaire.id, sort_order=1
    )
    medication_question_set.questions.append(
        Question(
            oid="medication",
            label="Medications",
            type=QuestionTypes.MEDICATION.value,
            sort_order=0,
            required=False,
            non_db_answer_options_json={
                "common": [
                    "Cipro",
                    "Isotretinoin",
                    "Levofloxacin",
                    "Lithium",
                    "Phenobarbital",
                    "Tetracyclines",
                    "Topiramate",
                    "Valproate",
                    "Vitamin A",
                    "Warfarin",
                ]
            },
        )
    )
    questionnaire.question_sets.append(medication_question_set)
    print("Constructed medication question set!")

    ##### Allergy intolerance! #####
    allergy_question_set = QuestionSet(
        oid="allergy_intolerance", questionnaire_id=questionnaire.id, sort_order=2
    )
    allergy_question_set.questions.append(
        Question(
            oid="allergy_intolerance",
            label="Allergies",
            type=QuestionTypes.ALLERGY_INTOLERANCE.value,
            sort_order=0,
            required=False,
            non_db_answer_options_json=allergy_options_json(),
        )
    )
    questionnaire.question_sets.append(allergy_question_set)
    print("Constructed allergy intolerance question set!")

    ##### Condition! #####
    condition_question_set = QuestionSet(
        oid="condition", questionnaire_id=questionnaire.id, sort_order=3
    )
    condition_question_set.questions.append(
        Question(
            oid="condition",
            label="Medical conditions",
            type=QuestionTypes.CONDITION.value,
            sort_order=0,
            required=False,
            non_db_answer_options_json={
                "options": [
                    "Menstrual disorders (e.g. heavy periods, absent periods)",
                    "Infertility",
                    "Polycystic Ovarian Syndrome (PCOS)",
                    "Overweight or obesity",
                    "Hypertension (high blood pressure)",
                    "Diabetes or gestational diabetes",
                    "Hypothyroid or hyperthyroid (e.g. Hashimoto’s or Grave’s)",
                    "Endometriosis",
                    "Depression, anxiety, or mood disorder",
                    "Fibroids",
                    "Cancer",
                    "Eating disorders",
                ]
            },
        )
    )
    questionnaire.question_sets.append(condition_question_set)
    print("Constructed condition question set!")

    if dry_run:
        print("...But not committing any of them!")
    else:
        print("Now committing!")
        db.session.add_all(
            [
                questionnaire,
                basic_info_question_set,
                medication_question_set,
                allergy_question_set,
                condition_question_set,
            ]
        )

        db.session.commit()
