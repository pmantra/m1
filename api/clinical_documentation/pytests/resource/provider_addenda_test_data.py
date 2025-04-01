provider_addenda_and_questionnaire = {
    "provider_addenda": [
        {
            "appointment_id": 997948365,
            "associated_answer_id": "",
            "associated_question_id": "",
            "id": "1",
            "provider_addendum_answers": [
                {
                    "answer_id": "1",
                    "date": "2024-01-01",
                    "question_id": "1",
                    "text": "test text",
                }
            ],
            "questionnaire_id": "1",
            "submitted_at": "2024-01-01T00:00:00+00:00",
            "user_id": 1,
        }
    ],
    "questionnaire": {
        "description_text": "description",
        "id": "1",
        "oid": "addendum_notes",
        "question_sets": [
            {
                "id": "1",
                "oid": "addendum_notes",
                "prerequisite_answer_id": None,
                "questions": [
                    {
                        "answers": [
                            {
                                "id": "1",
                                "oid": "addendum_notes",
                                "soft_deleted_at": None,
                                "sort_order": 1,
                                "text": "test text",
                            }
                        ],
                        "id": "1",
                        "label": "label",
                        "non_db_answer_options_json": None,
                        "oid": "addendum_notes",
                        "required": False,
                        "soft_deleted_at": None,
                        "sort_order": 1,
                        "type": "CONDITION",
                    }
                ],
                "soft_deleted_at": None,
                "sort_order": 1,
            }
        ],
        "soft_deleted_at": None,
        "sort_order": 1,
        "title_text": "title",
        "trigger_answer_ids": ["1"],
    },
}

error_message_missing_practitioner_id = {
    "description": "Missing or empty 'practitioner_id' request argument(s)."
}

error_message_missing_appointment_id = {
    "description": "Missing or empty 'appointment_id' request argument(s)."
}

error_message_missing_appointment_id_and_practitioner_id = {
    "description": "Missing or empty 'appointment_id' and Missing or empty 'practitioner_id' request argument(s)."
}
