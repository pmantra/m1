from authz.models.roles import ROLES
from clinical_documentation.repository.member_questionnaires import (
    MemberQuestionnaireRepository,
)
from pytests.db_util import enable_db_performance_warnings


def test_get_member_questionnaires(db, factories):
    questionnaires = [
        factories.EmptyQuestionnaireFactory.create(
            oid="cancellation_survey", sort_order=1
        ),
        factories.EmptyQuestionnaireFactory.create(
            oid="member_rating_v2", sort_order=0
        ),
    ]

    for questionnaire in questionnaires:
        for i in range(0, 2):
            qs = factories.EmptyQuestionSetFactory.create(
                questionnaire_id=questionnaire.id,
                oid=f"{questionnaire.oid},{i}",
                sort_order=i,
            )
            for j in range(0, 2):
                q = factories.EmptyQuestionFactory.create(
                    question_set_id=qs.id, label=f"{i},{j}", sort_order=1 - j
                )
                if j:
                    factories.AnswerFactory.create(
                        question_id=q.id, text=f"{i},{j}", sort_order=0
                    )

    with enable_db_performance_warnings(
        database=db,
        failure_threshold=4,
    ):
        questionnaires = MemberQuestionnaireRepository(db.session).get_questionnaires()

    actual = [
        {
            "oid": questionnaire.oid,
            "sort_order": questionnaire.sort_order,
            "question_sets": [
                {
                    "oid": question_set.oid,
                    "sort_order": question_set.sort_order,
                    "questions": [
                        {
                            "label": question.label,
                            "sort_order": question.sort_order,
                            "answers": [
                                {"text": answer.text} for answer in question.answers
                            ],
                        }
                        for question in question_set.questions
                    ],
                }
                for question_set in questionnaire.question_sets
            ],
        }
        for questionnaire in questionnaires
    ]
    expected = [
        {
            "oid": "member_rating_v2",
            "sort_order": 0,
            "question_sets": [
                {
                    "oid": "member_rating_v2,0",
                    "sort_order": 0,
                    "questions": [
                        {"label": "0,1", "sort_order": 0, "answers": [{"text": "0,1"}]},
                        {"label": "0,0", "sort_order": 1, "answers": []},
                    ],
                },
                {
                    "oid": "member_rating_v2,1",
                    "sort_order": 1,
                    "questions": [
                        {"label": "1,1", "sort_order": 0, "answers": [{"text": "1,1"}]},
                        {"label": "1,0", "sort_order": 1, "answers": []},
                    ],
                },
            ],
        },
        {
            "oid": "cancellation_survey",
            "sort_order": 1,
            "question_sets": [
                {
                    "oid": "cancellation_survey,0",
                    "sort_order": 0,
                    "questions": [
                        {"label": "0,1", "sort_order": 0, "answers": [{"text": "0,1"}]},
                        {"label": "0,0", "sort_order": 1, "answers": []},
                    ],
                },
                {
                    "oid": "cancellation_survey,1",
                    "sort_order": 1,
                    "questions": [
                        {"label": "1,1", "sort_order": 0, "answers": [{"text": "1,1"}]},
                        {"label": "1,0", "sort_order": 1, "answers": []},
                    ],
                },
            ],
        },
    ]
    assert expected == actual


def test_get_vertical_specific_questionnaire_oids_by_product_id_no_specific(
    db, factories
):
    product = factories.ProductFactory.create()
    results = MemberQuestionnaireRepository(
        db.session
    ).get_vertical_specific_member_rating_questionnaire_oids_by_product_id([product.id])
    assert {} == results


def test_get_vertical_specific_questionnaire_oids_by_product_id_with_specific(
    db, factories
):
    product = factories.ProductFactory.create()

    # Add the ca-vertical-specific questionnaire
    member_role = factories.RoleFactory.create(name=ROLES.member)
    ca_questionnaire_oid = "member_rating_ca"
    factories.QuestionnaireFactory.create(
        oid=ca_questionnaire_oid,
        verticals=[product.vertical],
        roles=[member_role],
    )
    db.session.commit()

    results = MemberQuestionnaireRepository(
        db.session
    ).get_vertical_specific_member_rating_questionnaire_oids_by_product_id([product.id])
    assert {product.id: ["member_rating_ca"]} == results


def test_get_vertical_specific_questionnaire_oids_by_product_id_with_no_ids(db):
    results = MemberQuestionnaireRepository(
        db.session
    ).get_vertical_specific_member_rating_questionnaire_oids_by_product_id([])
    assert {} == results
