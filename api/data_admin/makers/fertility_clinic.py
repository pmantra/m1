from flask import flash

from data_admin.data_factory import DataFactory
from data_admin.maker_base import _MakerBase
from direct_payment.clinic.models.clinic import (
    FertilityClinic,
    FertilityClinicAllowedDomain,
    FertilityClinicLocation,
)
from storage.connection import db


class FertilityClinicMaker(_MakerBase):
    def add_fertility_clinic(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        name,
        fee_schedule_id,
        affiliated_network="",
        notes="",
        id=None,
        uuid=None,
        created_at=None,
        modified_at=None,
    ):
        fc = FertilityClinic(
            name=name,
            affiliated_network=affiliated_network,
            notes=notes,
            fee_schedule_id=fee_schedule_id,
        )
        _add_time_logged_external_uuid_model_base_attr(
            fc, id, uuid, created_at, modified_at
        )

        db.session.add(fc)
        db.session.flush()
        return fc

    def create_object(self, spec, parent=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        fee_schedule_id = spec.get("fee_schedule_id")
        if not fee_schedule_id:
            # avoid circular import
            from data_admin.makers.mmb import FeeScheduleMaker
            from direct_payment.clinic.models.fee_schedule import FeeSchedule

            fee_schedule = FeeSchedule.query.filter_by(
                name=spec["fee_schedule"]["name"]
            ).first()
            if not fee_schedule:
                fee_schedule = FeeScheduleMaker().create_object_and_flush(
                    spec["fee_schedule"]
                )
            fee_schedule_id = fee_schedule.id

        name = spec.get("name")
        existing_clinic = FertilityClinic.query.filter_by(
            name=name,
        ).first()

        if existing_clinic:
            flash(
                f"Fertility Clinic '{name}' for already exists.",
                "info",
            )
            return existing_clinic

        clinic = self.add_fertility_clinic(
            name=spec.get("name"),
            fee_schedule_id=fee_schedule_id,
            notes=spec.get("notes"),
            affiliated_network=spec.get("affiliated_network"),
            id=spec.get("id"),
            uuid=spec.get("uuid"),
            created_at=spec.get("created_at"),
            modified_at=spec.get("modified_at"),
        )

        if "locations" in spec and isinstance(spec.get("locations"), list):
            for loc_spec in spec.get("locations"):
                loc_spec["fertility_clinic_id"] = clinic.id
                FertilityClinicLocationMaker().create_object_and_flush(loc_spec)

        if "allowed_domains" in spec and isinstance(spec.get("allowed_domains"), list):
            for domain_spec in spec.get("allowed_domains"):
                domain_spec["fertility_clinic_id"] = clinic.id
                FertilityClinicAllowedDomainMaker().create_object_and_flush(domain_spec)
        if "users" in spec and isinstance(spec.get("users"), list):
            for user_spec in spec.get("users"):
                user_spec["fertility_clinic_id"] = clinic.id
                FertilityClinicUserProfileMaker().create_object_and_flush(user_spec)

        return clinic


class FertilityClinicLocationMaker(_MakerBase):
    def add_fertility_clinic_location(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        name,
        address_1,
        city,
        subdivision_code,
        postal_code,
        country_code,
        fertility_clinic_id,
        phone_number="",
        email="",
        address_2=None,
        id=None,
        uuid=None,
        created_at=None,
        modified_at=None,
    ):
        fc_location = FertilityClinicLocation(
            name=name,
            address_1=address_1,
            city=city,
            subdivision_code=subdivision_code,
            postal_code=postal_code,
            country_code=country_code,
            fertility_clinic_id=fertility_clinic_id,
            phone_number=phone_number,
            email=email,
        )

        _add_time_logged_external_uuid_model_base_attr(
            fc_location, id, uuid, created_at, modified_at
        )
        if address_2:
            fc_location.address_2 = address_2

        db.session.add(fc_location)
        db.session.flush()

        return fc_location

    def create_object(self, spec, parent=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        location = self.add_fertility_clinic_location(
            name=spec.get("name"),
            address_1=spec.get("address_1"),
            address_2=spec.get("address_2"),
            city=spec.get("city"),
            subdivision_code=spec.get("subdivision_code"),
            postal_code=spec.get("postal_code"),
            country_code=spec.get("country_code"),
            phone_number=spec.get("name"),
            email=spec.get("email"),
            fertility_clinic_id=spec.get("fertility_clinic_id"),
            id=spec.get("id"),
            uuid=spec.get("uuid"),
            created_at=spec.get("created_at"),
            modified_at=spec.get("modified_at"),
        )
        return location


class FertilityClinicAllowedDomainMaker(_MakerBase):
    def add_fertility_clinic_allowed_domain(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        domain,
        fertility_clinic_id,
        id=None,
        uuid=None,
        created_at=None,
        modified_at=None,
    ):
        fc_allowed_domain = FertilityClinicAllowedDomain(
            domain=domain, fertility_clinic_id=fertility_clinic_id
        )

        _add_time_logged_external_uuid_model_base_attr(
            fc_allowed_domain, id, uuid, created_at, modified_at
        )

        db.session.add(fc_allowed_domain)
        db.session.flush()
        return fc_allowed_domain

    def create_object(self, spec, parent=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        allowed_domain = self.add_fertility_clinic_allowed_domain(
            domain=spec.get("domain"),
            fertility_clinic_id=spec.get("fertility_clinic_id"),
            id=spec.get("id"),
            uuid=spec.get("uuid"),
            created_at=spec.get("created_at"),
            modified_at=spec.get("modified_at"),
        )

        return allowed_domain


class FertilityClinicUserProfileMaker(_MakerBase):
    def create_object(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        profile = DataFactory(
            None, "no client"
        ).add_and_map_fertility_clinic_user_profile_and_user(
            first_name=spec.get("first_name"),
            last_name=spec.get("last_name"),
            role=spec.get("role"),
            fertility_clinic_id=spec.get("fertility_clinic_id"),
            email_prefix=spec.get("email_prefix"),
            password=spec.get("password"),
        )

        return profile


def _add_time_logged_external_uuid_model_base_attr(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    model, id, uuid, created_at, modified_at
):
    if id:
        model.id = id
    if uuid:
        model.uuid = uuid
    if created_at:
        model.created_at = created_at
    if modified_at:
        model.modified_at = modified_at
