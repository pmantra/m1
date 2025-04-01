-- get_questionnaires
SELECT
    q.id as questionnaire_id,
    q.sort_order as questionnaire_sort_order,
    q.oid as questionnaire_oid,
    q.title_text as questionnaire_title_text,
    q.description_text as questionnaire_description_text,
    q.intro_appointment_only as questionnaire_intro_appointment_only,
    q.track_name as questionnaire_track_name,
    qset.id as question_set_id,
    qset.sort_order as question_set_sort_order,
    qset.oid as question_set_oid,
    qn.id as question_id,
    qn.oid as question_oid,
    qn.sort_order as question_sort_order,
    qn.label as question_label,
    qn.type as question_type,
    qn.required as question_required,
    a.id as answer_id,
    a.oid as answer_oid,
    a.sort_order as answer_sort_order,
    a.text as answer_text
FROM questionnaire q
JOIN question_set qset on q.id = qset.questionnaire_id
JOIN question qn on qn.question_set_id = qset.id
LEFT JOIN answer a on a.question_id = qn.id
WHERE q.oid in ('member_ca_rating', 'member_rating_v2', 'member_rating_followup_v2', 'cancellation_survey')
AND q.soft_deleted_at is NULL
AND qset.soft_deleted_at is NULL
AND qn.soft_deleted_at is NULL
AND a.soft_deleted_at is NULL;

-- get_questionnaire_oids_by_product_id
SELECT
    p.id as product_id,
    q.oid as questionnaire_oid
FROM questionnaire q
JOIN questionnaire_vertical qv on q.id = qv.questionnaire_id
JOIN questionnaire_role qr on q.id = qr.questionnaire_id
JOIN `role` r on qr.role_id = r.id
JOIN product p on p.vertical_id = qv.vertical_id
WHERE p.id in :product_ids
AND r.name = 'member';

-- get_questionnaire_trigger_answers
SELECT
    answer_id as trigger_answer_id,
    questionnaire_id as questionnaire_id
FROM questionnaire_trigger_answer;
