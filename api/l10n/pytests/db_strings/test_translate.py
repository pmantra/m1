import pytest

from l10n.db_strings.store import DBStringStore
from l10n.db_strings.translate import TranslateDBFields


class TestTranslateDBFields:
    @pytest.mark.parametrize(
        "slug, slug_list, field, field_list, model_name, expected_english_string",
        [
            (
                "nutrition_coach",
                DBStringStore.VERTICAL_SLUGS,
                "name",
                DBStringStore.VERTICAL_FIELDS,
                "vertical",
                "Nutrition Coach",
            ),
            (
                "nutrition_coach",
                DBStringStore.VERTICAL_SLUGS,
                "description",
                DBStringStore.VERTICAL_FIELDS,
                "vertical",
                "Healthy eating, weight management",
            ),
        ],
    )
    def test_get_translated_string_from_slug__slug_found(
        self, slug, slug_list, field, field_list, model_name, expected_english_string
    ):
        assert (
            TranslateDBFields()._get_translated_string_from_slug(
                slug, slug_list, field, field_list, model_name, default=""
            )
            == expected_english_string
        )

    @pytest.mark.parametrize(
        "slug, slug_list, field, field_list, model_name",
        [
            (
                "nutrition_coach_123",
                DBStringStore.VERTICAL_SLUGS,
                "name",
                DBStringStore.VERTICAL_FIELDS,
                "vertical",
            ),
            (
                "nutrition_coach",
                DBStringStore.VERTICAL_SLUGS,
                "description_wrong",
                DBStringStore.VERTICAL_FIELDS,
                "vertical",
            ),
        ],
    )
    def test_get_translated_string_from_slug__slug_not_found(
        self, slug, slug_list, field, field_list, model_name
    ):
        default = "Default String"
        assert (
            TranslateDBFields()._get_translated_string_from_slug(
                slug, slug_list, field, field_list, model_name, default=default
            )
            == default
        )

    @pytest.mark.parametrize(
        "slug, field, expected_english_string",
        [
            ("nutrition_coach", "name", "Nutrition Coach"),
            ("nutrition_coach", "description", "Healthy eating, weight management"),
        ],
    )
    def test_get_translated_vertical(self, slug, field, expected_english_string):
        assert (
            TranslateDBFields().get_translated_vertical(slug, field, default="")
            == expected_english_string
        )

    @pytest.mark.parametrize(
        "slug, field, expected_english_string",
        [
            ("allergies", "name", "Allergies"),
            (
                "stress_reduction_and_mindfulness",
                "name",
                "Stress reduction and mindfulness",
            ),
        ],
    )
    def test_get_translated_specialty(self, slug, field, expected_english_string):
        assert (
            TranslateDBFields().get_translated_specialty(slug, field, default="")
            == expected_english_string
        )

    @pytest.mark.parametrize(
        "slug, field, expected_english_string",
        [
            ("nutrition", "name", "Nutrition"),
            (
                "medication_education",
                "description",
                "How to administer injections, manage a schedule, side effects",
            ),
        ],
    )
    def test_get_translated_need(self, slug, field, expected_english_string):
        assert (
            TranslateDBFields().get_translated_need(slug, field, default="")
            == expected_english_string
        )

    @pytest.mark.parametrize(
        "slug, field, expected_english_string",
        [
            ("emotional_health", "name", "Emotional Health"),
            ("pregnancy", "name", "Pregnancy"),
        ],
    )
    def test_get_translated_need_category(self, slug, field, expected_english_string):
        assert (
            TranslateDBFields().get_translated_need_category(slug, field, default="")
            == expected_english_string
        )

    @pytest.mark.parametrize(
        "slug, field, expected_english_string",
        [
            ("english", "name", "English"),
            ("iranian_persian", "name", "Iranian Persian"),
        ],
    )
    def test_get_translated_language(self, slug, field, expected_english_string):
        assert (
            TranslateDBFields().get_translated_language(slug, field, default="")
            == expected_english_string
        )
