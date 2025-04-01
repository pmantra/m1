provider_appointment = {
    "id": 997948328,
    "appointment_id": 100,
    "scheduled_start": "2024-03-21T10:00:00",
    "scheduled_end": "2024-03-21T10:15:00",
    "cancelled_at": None,
    "cancellation_policy": "conservative",
    "cancelled_note": "cancelled by patient",
    "member_started_at": "2024-03-21T10:00:00",
    "member_ended_at": "2024-03-21T10:14:00",
    "member_disconnected_at": "2024-03-21T10:05:00",
    "practitioner_started_at": "2024-03-21T10:00:00",
    "practitioner_ended_at": "2024-03-21T10:14:09",
    "practitioner_disconnected_at": "2024-03-21T10:05:01",
    "phone_call_at": "2024-03-21T10:00:01",
    "privacy": "basic",
    "privilege_type": "standard",
    "purpose": "birth_planning",
    "state": "PAYMENT_PENDING",
    "pre_session": {
        "created_at": None,
        "draft": None,
        "notes": "pre-session notes",
    },
    "post_session": {
        "created_at": "2024-03-22T10:00:00",
        "draft": False,
        "notes": "post-session notes",
    },
    "need": {
        "id": 1,
        "name": "egg freeze",
        "description": "timeline for egg freeze",
    },
    "video": None,
    "product": {
        "practitioner": {
            "id": 1,
            "name": "Stephanie Schmitt",
            "profiles": {
                "practitioner": {
                    "can_prescribe": True,
                    "messaging_enabled": True,
                    "certified_subdivision_codes": ["US-NY"],
                    "vertical_objects": [{"id": 1, "filter_by_state": True}],
                },
                "member": None,
            },
        },
        "vertical_id": 4,
    },
    "member": {
        "id": 2,
        "name": "Alice Johnson",
        "first_name": "Alice",
        "email": "alice.johnson@xxx.com",
        "created_at": "2022-01-01T00:00:00",
        "country": None,
        "organization": {
            "name": "test org",
            "education_only": False,
            "rx_enabled": True,
            "vertical_group_version": "",
            "display_name": "",
            "benefits_url": None,
        },
        "profiles": {
            "member": {
                "care_plan_id": 1,
                "subdivision_code": "US-NY",
                "state": "NY",
                "tel_number": "tel:+1-212-555-1515",
            },
            "practitioner": None,
        },
    },
    "prescription_info": {
        "enabled": False,
        "pharmacy_id": "1",
        "pharmacy_info": {
            "PharmacyId": "1",
            "Pharmacy": "test pharma",
            "State": "NY",
            "ZipCode": "10027",
            "PrimaryFax": "555-555-5555",
            "StoreName": "999 Pharmacy",
            "Address1": "999 999th St",
            "Address2": "",
            "PrimaryPhone": "555-555-5556",
            "PrimaryPhoneType": "Work",
            "City": "NEW YORK",
            "IsPreferred": True,
            "IsDefault": False,
            "ServiceLevel": 9,
        },
    },
    "rx_enabled": False,
    "rx_reason": "pharmacy_info_not_added",
    "rx_written_via": "dosespot",
    "structured_internal_note": {
        "question_sets": [
            {
                "id": "1",
                "oid": "coaching_notes_coaching_providers",
                "prerequisite_answer_id": None,
                "questions": [
                    {
                        "answers": [
                            {
                                "id": "1",
                                "oid": "coaching_notes_coaching_providers",
                                "soft_deleted_at": None,
                                "sort_order": 1,
                                "text": "test text",
                            }
                        ],
                        "id": "1",
                        "label": "label",
                        "non_db_answer_options_json": None,
                        "oid": "coaching_notes_coaching_providers",
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
        "questionnaire": {
            "description_text": "description",
            "id": "1",
            "oid": "coaching_notes_coaching_providers",
            "question_sets": [
                {
                    "id": "1",
                    "oid": "coaching_notes_coaching_providers",
                    "prerequisite_answer_id": None,
                    "questions": [
                        {
                            "answers": [
                                {
                                    "id": "1",
                                    "oid": "coaching_notes_coaching_providers",
                                    "soft_deleted_at": None,
                                    "sort_order": 1,
                                    "text": "test text",
                                }
                            ],
                            "id": "1",
                            "label": "label",
                            "non_db_answer_options_json": None,
                            "oid": "coaching_notes_coaching_providers",
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
        "recorded_answer_set": {
            "appointment_id": 997948365,
            "draft": False,
            "id": "1",
            "modified_at": "2024-02-01T00:00:00+00:00",
            "questionnaire_id": "1",
            "recorded_answers": [
                {
                    "answer_id": "1",
                    "appointment_id": 997948365,
                    "date": "2024-03-22",
                    "payload": {
                        "text": "test_text",
                    },
                    "question_id": "1",
                    "question_type": "CONDITION",
                    "text": "test_text",
                    "user_id": 1,
                }
            ],
            "source_user_id": 1,
            "submitted_at": "2024-01-01T00:00:00+00:00",
        },
        "recorded_answers": [
            {
                "answer_id": "1",
                "appointment_id": 997948365,
                "date": "2024-03-22",
                "payload": {
                    "text": "test_text",
                },
                "question_id": "1",
                "question_type": "CONDITION",
                "text": "test_text",
                "user_id": 1,
            }
        ],
    },
    "provider_addenda": {
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
            "oid": "coaching_notes_coaching_providers",
            "question_sets": [
                {
                    "id": "1",
                    "oid": "coaching_notes_coaching_providers",
                    "prerequisite_answer_id": None,
                    "questions": [
                        {
                            "answers": [
                                {
                                    "id": "1",
                                    "oid": "coaching_notes_coaching_providers",
                                    "soft_deleted_at": None,
                                    "sort_order": 1,
                                    "text": "test text",
                                }
                            ],
                            "id": "1",
                            "label": "label",
                            "non_db_answer_options_json": None,
                            "oid": "coaching_notes_coaching_providers",
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
    },
}
