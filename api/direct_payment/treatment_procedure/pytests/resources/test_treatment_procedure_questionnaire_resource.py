import json


class TestTreatmentProcedureQuestionnairesResource:
    def test_get_treatment_procedure_questionnaire_unauthorized(
        self,
        factories,
        client,
        api_helpers,
    ):
        # Arrange
        user = factories.DefaultUserFactory.create()

        # Act
        res = client.get(
            "/api/v1/direct_payment/treatment_procedure_questionnaires",
            headers=api_helpers.json_headers(user=user),
        )

        # Assert
        assert res.status_code == 401

    def test_get_treatment_procedure_questionnaires_when_none_exist(
        self,
        client,
        api_helpers,
        fc_user,
    ):
        # Act
        res = client.get(
            "/api/v1/direct_payment/treatment_procedure_questionnaires",
            headers=api_helpers.json_headers(user=fc_user),
        )

        # Assert
        assert res.status_code == 404

    def test_get_treatment_procedure_questionnaires_shape(
        self,
        client,
        api_helpers,
        fc_user,
        questionnaire_global_procedures,
    ):
        # Act
        res = client.get(
            "/api/v1/direct_payment/treatment_procedure_questionnaires",
            headers=api_helpers.json_headers(user=fc_user),
        )

        # Assert
        assert res.status_code == 200

        res_data = json.loads(res.data)
        questionnaires = res_data["questionnaires"]

        assert questionnaires
        assert len(questionnaires) == (
            len(questionnaire_global_procedures) - 1
        )  # - 1 for the duplicate questionnaire in the fixture
        for entry in questionnaire_global_procedures:
            match = next(
                (
                    questionnaire
                    for questionnaire in questionnaires
                    if questionnaire["id"]
                    == str(
                        entry.questionnaire_id
                    )  # when serialized, the ids are converted to strings
                ),
                None,
            )
            assert entry.global_procedure_id in match["global_procedure_ids"]

    def test_post_treatment_procedure_questionnaire_unauthorized(
        self,
        factories,
        client,
        api_helpers,
    ):
        # Arrange
        user = factories.DefaultUserFactory.create()

        # Act
        res = client.post(
            "/api/v1/direct_payment/treatment_procedure_questionnaires",
            headers=api_helpers.json_headers(user=user),
        )

        # Assert
        assert res.status_code == 401

    def test_post_treatment_procedure_questionnaires_without_payload(
        self,
        client,
        api_helpers,
        fc_user,
    ):
        # Act
        res = client.post(
            "/api/v1/direct_payment/treatment_procedure_questionnaires",
            headers=api_helpers.json_headers(user=fc_user),
            data=json.dumps({}),
        )

        # Assert
        assert res.status_code == 400
        assert (
            json.loads(res.get_data().decode("utf-8")).get("message")
            == "Invalid request body. Must include treatment_procedure_id and questionnaires"
        )

    def test_post_treatment_procedure_questionnaires_with_invalid_treatment_procedure(
        self,
        client,
        api_helpers,
        fc_user,
        treatment_procedure,
        treatment_procedure_recorded_answer_set_questionnaire,
    ):
        # Arrange
        questionnaire_id = treatment_procedure_recorded_answer_set_questionnaire[
            "questionnaire_id"
        ]
        questions = treatment_procedure_recorded_answer_set_questionnaire["questions"]
        request_args = {
            "treatment_procedure_id": treatment_procedure.id + 1,
            "questionnaires": [
                {"questionnaire_id": questionnaire_id, "questions": questions}
            ],
        }

        # Act
        res = client.post(
            "/api/v1/direct_payment/treatment_procedure_questionnaires",
            headers=api_helpers.json_headers(user=fc_user),
            data=json.dumps(request_args),
        )

        # Assert
        assert res.status_code == 400
        assert (
            json.loads(res.get_data().decode("utf-8")).get("message")
            == "Could not find treatment procedure"
        )

    def test_post_treatment_procedure_questionnaires_with_no_table_data(
        self,
        client,
        api_helpers,
        fc_user,
        treatment_procedure,
    ):
        # Arrange
        request_args = {
            "treatment_procedure_id": treatment_procedure.id,
            "questionnaires": [
                {
                    "questionnaire_id": 1,
                    "questions": [
                        {
                            "question_id": 1,
                            "answer_id": 1,
                        },
                    ],
                }
            ],
        }

        # Act
        res = client.post(
            "/api/v1/direct_payment/treatment_procedure_questionnaires",
            headers=api_helpers.json_headers(user=fc_user),
            data=json.dumps(request_args),
        )

        # Assert
        assert res.status_code == 500

    def test_post_treatment_procedure_questionnaires_success(
        self,
        client,
        api_helpers,
        fc_user,
        treatment_procedure,
        treatment_procedure_recorded_answer_set_questionnaire,
    ):
        # Arrange
        questionnaire_id = treatment_procedure_recorded_answer_set_questionnaire[
            "questionnaire_id"
        ]
        questions = treatment_procedure_recorded_answer_set_questionnaire["questions"]
        request_args = {
            "treatment_procedure_id": treatment_procedure.id,
            "questionnaires": [
                {"questionnaire_id": questionnaire_id, "questions": questions}
            ],
        }

        # Act
        res = client.post(
            "/api/v1/direct_payment/treatment_procedure_questionnaires",
            headers=api_helpers.json_headers(user=fc_user),
            data=json.dumps(request_args),
        )

        # Assert
        assert res.status_code == 200
