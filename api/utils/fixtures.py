def create_user_factory():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    from pytests.factories import DefaultUserFactory

    return DefaultUserFactory


def restore_fixtures() -> None:
    from data_admin.data_factory import DataFactory
    from schemas.io import Fixture, restore
    from storage.connection import db

    restore(
        (
            Fixture.US_STATES,
            Fixture.LANGUAGES,
            Fixture.CANCELLATION_POLICIES,
            Fixture.AGREEMENTS,
            Fixture.FORUM_CATEGORIES,
            Fixture.REFERRAL_CODE_CATEGORIES,
            Fixture.ROLES,
            Fixture.SPECIALTIES,
            Fixture.SPECIALTY_KEYWORDS,
            Fixture.TAGS,
            Fixture.TEXT_COPIES,
            Fixture.USER_FLAGS,
            Fixture.VERTICALS,
            Fixture.ASSESSMENTS,
            Fixture.MODULES,
            Fixture.CONNECTED_CONTENT_FIELDS,
            Fixture.RESOURCES,
            Fixture.BMS_PRODUCTS,
            Fixture.MESSAGE_PRODUCTS,
            Fixture.QUESTIONNAIRES,
        )
    )
    DataFactory(None, "no_client").add_default_care_coordinator()
    db.session.commit()
