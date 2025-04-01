import os

import contentful_management

from utils import log

CONTENTFUL_SPACE_ID = os.getenv("CONTENTFUL_LEARN_SPACE_ID")
CONTENTFUL_MANAGEMENT_KEY = os.getenv("CONTENTFUL_LEARN_MANAGEMENT_KEY")
log = log.logger(__name__)


def do_migration(environment: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    client = contentful_management.Client(CONTENTFUL_MANAGEMENT_KEY)
    space = client.spaces().find(CONTENTFUL_SPACE_ID)
    current_environment = space.environments().find(environment)

    locales = current_environment.locales().all()

    for locale in locales:
        if locale.code == "en-US":
            default_locale = locale
        log.info("🗑️ Clearing fallback for locale", locale=locale.code)  # type: ignore[attr-defined] # Module has no attribute "info"
        locale.fallback_code = None
        locale.save()

    log.info("⚙️ Updating default locale (en-US) to be 'en'")  # type: ignore[attr-defined] # Module has no attribute "info"
    default_locale.update({"name": "English", "code": "en"})
    default_locale.save()

    create_new_locale(current_environment, "Spanish", "es")
    create_new_locale(current_environment, "French", "fr")
    create_new_locale(current_environment, "English (United States)", "en-US")

    # fix the defaults
    locales = current_environment.locales().all()
    for locale in locales:
        if locale.code == "fr-FR":
            locale.fallback_code = "fr"
        elif locale.code == "es-419":
            locale.fallback_code = "es"
        elif locale.code == "en":
            locale.fallback_code = None
        else:
            locale.fallback_code = "en"
        log.info(  # type: ignore[attr-defined] # Module has no attribute "info"
            "🔧 Setting default for locale",
            locale=locale.code,
            default=locale.fallback_code,
        )
        locale.save()

    log.info("👷 Done fixing locales!")  # type: ignore[attr-defined] # Module has no attribute "info"


def create_new_locale(current_environment, locale_name, locale_code):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.info("✨ Creating new locale", name=locale_name, code=locale_code)  # type: ignore[attr-defined] # Module has no attribute "info"
    current_environment.locales().create(
        {
            "name": locale_name,
            "code": locale_code,
            "optional": True,
        }
    )
