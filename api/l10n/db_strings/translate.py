from flask_babel import gettext, lazy_gettext

from l10n.db_strings.store import DBStringStore
from utils.log import logger

log = logger(__name__)

VERTICAL_MODEL = "vertical"
SPECIALTY_MODEL = "specialty"
CANCELLATION_POLICY_MODEL = "cancellation_policy"
CA_MEMBER_TRANSITION_MODEL = "ca_member_transition_template"
NEED_MODEL = "need"
NEED_CATEGORY_MODEL = "need_category"
LANGUAGE_MODEL = "language"
QUESTIONNAIRE_MODEL = "questionnaire"
QUESTION_MODEL = "question"
ANSWER_MODEL = "answer"


class TranslateDBFields:
    """
    Get the translated text from the appropriate language files.
    The translated text for DB fields is identified by a "msgid" of the form:
    "<db_table_name>_<slug>_<field>"
    """

    def get_translated_vertical(
        self, slug: str, field: str, default: str, lazy: bool = False
    ) -> str:
        return self._get_translated_string_from_slug(
            slug=slug,
            field=field,
            slug_list=DBStringStore.VERTICAL_SLUGS,
            field_list=DBStringStore.VERTICAL_FIELDS,
            model_name=VERTICAL_MODEL,
            lazy=lazy,
            default=default,
        )

    def get_translated_specialty(
        self, slug: str, field: str, default: str, lazy: bool = False
    ) -> str:
        return self._get_translated_string_from_slug(
            slug=slug,
            field=field,
            slug_list=DBStringStore.SPECIALTY_SLUGS,
            field_list=DBStringStore.SPECIALTY_FIELDS,
            model_name=SPECIALTY_MODEL,
            lazy=lazy,
            default=default,
        )

    def get_translated_cancellation_policy(
        self, slug: str, field: str, default: str, lazy: bool = False
    ) -> str:
        return self._get_translated_string_from_slug(
            slug=slug,
            field=field,
            slug_list=DBStringStore.CANCELLATION_POLICY_SLUGS,
            field_list=DBStringStore.CANCELLATION_POLICY_FIELDS,
            model_name=CANCELLATION_POLICY_MODEL,
            lazy=lazy,
            default=default,
        )

    def get_translated_ca_member_transition(
        self, slug: str, field: str, default: str, lazy: bool = False
    ) -> str:
        return self._get_translated_string_from_slug(
            slug=slug,
            field=field,
            slug_list=DBStringStore.CA_MEMBER_TRANSITION_SLUGS,
            field_list=DBStringStore.CA_MEMBER_TRANSITION_FIELDS,
            model_name=CA_MEMBER_TRANSITION_MODEL,
            lazy=lazy,
            default=default,
        )

    def get_translated_need_category(
        self, slug: str, field: str, default: str, lazy: bool = False
    ) -> str:
        return self._get_translated_string_from_slug(
            slug=slug,
            field=field,
            slug_list=DBStringStore.NEED_CATEGORY_SLUGS,
            field_list=DBStringStore.NEED_CATEGORY_FIELDS,
            model_name=NEED_CATEGORY_MODEL,
            lazy=lazy,
            default=default,
        )

    def get_translated_need(
        self, slug: str, field: str, default: str, lazy: bool = False
    ) -> str:
        return self._get_translated_string_from_slug(
            slug=slug,
            field=field,
            slug_list=DBStringStore.NEED_SLUGS,
            field_list=DBStringStore.NEED_FIELDS,
            model_name=NEED_MODEL,
            lazy=lazy,
            default=default,
        )

    def get_translated_language(
        self, slug: str, field: str, default: str, lazy: bool = False
    ) -> str:
        return self._get_translated_string_from_slug(
            slug=slug,
            field=field,
            slug_list=DBStringStore.LANGUAGE_SLUGS,
            field_list=DBStringStore.LANGUAGE_FIELDS,
            model_name=LANGUAGE_MODEL,
            lazy=lazy,
            default=default,
        )

    def get_translated_questionnaire(
        self, slug: str, field: str, default: str, lazy: bool = False
    ) -> str:
        return self._get_translated_string_from_slug(
            slug=slug,
            field=field,
            slug_list=DBStringStore.QUESTIONNAIRE_SLUGS,
            field_list=DBStringStore.QUESTIONNAIRE_FIELDS,
            model_name=QUESTIONNAIRE_MODEL,
            lazy=lazy,
            default=default,
        )

    def get_translated_question(
        self, slug: str, field: str, default: str, lazy: bool = False
    ) -> str:
        return self._get_translated_string_from_slug(
            slug=slug,
            field=field,
            slug_list=DBStringStore.QUESTION_SLUGS,
            field_list=DBStringStore.QUESTION_FIELDS,
            model_name=QUESTION_MODEL,
            lazy=lazy,
            default=default,
        )

    def get_translated_answer(
        self, slug: str, field: str, default: str, lazy: bool = False
    ) -> str:
        return self._get_translated_string_from_slug(
            slug=slug,
            field=field,
            slug_list=DBStringStore.ANSWER_SLUGS,
            field_list=DBStringStore.ANSWER_FIELDS,
            model_name=ANSWER_MODEL,
            lazy=lazy,
            default=default,
        )

    def _get_translated_string_from_slug(
        self,
        slug: str,
        slug_list: list[str],
        field: str,
        field_list: list[str],
        model_name: str,
        default: str,
        lazy: bool = False,
    ) -> str:
        translation_string = f"{model_name}_{slug}_{field}"
        if slug in slug_list and field in field_list:
            if lazy:
                return lazy_gettext(translation_string)
            return gettext(translation_string)
        log.error(
            "Translated text not found for msgid",
            slug=slug,
            field=field,
            model_name=model_name,
            msgid=translation_string,
        )
        return default
