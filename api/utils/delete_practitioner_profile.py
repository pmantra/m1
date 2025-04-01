from appointments.models.availability_notification_request import (
    AvailabilityNotificationRequest,
)
from appointments.models.payments import (
    AppointmentFeeCreator,
    FeeAccountingEntry,
    practitioner_credits,
)
from authn.models.sso import ExternalIdentity
from care_advocates.models.assignable_advocates import AssignableAdvocate
from care_advocates.models.member_match_logs import MemberMatchLog
from models.products import Product
from models.profiles import (
    MemberPractitionerAssociation,
    PractitionerProfile,
    PractitionerSubdivision,
    RoleProfile,
    practitioner_categories,
    practitioner_certifications,
    practitioner_characteristics,
    practitioner_languages,
    practitioner_specialties,
    practitioner_states,
    practitioner_verticals,
)
from provider_matching.models.practitioner_track_vgc import PractitionerTrackVGC
from storage.connection import db
from utils.log import logger

log = logger(__name__)

related_tables_through_foreign_key = {
    "practitioner_id": [
        practitioner_characteristics,
    ],
    "user_id": [
        practitioner_certifications,
        practitioner_categories,
        practitioner_states,
        practitioner_verticals,
        practitioner_specialties,
        practitioner_languages,
        practitioner_credits,
    ],
}

related_models_through_foreign_key = {
    "practitioner_id": [
        PractitionerTrackVGC,
        AssignableAdvocate,
        MemberPractitionerAssociation,
        PractitionerSubdivision,
        AvailabilityNotificationRequest,
        FeeAccountingEntry,
    ],
    "user_id": [
        Product,
        AppointmentFeeCreator,
        ExternalIdentity,
        RoleProfile,
    ],
    "care_advocate_id": [MemberMatchLog],
}


def get_tables_where_practitioner_is_present(practitioner_id, foreign_key):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    related_tables = related_tables_through_foreign_key[foreign_key]
    related_tables_with_prac_present = []
    for table in related_tables:
        if foreign_key == "practitioner_id":
            related_rows = db.session.query(table).filter(
                table.c.practitioner_id == practitioner_id
            )
        elif foreign_key == "user_id":
            related_rows = db.session.query(table).filter(
                table.c.user_id == practitioner_id
            )
        if related_rows.count() > 0:
            related_tables_with_prac_present.append(str(table))
    return related_tables_with_prac_present


def get_models_where_practitioner_is_present(practitioner_id, foreign_key):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    related_models = related_models_through_foreign_key[foreign_key]
    related_models_with_prac_present = []
    for model in related_models:  # type: ignore[attr-defined] # "object" has no attribute "__iter__"; maybe "__dir__" or "__str__"? (not iterable)
        if foreign_key == "practitioner_id":
            related_rows = db.session.query(model).filter_by(
                practitioner_id=practitioner_id
            )
        elif foreign_key == "user_id":
            related_rows = db.session.query(model).filter_by(user_id=practitioner_id)
        elif foreign_key == "care_advocate_id":
            related_rows = db.session.query(model).filter_by(
                care_advocate_id=practitioner_id
            )

        if related_rows.count() > 0:
            related_models_with_prac_present.append(str(model))
    return related_models_with_prac_present


