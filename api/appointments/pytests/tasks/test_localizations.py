import json
from unittest import mock

from flask_babel import get_locale

from appointments.tasks.localization import (
    SUPPORTED_LOCALES,
    update_appointment_search_localized_strings,
)

TRANSLATIONS = {
    "es": {
        "need_nutrition_name": "need_es",
        "need_nutrition_description": "needdesc_es",
        "need_category_lifestyle_nutrition_name": "needcat_es",
        "vertical_nutrition_coach_name": "vert1_es",
        "specialty_pediatric_nutrition_name": "spec1_es",
    },
    "fr": {
        "need_nutrition_name": "need_fr",
        "need_nutrition_description": "needdesc_fr",
        "need_category_lifestyle_nutrition_name": "needcat_fr",
        "vertical_nutrition_coach_name": "vert1_fr",
        "specialty_pediatric_nutrition_name": "spec1_fr",
    },
    "fr_CA": {
        "need_nutrition_name": "need_frca",
        "need_nutrition_description": "needdesc_frca",
        "need_category_lifestyle_nutrition_name": "needcat_frca",
        "vertical_nutrition_coach_name": "vert1_frca",
        "specialty_pediatric_nutrition_name": "spec1_frca",
    },
}


def mock_gettext(input_string):
    # Check the current locale
    current_locale = str(get_locale())
    # Return different translations based on the locale and input string
    return TRANSLATIONS.get(current_locale, {}).get(input_string, input_string)


@mock.patch("l10n.db_strings.translate.gettext", side_effect=mock_gettext)
def test_update_appointment_search_localized_strings(mock_gettext, factories):
    need = factories.NeedFactory.create(name="nutrition")
    need_category = factories.NeedCategoryFactory.create(name="lifestyle_nutrition")
    vertical = factories.VerticalFactory.create(name="nutrition_coach")
    specialty = factories.SpecialtyFactory.create(name="pediatric_nutrition")

    update_appointment_search_localized_strings()

    # After first update the translated string should be stored on the models

    expected_localized_need_data = {
        "name": {
            "es": TRANSLATIONS["es"]["need_nutrition_name"],
            "fr": TRANSLATIONS["fr"]["need_nutrition_name"],
            "fr_CA": TRANSLATIONS["fr_CA"]["need_nutrition_name"],
        },
        "description": {
            "es": TRANSLATIONS["es"]["need_nutrition_description"],
            "fr": TRANSLATIONS["fr"]["need_nutrition_description"],
            "fr_CA": TRANSLATIONS["fr_CA"]["need_nutrition_description"],
        },
    }
    expected_localized_need_categories = {
        "name": {
            "es": TRANSLATIONS["es"]["need_category_lifestyle_nutrition_name"],
            "fr": TRANSLATIONS["fr"]["need_category_lifestyle_nutrition_name"],
            "fr_CA": TRANSLATIONS["fr_CA"]["need_category_lifestyle_nutrition_name"],
        }
    }
    expected_localized_verticals = {
        "name": {
            "es": TRANSLATIONS["es"]["vertical_nutrition_coach_name"],
            "fr": TRANSLATIONS["fr"]["vertical_nutrition_coach_name"],
            "fr_CA": TRANSLATIONS["fr_CA"]["vertical_nutrition_coach_name"],
        }
    }
    expected_localized_specialty = {
        "name": {
            "es": TRANSLATIONS["es"]["specialty_pediatric_nutrition_name"],
            "fr": TRANSLATIONS["fr"]["specialty_pediatric_nutrition_name"],
            "fr_CA": TRANSLATIONS["fr_CA"]["specialty_pediatric_nutrition_name"],
        }
    }

    localized_need_data = json.loads(need.searchable_localized_data)
    localized_need_categories = json.loads(need_category.searchable_localized_data)
    localized_verticals = json.loads(vertical.searchable_localized_data)
    localized_specialty = json.loads(specialty.searchable_localized_data)

    for locale in SUPPORTED_LOCALES:
        assert (
            localized_need_data["name"][locale]
            == expected_localized_need_data["name"][locale]
        )
        assert (
            localized_need_data["description"][locale]
            == expected_localized_need_data["description"][locale]
        )
        assert (
            localized_need_categories["name"][locale]
            == expected_localized_need_categories["name"][locale]
        )
        assert (
            localized_specialty["name"][locale]
            == expected_localized_specialty["name"][locale]
        )
        assert (
            localized_verticals["name"][locale]
            == expected_localized_verticals["name"][locale]
        )

    # Second time there should be no updates
    with mock.patch(
        "appointments.tasks.localization.db.session.add"
    ) as mock_session_add:
        update_appointment_search_localized_strings()
        mock_session_add.assert_not_called()

    #     Create some data without translations, the translation should fallback to English
    need_no_translation = factories.NeedFactory.create(
        name="Need without translation", description="Description without translation"
    )
    need_category_no_translation = factories.NeedCategoryFactory.create(
        name="Need category without translation"
    )
    vertical_no_translation = factories.VerticalFactory.create(
        name="Vertical without translation"
    )
    specialty_no_translation = factories.SpecialtyFactory.create(
        name="specialty without translation"
    )

    update_appointment_search_localized_strings()
    localized_need_data = json.loads(need_no_translation.searchable_localized_data)
    localized_need_categories = json.loads(
        need_category_no_translation.searchable_localized_data
    )
    localized_verticals = json.loads(vertical_no_translation.searchable_localized_data)
    localized_specialty = json.loads(specialty_no_translation.searchable_localized_data)

    for locale in SUPPORTED_LOCALES:
        assert localized_need_data["name"][locale] == need_no_translation.name
        assert (
            localized_need_data["description"][locale]
            == need_no_translation.description
        )
        assert (
            localized_need_categories["name"][locale]
            == need_category_no_translation.name
        )
        assert localized_specialty["name"][locale] == specialty_no_translation.name
        assert localized_verticals["name"][locale] == vertical_no_translation.name
