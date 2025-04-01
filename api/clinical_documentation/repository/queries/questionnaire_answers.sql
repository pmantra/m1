-- get_questionnaire_ids_from_question_ids
SELECT DISTINCT(qr.id)
FROM question q
JOIN question_set qs on q.question_set_id = qs.id
JOIN questionnaire qr on qs.questionnaire_id = qr.id
WHERE q.id in :question_ids;

-- delete_existing_recorded_answers
DELETE r FROM recorded_answer r
JOIN question q ON r.question_id = q.id
JOIN question_set qs on q.question_set_id = qs.id
JOIN questionnaire qr on qs.questionnaire_id = qr.id
WHERE r.appointment_id = :appointment_id and qr.id = :questionnaire_id;

-- insert_recorded_answers_template
-- Note that this is not yet a valid SQL statement. We must replace the
-- {rows_placeholder} variable with a variable number of
-- placeholders that are formatted like this:
-- (:text, :appointment_id, :question_id, :answer_id, :user_id),
-- This will allow us to insert a variable number of rows.
INSERT INTO recorded_answer(
    text, appointment_id, question_id, answer_id, user_id
) VALUES {rows_placeholder};