def delete_practitioner_profile(practitioner_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation

    if db.session.query(PractitionerProfile).get(practitioner_id) is None:
        log.warn(f"No PractitionerProfile found for id {practitioner_id}")
        return

    models_with_practitioner = []
    for fk in ["practitioner_id", "user_id", "care_advocate_id"]:
        models_with_practitioner_for_fk = get_models_where_practitioner_is_present(
            practitioner_id=practitioner_id, foreign_key=fk
        )
        if len(models_with_practitioner_for_fk) > 0:
            models_with_practitioner.extend(models_with_practitioner_for_fk)
    if len(models_with_practitioner) > 0:
        log.warn(
            f"PractitionerProfile {practitioner_id} cannot be deleted because it has rows in the {str(models_with_practitioner)} model(s) associated with it. Please delete these associations first."
        )

    tables_with_practitioner = []
    for fk in ["practitioner_id", "user_id"]:
        tables_with_practitioner_for_fk = get_tables_where_practitioner_is_present(
            practitioner_id=practitioner_id, foreign_key=fk
        )
        if len(tables_with_practitioner_for_fk) > 0:
            tables_with_practitioner.extend(tables_with_practitioner_for_fk)

    if len(tables_with_practitioner) > 0:
        log.warn(
            f"PractitionerProfile {practitioner_id} cannot be deleted because it has rows in the {str(tables_with_practitioner)} table(s) associated with it. Please delete these associations first."
        )

    if len(models_with_practitioner) > 0 or len(tables_with_practitioner) > 0:
        return

    try:
        db.session.query(PractitionerProfile).filter_by(
            user_id=practitioner_id
        ).delete()
        db.session.commit()
        log.info(
            "Successfully deleted practitioner profile", practitioner_id=practitioner_id
        )
    except Exception as e:
        log.exception(
            "Failed to delete PractitionerProfile",
            exception=e,
            practitioner_id=practitioner_id,
        )

        db.session.rollback()


def migrate_practitioner_related_entities(source_prac_id, new_prac_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation

    if db.session.query(PractitionerProfile).get(source_prac_id) is None:
        log.warn(f"No PractitionerProfile found for id {source_prac_id}")
        return

    if db.session.query(PractitionerProfile).get(new_prac_id) is None:
        log.warn(f"No PractitionerProfile found for id {new_prac_id}")
        return

    related_models = related_models_through_foreign_key["practitioner_id"]

    for model in related_models:  # type: ignore[attr-defined] # "object" has no attribute "__iter__"; maybe "__dir__" or "__str__"? (not iterable)
        print(f"Working on {str(model)}")
        rows = db.session.query(model).filter_by(practitioner_id=source_prac_id).all()
        if len(rows) == 0:
            print(f"Found no rows for {str(model)}")
        for row in rows:
            print(f"Migrating {row}")
            row.practitioner_id = new_prac_id
            db.session.add(row)
            db.session.commit()

        # Validate that rows dont exist anymore
        rows = db.session.query(model).filter_by(practitioner_id=source_prac_id).all()
        if len(rows) > 0:
            raise Exception

    related_models = related_models_through_foreign_key["user_id"]
    for model in related_models:  # type: ignore[attr-defined] # "object" has no attribute "__iter__"; maybe "__dir__" or "__str__"? (not iterable)
        print(f"Working on {str(model)}")
        rows = db.session.query(model).filter_by(user_id=source_prac_id).all()
        if len(rows) == 0:
            print(f"Found no rows for {str(model)}")
        for row in rows:
            print(f"Migrating {row}")
            row.user_id = new_prac_id
            db.session.add(row)
            db.session.commit()

        # Validate that rows dont exist anymore
        rows = db.session.query(model).filter_by(user_id=source_prac_id).all()
        if len(rows) > 0:
            raise Exception

    related_tables = related_tables_through_foreign_key["practitioner_id"]
    for table in related_tables:
        print(f"Working on {str(table)}")

        rows = (
            db.session.query(table)
            .filter(table.c.practitioner_id == source_prac_id)
            .all()
        )

        if len(rows) == 0:
            print(f"Found no rows for {str(table)}")
        else:
            print(f"Migrating {str(table)}")
            update_statement = (
                table.update()
                .where(table.c.practitioner_id == source_prac_id)
                .values(practitioner_id=new_prac_id)
            )

            db.session.execute(update_statement)
            db.session.commit()

        # Validate that rows dont exist anymore
        rows = (
            db.session.query(table)
            .filter(table.c.practitioner_id == source_prac_id)
            .all()
        )
        if len(rows) > 0:
            raise Exception

    related_tables = related_tables_through_foreign_key["user_id"]
    for table in related_tables:
        print(f"Working on {str(table)}")

        rows = db.session.query(table).filter(table.c.user_id == source_prac_id).all()

        if len(rows) == 0:
            print(f"Found no rows for {str(table)}")
        else:
            print(f"Migrating {str(table)}")
            update_statement = (
                table.update()
                .where(table.c.user_id == source_prac_id)
                .values(user_id=new_prac_id)
            )

            db.session.execute(update_statement)
            db.session.commit()

        # Validate that rows dont exist anymore
        rows = db.session.query(table).filter(table.c.user_id == source_prac_id).all()
        if len(rows) > 0:
            raise Exception
