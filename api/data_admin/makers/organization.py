import dateparser
from marshmallow import Schema
from marshmallow import fields as fields_v3

from data_admin.data_factory import DataFactory
from data_admin.maker_base import _MakerBase
from models.enterprise import (
    ModuleExtensionLogic,
    Organization,
    OrganizationExternalID,
    OrganizationModuleExtension,
)
from models.programs import Module
from models.verticals_and_specialties import VerticalGroupVersion
from storage.connection import db
from utils.log import logger
from views.schemas.common import MavenSchema
from views.schemas.common_v3 import MavenDateTime as V3MavenDateTime
from views.schemas.common_v3 import OrganizationEmployeeDataSchema, V3BooleanField
from wheelhouse.marshmallow_v1.marshmallow_v1 import fields

log = logger(__name__)


class OrganizationEmployeeSchema(Schema):
    organization_name = fields_v3.String(dump_default="Maven", load_default="Maven")
    company_email = fields_v3.String(dump_default="Maven", load_default="random")
    date_of_birth = V3MavenDateTime()
    unique_corp_id = fields_v3.String()
    dependent_id = fields_v3.String()
    beneficiaries_enabled = V3BooleanField()
    wallet_enabled = V3BooleanField()
    first_name = fields_v3.String()
    last_name = fields_v3.String()
    work_state = fields_v3.String()
    can_get_pregnant = V3BooleanField()
    address = fields_v3.Nested(OrganizationEmployeeDataSchema)


class OrganizationEmployeeDependentSchema(MavenSchema):
    member_email = fields.String()
    first_name = fields.String()
    middle_name = fields.String()
    last_name = fields.String()


class OrganizationMaker(_MakerBase):
    def create_object(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        _vgv_name = spec.get("vertical_group_version", "Enterprise")
        vgv = (
            VerticalGroupVersion.query.filter_by(name=_vgv_name).first()
            or VerticalGroupVersion.query.filter_by(name="Enterprise").first()
            or VerticalGroupVersion(name="Enterprise")
        )
        db.session.add(vgv)
        db.session.flush()

        activated_at = None
        if spec.get("activated_at"):
            activated_at = dateparser.parse(spec.get("activated_at"))

        org = DataFactory(None, "no client").add_organization(
            name=spec.get("name"),
            vertical_group_version=vgv.name,
            medical_plan_only=spec.get("medical_plan_only"),
            employee_only=spec.get("employee_only"),
            bms_enabled=spec.get("bms_enabled"),
            alternate_verification=spec.get("alternate_verification"),
            allowed_track_names=spec.get("allowed_track_names"),
            associated_care_coordinator=spec.get("associated_care_coordinator"),
            activated_at=activated_at,
            add_tracks=spec.get("client_tracks") is None,
            client_tracks=spec.get("client_tracks"),
            alegeus_employer_id=spec.get("alegeus_employer_id"),
        )

        return org


class OrganizationExternalIDMaker(_MakerBase):
    def create_object(self, spec) -> OrganizationExternalID:  # type: ignore[no-untyped-def,override] # Signature of "create_object" incompatible with supertype "_MakerBase"
        organization = Organization.query.filter_by(
            name=spec.get("organization")
        ).first()
        organization_external_id = OrganizationExternalID(
            idp=spec.get("idp"),
            external_id=spec.get("external_id"),
            organization=organization,
        )
        db.session.add(organization_external_id)
        db.session.flush()
        return organization_external_id


class OrganizationModuleExtensionMaker(_MakerBase):
    @staticmethod
    def create_object(spec) -> OrganizationModuleExtension:  # type: ignore[no-untyped-def,override] # Signature of "create_object" incompatible with supertype "_MakerBase"
        org = Organization.query.filter_by(name=spec["organization_name"]).one()
        module = Module.query.filter_by(name=spec["module_name"]).one()
        effective_from = dateparser.parse(spec.get("effective_from", "now"))
        extension = OrganizationModuleExtension(
            organization_id=org.id,
            module_id=module.id,
            extension_logic=spec.get("extension_logic", ModuleExtensionLogic.ALL.value),
            extension_days=spec.get("extension_days", 1000),
            priority=spec.get("priority", 1),
            effective_from=effective_from,
        )
        db.session.add(extension)
        db.session.flush()
        return extension
