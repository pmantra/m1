from flask_babel import gettext

from l10n.db_strings.store import DBStringStore
from storage.connection import db

"""
This is an ad-hoc script that we used to add missing strings to the translation files and 
DBStringStore. 

These strings were missing for two reasons: 
- The files were initialized first, before we actually backfilled the slugs in the prod db
and realized that these slugs differed in some cases from what we expected. This was because
the slugs in the prod db don't all follow the same schema, and some of them have suffixes due to
clashes.
- Rows in the prod db were inserted or mutated without changing these fields. We need to lock
these rows down so they can't be changed through admin, but that hasn't been done yet.

Usage:
Connect to a prod pod dev shell and paste this script in. You can change the "mode" just by
modifying the `mode = <...>` line. DIAGNOSIS is useful for giving an overview of the amount
of drift that needs to be fixed. The other modes print output to the shell which can be
directly pasted / appended into the relevant files to fix them. 
"""


DIAGNOSIS = "diagnosis"
PRINT_MISSING_EN_PO_KEYS = "print_missing_en_po_keys"
PRINT_MISSING_POT_KEYS = "print_missing_pot_keys"
PRINT_MISSING_DB_STORE_SLUGS = "print_missing_db_store_slugs"
MODES = [
    DIAGNOSIS,
    PRINT_MISSING_EN_PO_KEYS,
    PRINT_MISSING_POT_KEYS,
    PRINT_MISSING_DB_STORE_SLUGS,
]

# simplified from TranslateDBFields._get_translated_string_from_slug
def get_translation_key(model_name: str, slug: str, field: str) -> str:
    return f"{model_name}_{slug}_{field}"


models = [
    (
        "vertical",
        DBStringStore.VERTICAL_FIELDS,
        DBStringStore.VERTICAL_SLUGS,
        f"SELECT slug, {', '.join(DBStringStore.VERTICAL_FIELDS)} FROM vertical WHERE deleted_at is NULL",
    ),
    (
        "need",
        DBStringStore.NEED_FIELDS,
        DBStringStore.NEED_SLUGS,
        f"SELECT slug, {', '.join(DBStringStore.NEED_FIELDS)} FROM need",
    ),
    (
        "language",
        DBStringStore.LANGUAGE_FIELDS,
        DBStringStore.LANGUAGE_SLUGS,
        f"SELECT slug, {', '.join(DBStringStore.LANGUAGE_FIELDS)} FROM language",
    ),
    (
        "need_category",
        DBStringStore.NEED_CATEGORY_FIELDS,
        DBStringStore.NEED_CATEGORY_SLUGS,
        f"SELECT slug, {', '.join(DBStringStore.NEED_CATEGORY_FIELDS)} FROM need_category",
    ),
    (
        "specialty",
        DBStringStore.SPECIALTY_FIELDS,
        DBStringStore.SPECIALTY_SLUGS,
        f"SELECT slug, {', '.join(DBStringStore.SPECIALTY_FIELDS)} FROM specialty",
    ),
]

mode = DIAGNOSIS

for model_name, fields, expected_slugs, query in models:
    rows = list(db.session.execute(query))
    missing_codes = []
    if mode == PRINT_MISSING_POT_KEYS:
        print(f"\n\nMISSING POT KEYS FOR {model_name}")  # noqa
    elif mode == PRINT_MISSING_EN_PO_KEYS:
        print(f"\n\nMISSING en PO KEYS FOR {model_name}")  # noqa

    for row in rows:
        slug = row.slug
        for field in fields:
            translation_key = f"{model_name}_{slug}_{field}"
            is_missing_str = gettext(translation_key) == translation_key
            if is_missing_str:
                if mode == DIAGNOSIS:
                    print(f"Missing key: {translation_key}")  # noqa
                elif mode == PRINT_MISSING_POT_KEYS:
                    print(f'msgid "{translation_key}"')  # noqa
                    print('msgstr ""')  # noqa
                    print("")  # noqa
                elif mode == PRINT_MISSING_EN_PO_KEYS:
                    print(f'msgid "{translation_key}"')  # noqa
                    print(f'msgstr "{getattr(row, field)}"')  # noqa
                    print("")  # noqa

        is_missing_code = slug not in expected_slugs
        if is_missing_code:
            if mode == PRINT_MISSING_DB_STORE_SLUGS or mode == DIAGNOSIS:
                missing_codes.append(slug)
    if mode == PRINT_MISSING_DB_STORE_SLUGS or mode == DIAGNOSIS:
        print(f"Missing {model_name} codes: {missing_codes}")  # noqa
