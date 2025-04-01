import datetime
import json

from models.profiles import PractitionerProfile
from pytests.factories import VerticalFactory

now = datetime.datetime.utcnow()


class TestGetAsyncEncounterSummariesResource:
    def test_get_async_encounter_summaries_unauthorized(
        self,
        client,
        api_helpers,
        member,
    ):
        # Act
        res = client.post(
            f"/api/v1/members/{member.id}/async_encounter_summaries",
            headers=api_helpers.json_headers(None),
            data=json.dumps({}),
        )

        # Assert
        assert res.status_code == 401

    def test_get_async_encounter_summaries_not_allowed(
        self,
        client,
        api_helpers,
        member,
        new_practitioner_allergist,
    ):
        # Act
        res = client.post(
            f"/api/v1/members/{member.id}/async_encounter_summaries",
            headers=api_helpers.json_headers(user=new_practitioner_allergist),
            data=json.dumps({}),
        )

        # Assert
        assert res.status_code == 403

    def test_get_async_encounter_summaries_member_not_exist(
        self,
        client,
        api_helpers,
        member,
        valid_appointment,
        new_practitioner,
    ):
        # Arrange
        fake_number = 234234098203984

        # Act
        res = client.post(
            f"/api/v1/members/{fake_number}/async_encounter_summaries",
            headers=api_helpers.json_headers(user=new_practitioner),
            data=json.dumps({}),
        )

        # Assert
        assert res.status_code == 404

    def test_get_async_encounter_summaries_no_note_sharing(
        self,
        client,
        api_helpers,
        async_encounter_summary_answer,
        async_encounter_summary_second,
        async_encounter_summary_third,
    ):
        # Arrange
        async_encounter_summary_first = (
            async_encounter_summary_answer.async_encounter_summary
        )
        filters = {}
        async_encounter_summary_second.user.member_profile.json[
            "opted_in_notes_sharing"
        ] = False

        # Act
        res = client.get(
            f"/api/v1/members/{async_encounter_summary_second.user_id}/async_encounter_summaries",
            headers=api_helpers.json_headers(
                user=async_encounter_summary_second.provider
            ),
            query_string=filters,
        )

        # Assert
        assert res.status_code == 200
        async_encounter_summary_data = api_helpers.load_json(res)["data"]
        assert len(async_encounter_summary_data) == 2
        assert (
            async_encounter_summary_data[0]["id"] == async_encounter_summary_second.id
        )
        assert async_encounter_summary_data[1]["id"] == async_encounter_summary_first.id

    def test_get_async_encounter_summaries_filter_my_encounters(
        self,
        client,
        api_helpers,
        async_encounter_summary_answer,
        async_encounter_summary_second,
        async_encounter_summary_third,
    ):
        # Arrange
        async_encounter_summary_first = (
            async_encounter_summary_answer.async_encounter_summary
        )
        filters = {
            "my_encounters": True,
        }
        async_encounter_summary_second.user.member_profile.json[
            "opted_in_notes_sharing"
        ] = False

        # Act
        res = client.get(
            f"/api/v1/members/{async_encounter_summary_second.user_id}/async_encounter_summaries",
            headers=api_helpers.json_headers(
                user=async_encounter_summary_second.provider
            ),
            query_string=filters,
        )

        # Assert
        assert res.status_code == 200
        async_encounter_summary_data = api_helpers.load_json(res)["data"]
        assert len(async_encounter_summary_data) == 2
        assert (
            async_encounter_summary_data[0]["id"] == async_encounter_summary_second.id
        )
        assert async_encounter_summary_data[1]["id"] == async_encounter_summary_first.id

    def test_get_async_encounter_summaries_no_additional_filters(
        self,
        client,
        api_helpers,
        async_encounter_summary_answer,
        async_encounter_summary_second,
        async_encounter_summary_third,
    ):
        # Arrange
        async_encounter_summary_first = (
            async_encounter_summary_answer.async_encounter_summary
        )
        filters = {}
        async_encounter_summary_second.user.member_profile.json[
            "opted_in_notes_sharing"
        ] = True
        async_encounter_third_practitioner_profile = PractitionerProfile.query.get(
            async_encounter_summary_third.provider_id
        )
        async_encounter_third_practitioner_profile.first_name = "Gina"
        async_encounter_third_practitioner_profile.last_name = "Bob"
        obgyn_vertical = VerticalFactory(name="OB-GYN")
        allergist_vertical = VerticalFactory(name="Allergist")
        async_encounter_third_practitioner_profile.verticals = [
            obgyn_vertical,
            allergist_vertical,
        ]
        question_id = (
            async_encounter_summary_third.questionnaire.question_sets[0].questions[0].id
        )
        question_id_2 = (
            async_encounter_summary_third.questionnaire.question_sets[0].questions[1].id
        )
        answer_id = (
            async_encounter_summary_third.questionnaire.question_sets[0]
            .questions[0]
            .answers[0]
            .id
        )

        # Act
        res = client.get(
            f"/api/v1/members/{async_encounter_summary_second.user_id}/async_encounter_summaries",
            headers=api_helpers.json_headers(
                user=async_encounter_summary_second.provider
            ),
            query_string=filters,
        )

        # Assert
        assert res.status_code == 200
        async_encounter_summary_data = api_helpers.load_json(res)["data"]
        assert len(async_encounter_summary_data) == 3
        assert async_encounter_summary_data[0]["id"] == async_encounter_summary_third.id
        assert async_encounter_summary_data[0]["provider_first_name"] == "Gina"
        assert async_encounter_summary_data[0]["provider_last_name"] == "Bob"
        assert async_encounter_summary_data[0]["provider_verticals"] == [
            "OB-GYN",
            "Allergist",
        ]
        assert (
            async_encounter_summary_data[1]["id"] == async_encounter_summary_second.id
        )
        assert async_encounter_summary_data[2]["id"] == async_encounter_summary_first.id
        # test questionnaire data
        questionnaire_data = async_encounter_summary_data[0]["questionnaire"]
        assert questionnaire_data["id"] == str(
            async_encounter_summary_third.questionnaire.id
        )
        assert (str(question_id) and str(question_id_2)) in [
            question["id"]
            for question in questionnaire_data["question_sets"][0]["questions"]
        ]
        assert str(answer_id) in [
            answer["id"]
            for answer in questionnaire_data["question_sets"][0]["questions"][0][
                "answers"
            ]
        ]

    def test_get_async_encounter_summaries_test_limit(
        self,
        client,
        api_helpers,
        async_encounter_summary_answer,
        async_encounter_summary_second,
        async_encounter_summary_third,
        async_encounter_summary_fourth,
        async_encounter_summary_fifth,
        async_encounter_summary_sixth,
        async_encounter_summary_seventh,
        async_encounter_summary_eighth,
        async_encounter_summary_ninth,
        async_encounter_summary_tenth,
        async_encounter_summary_eleventh,
    ):
        # Arrange
        filters = {}
        async_encounter_summary_second.user.member_profile.json[
            "opted_in_notes_sharing"
        ] = True

        # Act
        res = client.get(
            f"/api/v1/members/{async_encounter_summary_second.user_id}/async_encounter_summaries",
            headers=api_helpers.json_headers(
                user=async_encounter_summary_second.provider
            ),
            query_string=filters,
        )

        # Assert
        assert res.status_code == 200
        async_encounter_summary_data = api_helpers.load_json(res)["data"]
        assert len(async_encounter_summary_data) == 10

    def test_get_async_encounter_summaries_filter_provider_types(
        self,
        client,
        api_helpers,
        async_encounter_summary_answer,
        async_encounter_summary_second,
        async_encounter_summary_third,
    ):
        # Arrange
        async_encounter_summary_first = (
            async_encounter_summary_answer.async_encounter_summary
        )
        filters = {
            "provider_types": ["Care Advocate", "Nurse Practitioner"],
            "my_encounters": True,
        }
        async_encounter_summary_second.user.member_profile.json[
            "opted_in_notes_sharing"
        ] = False

        # Act
        res = client.get(
            f"/api/v1/members/{async_encounter_summary_second.user_id}/async_encounter_summaries",
            headers=api_helpers.json_headers(
                user=async_encounter_summary_second.provider
            ),
            query_string=filters,
        )

        # Assert
        assert res.status_code == 200
        async_encounter_summary_data = api_helpers.load_json(res)["data"]
        assert len(async_encounter_summary_data) == 2
        assert (
            async_encounter_summary_data[0]["id"] == async_encounter_summary_second.id
        )
        assert async_encounter_summary_data[1]["id"] == async_encounter_summary_first.id

    def test_get_async_encounter_summaries_filter_provider_types_querystring(
        self,
        client,
        api_helpers,
        async_encounter_summary_answer,
        async_encounter_summary_second,
        async_encounter_summary_third,
    ):
        # Arrange
        async_encounter_summary_first = (
            async_encounter_summary_answer.async_encounter_summary
        )
        filters = "?provider_types=Care+Advocate&provider_types=Nurse+Practitioner"
        async_encounter_summary_second.user.member_profile.json[
            "opted_in_notes_sharing"
        ] = False

        # Act
        res = client.get(
            f"/api/v1/members/{async_encounter_summary_second.user_id}/async_encounter_summaries{filters}",
            headers=api_helpers.json_headers(
                user=async_encounter_summary_second.provider
            ),
        )

        # Assert
        assert res.status_code == 200
        async_encounter_summary_data = api_helpers.load_json(res)["data"]
        assert len(async_encounter_summary_data) == 2
        assert (
            async_encounter_summary_data[0]["id"] == async_encounter_summary_second.id
        )
        assert async_encounter_summary_data[1]["id"] == async_encounter_summary_first.id

    def test_get_async_encounter_summaries_filter_scheduled_start(
        self,
        client,
        api_helpers,
        async_encounter_summary_answer,
        async_encounter_summary_second,
        async_encounter_summary_third,
    ):
        # Arrange
        filters = {
            "scheduled_start": now - datetime.timedelta(hours=6),
        }
        async_encounter_summary_second.user.member_profile.json[
            "opted_in_notes_sharing"
        ] = True

        # Act
        res = client.get(
            f"/api/v1/members/{async_encounter_summary_second.user_id}/async_encounter_summaries",
            headers=api_helpers.json_headers(
                user=async_encounter_summary_second.provider
            ),
            query_string=filters,
        )

        # Assert
        assert res.status_code == 200
        async_encounter_summary_data = api_helpers.load_json(res)["data"]
        assert len(async_encounter_summary_data) == 1
        assert async_encounter_summary_data[0]["id"] == async_encounter_summary_third.id

    def test_get_async_encounter_summaries_filter_scheduled_end(
        self,
        client,
        api_helpers,
        async_encounter_summary_answer,
        async_encounter_summary_second,
        async_encounter_summary_third,
    ):
        # Arrange
        async_encounter_summary_first = (
            async_encounter_summary_answer.async_encounter_summary
        )
        filters = {
            "scheduled_end": now - datetime.timedelta(hours=6),
        }
        async_encounter_summary_third.user.member_profile.json[
            "opted_in_notes_sharing"
        ] = True

        # Act
        res = client.get(
            f"/api/v1/members/{async_encounter_summary_second.user_id}/async_encounter_summaries",
            headers=api_helpers.json_headers(
                user=async_encounter_summary_second.provider
            ),
            query_string=filters,
        )

        # Assert
        assert res.status_code == 200
        async_encounter_summary_data = api_helpers.load_json(res)["data"]
        assert len(async_encounter_summary_data) == 2
        assert (
            async_encounter_summary_data[0]["id"] == async_encounter_summary_second.id
        )
        assert async_encounter_summary_data[1]["id"] == async_encounter_summary_first.id

    class TestPostAsyncEncounterSummariesResource:
        def test_post_async_encounter_summaries_unauthorized(
            self,
            client,
            api_helpers,
            member,
        ):
            # Act
            res = client.post(
                f"/api/v1/members/{member.id}/async_encounter_summaries",
                headers=api_helpers.json_headers(None),
                data=json.dumps({}),
            )

            # Assert
            assert res.status_code == 401

        def test_post_async_encounter_summaries_not_allowed(
            self,
            client,
            api_helpers,
            member,
            valid_appointment,
            new_practitioner,
        ):
            # Act
            res = client.post(
                f"/api/v1/members/{member.id}/async_encounter_summaries",
                headers=api_helpers.json_headers(user=new_practitioner),
                data=json.dumps({}),
            )

            # Assert
            assert res.status_code == 403
            assert (
                json.loads(res.get_data().decode("utf-8")).get("errors")[0]["detail"]
                == "You do not have access to that target user's information."
            )

        def test_post_async_encounter_summaries_without_required_request_payload(
            self,
            client,
            api_helpers,
            practitioner_user,
            valid_appointment,
        ):
            # Arrange
            data = {
                "async_encounter_summary": {
                    "async_encounter_summary_answers": [
                        {
                            "question_id": "888888",
                        }
                    ],
                    "questionnaire_id": "11111111",
                    "encounter_date": "2023-12-25T14:00:00",
                }
            }

            # Act
            res = client.post(
                f"/api/v1/members/{valid_appointment.member_schedule.user.id}/async_encounter_summaries",
                headers=api_helpers.json_headers(user=practitioner_user),
                json=data,
            )

            # Assert
            assert res.status_code == 400
            assert (
                json.loads(res.get_data().decode("utf-8")).get("message")
                == "Invalid request body. Answers must include answer_id, text or date."
            )

        def test_post_async_encounter_summaries_member_not_found(
            self,
            client,
            api_helpers,
            member,
            practitioner_user,
        ):
            # Act
            res = client.post(
                "/api/v1/members/1234567890000/async_encounter_summaries",
                headers=api_helpers.json_headers(user=practitioner_user),
                data=json.dumps(
                    {
                        "async_encounter_summary": {
                            "async_encounter_summary_answers": [
                                {
                                    "answer_id": "77777777",
                                    "question_id": "888888",
                                },
                                {
                                    "question_id": "234234",
                                    "text": "This is an answer",
                                },
                            ],
                            "questionnaire_id": "11111111",
                            "encounter_date": "2023-12-25T14:00:00",
                        }
                    }
                ),
            )

            # Assert
            assert res.status_code == 404
            assert (
                json.loads(res.get_data().decode("utf-8")).get("message")
                == "Member not found."
            )

        def test_post_async_encounter_summaries_success(
            self,
            client,
            api_helpers,
            practitioner_user,
            valid_appointment,
            questionnaire,
        ):
            # Arrange
            question_id = str(questionnaire.question_sets[0].questions[0].id)
            question_id_2 = str(questionnaire.question_sets[0].questions[1].id)
            answer_id = str(questionnaire.question_sets[0].questions[0].answers[0].id)
            text = "This is an answer"
            encounter_date = "2023-12-25T14:00:00"
            data = {
                "async_encounter_summary": {
                    "async_encounter_summary_answers": [
                        {
                            "answer_id": answer_id,
                            "question_id": question_id,
                        },
                        {
                            "question_id": question_id_2,
                            "text": text,
                        },
                    ],
                    "questionnaire_id": str(questionnaire.id),
                    "encounter_date": encounter_date,
                }
            }

            # Act
            res = client.post(
                f"/api/v1/members/{valid_appointment.member_schedule.user.id}/async_encounter_summaries",
                headers=api_helpers.json_headers(user=practitioner_user),
                json=data,
            )

            # Assert
            assert res.status_code == 200
            async_encounter_summary = api_helpers.load_json(res)[
                "async_encounter_summary"
            ]
            async_encounter_summary_answers = async_encounter_summary[
                "async_encounter_summary_answers"
            ]
            assert async_encounter_summary["questionnaire_id"] == str(questionnaire.id)
            assert async_encounter_summary["encounter_date"] == encounter_date
            assert (question_id and question_id_2) in [
                data["question_id"] for data in async_encounter_summary_answers
            ]
            assert answer_id in [
                data["answer_id"] for data in async_encounter_summary_answers
            ]
            assert text in [data["text"] for data in async_encounter_summary_answers]
