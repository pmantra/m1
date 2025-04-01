-- get_recorded_answer_set
SELECT
    id,
    questionnaire_id,
    modified_at,
    submitted_at,
    source_user_id,
    draft,
    appointment_id
FROM recorded_answer_set
WHERE recorded_answer_set.appointment_id = :appointment_id
    AND recorded_answer_set.source_user_id = :practitioner_id
ORDER BY recorded_answer_set.submitted_at DESC;

-- get_questionnaire_by_recorded_answer_set
SELECT
    questionnaire.id,
    questionnaire.sort_order,
    questionnaire.oid,
    questionnaire.title_text,
    questionnaire.description_text,
    questionnaire.soft_deleted_at
FROM recorded_answer_set
LEFT OUTER JOIN questionnaire ON questionnaire.id = recorded_answer_set.questionnaire_id
WHERE recorded_answer_set.appointment_id = :appointment_id
    AND recorded_answer_set.source_user_id = :practitioner_id
ORDER BY recorded_answer_set.submitted_at DESC;

-- get_questionnaires_by_practitioner
SELECT
    questionnaire.id,
    questionnaire.sort_order,
    questionnaire.oid,
    questionnaire.title_text,
    questionnaire.description_text,
    questionnaire.soft_deleted_at
FROM questionnaire
JOIN questionnaire_vertical ON questionnaire.id = questionnaire_vertical.questionnaire_id
JOIN practitioner_verticals
    ON questionnaire_vertical.vertical_id = practitioner_verticals.vertical_id
WHERE practitioner_verticals.user_id = :practitioner_id
    AND (questionnaire.oid IS NULL OR questionnaire.oid NOT LIKE :async_encounter_oid_prefix)
GROUP BY questionnaire.id
ORDER BY questionnaire.id DESC;

-- get_questionnaire_by_oid
SELECT
    id,
    sort_order,
    oid,
    title_text,
    description_text,
    soft_deleted_at
FROM questionnaire
WHERE oid = :oid;

-- get_question_sets_by_questionnaire_id
SELECT
    id,
    oid,
    sort_order,
    prerequisite_answer_id,
    soft_deleted_at
FROM question_set
WHERE questionnaire_id = :questionnaire_id AND soft_deleted_at IS NULL;

-- get_questions_by_question_set_ids
SELECT
    id,
    sort_order,
    label,
    type,
    required,
    oid,
    non_db_answer_options_json,
    soft_deleted_at,
    question_set_id
FROM question
WHERE question_set_id IN :question_set_ids AND soft_deleted_at IS NULL;

-- get_answers_by_question_ids
SELECT
    id,
    sort_order,
    text,
    oid,
    soft_deleted_at,
    question_id
FROM answer
WHERE question_id IN :question_ids AND soft_deleted_at IS NULL;

-- get_recorded_answers_by_recorded_answer_set_id
SELECT
    recorded_answer.appointment_id,
    recorded_answer.question_id,
    recorded_answer.answer_id,
    recorded_answer.user_id,
    recorded_answer.payload AS payload_string,
    recorded_answer.text,
    recorded_answer.date,
    question.type           AS question_type_in_enum
FROM recorded_answer
LEFT OUTER JOIN question ON recorded_answer.question_id = question.id
WHERE recorded_answer.recorded_answer_set_id = :recorded_answer_set_id;

-- get_legacy_recorded_answers
 SELECT
    recorded_answer.appointment_id,
    recorded_answer.question_id,
    recorded_answer.answer_id,
    recorded_answer.user_id,
    recorded_answer.payload AS payload_string,
    recorded_answer.text,
    recorded_answer.date,
    question.type           AS question_type_in_enum
FROM recorded_answer
LEFT OUTER JOIN question ON recorded_answer.question_id = question.id
WHERE recorded_answer.appointment_id = :appointment_id AND recorded_answer.user_id = :practitioner_id;

-- get_roles_for_questionnaires
SELECT
    questionnaire.id AS questionnaire_id,
    role.name AS role_name
FROM questionnaire
JOIN questionnaire_role ON questionnaire.id = questionnaire_role.questionnaire_id
JOIN role ON questionnaire_role.role_id = role.id
WHERE questionnaire.id IN :questionnaire_ids
ORDER BY questionnaire.id;

-- get_trigger_answer_ids
SELECT answer.id
FROM questionnaire
JOIN questionnaire_trigger_answer ON questionnaire.id = questionnaire_trigger_answer.questionnaire_id
JOIN answer ON questionnaire_trigger_answer.answer_id = answer.id
WHERE questionnaire.id = :questionnaire_id;

-- get_provider_addenda
SELECT
    id,
    appointment_id,
    questionnaire_id,
    user_id,
    submitted_at,
    associated_answer_id
FROM provider_addendum
WHERE appointment_id = :appointment_id
  AND user_id = :practitioner_id
  AND questionnaire_id = :questionnaire_id
ORDER BY submitted_at;

-- get_provider_addenda_answers
SELECT
    question_id,
    answer_id,
    text,
    date,
    addendum_id
FROM provider_addendum_answer
WHERE addendum_id IN :addendum_ids
ORDER BY question_id;


-- get_question_sets_by_questionnaire_id_with_soft_deleted_data
SELECT
    id,
    oid,
    sort_order,
    prerequisite_answer_id,
    soft_deleted_at
FROM question_set
WHERE questionnaire_id = :questionnaire_id;


-- get_questions_by_question_set_ids_with_soft_deleted_data
SELECT
    id,
    sort_order,
    label,
    type,
    required,
    oid,
    non_db_answer_options_json,
    soft_deleted_at,
    question_set_id
FROM question
WHERE question_set_id IN :question_set_ids;


-- get_answers_by_question_ids_with_soft_deleted_data
SELECT
    id,
    sort_order,
    text,
    oid,
    soft_deleted_at,
    question_id
FROM answer
WHERE question_id IN :question_ids;