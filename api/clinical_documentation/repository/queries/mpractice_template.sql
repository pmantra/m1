-- get_mpractice_template_by_id
SELECT
    id,
    owner_id,
    sort_order,
    is_global,
    title,
    text,
    modified_at,
    created_at
FROM mpractice_template
WHERE id = :id;


-- get_mpractice_templates_by_owner
SELECT
    id,
    owner_id,
    sort_order,
    is_global,
    title,
    text,
    modified_at,
    created_at
FROM mpractice_template
WHERE owner_id = :owner_id
OR is_global is TRUE
ORDER BY sort_order, created_at;


-- get_mpractice_templates_by_title
SELECT
    id,
    owner_id,
    sort_order,
    is_global,
    title,
    text,
    modified_at,
    created_at
FROM mpractice_template
WHERE (owner_id = :owner_id
OR is_global is TRUE)
AND title = :title;


-- create_mpractice_template
INSERT INTO mpractice_template (owner_id, sort_order, is_global, title, text)
VALUES (:owner_id, :sort_order, :is_global, :title, :text);


-- delete_mpractice_template_by_id
DELETE FROM mpractice_template
WHERE id = :template_id AND owner_id = :owner_id;


-- edit_mpractice_template_title_and_text
UPDATE mpractice_template
SET title = :title,
    text = :text
WHERE id = :template_id AND owner_id = :owner_id;


-- edit_mpractice_template_title
UPDATE mpractice_template
SET title = :title
WHERE id = :template_id AND owner_id = :owner_id;


-- edit_mpractice_template_text
UPDATE mpractice_template
SET text = :text
WHERE id = :template_id AND owner_id = :owner_id;


-- edit_mpractice_template_by_id
UPDATE mpractice_template
SET sort_order = COALESCE(:sort_order, sort_order),
    is_global = COALESCE(:is_global, is_global),
    title = COALESCE(:title, title),
    text = COALESCE(:text, text),
WHERE id = :template_id AND owner_id = :owner_id;

