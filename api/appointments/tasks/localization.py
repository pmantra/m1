import json
from collections import defaultdict
from typing import Callable, List, Type

from flask_babel import force_locale

from appointments.models.needs_and_categories import Need, NeedCategory
from l10n.db_strings.translate import TranslateDBFields
from models.base import ModelBase
from models.verticals_and_specialties import Specialty, Vertical
from storage.connection import db
from tasks.queues import job
from utils.log import logger

log = logger(__name__)

SUPPORTED_LOCALES = ["es", "fr", "fr_CA"]


@job
def update_appointment_search_localized_strings() -> None:
    translate_db_fields = TranslateDBFields()
    # Model, translation func, fields
    models_and_translation_func = [
        (Need, translate_db_fields.get_translated_need, ["name", "description"]),
        (NeedCategory, translate_db_fields.get_translated_need_category, ["name"]),
        (Vertical, translate_db_fields.get_translated_vertical, ["name"]),
        (Specialty, translate_db_fields.get_translated_specialty, ["name"]),
    ]

    for model, translation_func, fields in models_and_translation_func:
        update_search_localized_strings_for_model(model, translation_func, fields)


def update_search_localized_strings_for_model(
    model: Type[ModelBase],
    translation_func: Callable[[str, str, str, bool], str],
    fields: List[str],
) -> None:
    # Fetch all rows from the table
    log.info(f"Scanning table {model.__tablename__} for changes in localized strings")
    rows = db.session.query(model).yield_per(100)
    for row in rows:
        new_translated_strings = defaultdict(dict)
        slug = row.slug
        for field in fields:
            for locale in SUPPORTED_LOCALES:
                with force_locale(locale):
                    translated_field = translation_func(
                        slug, field, getattr(row, field), False
                    )
                    new_translated_strings[field][locale] = translated_field

        new_translated_strings_json = json.dumps(
            new_translated_strings, ensure_ascii=False
        )

        if new_translated_strings_json != row.searchable_localized_data:
            log.info(
                f"Found changes in localized strings for {model.__tablename__} and id {row.id}",
                extra={
                    "old_json": row.searchable_localized_data,
                    "new_json": new_translated_strings_json,
                },
            )
            row.searchable_localized_data = new_translated_strings_json
            db.session.add(row)

    db.session.commit()
