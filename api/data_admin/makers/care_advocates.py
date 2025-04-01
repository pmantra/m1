from marshmallow_v1 import fields

from care_advocates.models.transitions import CareAdvocateMemberTransitionTemplate
from data_admin.maker_base import _MakerBase
from data_admin.makers.appointments import ScheduleEventMaker
from data_admin.makers.user import UserMaker
from storage.connection import db
from views.schemas.common import MavenSchema


class CareAdvocateMemberTransitionTemplateSchema(MavenSchema):
    message_type = fields.String()
    message_description = fields.String()
    message_body = fields.String()
    sender = fields.String()


class CareAdvocateMemberTransitionTemplateMaker(_MakerBase):
    spec_class = CareAdvocateMemberTransitionTemplateSchema(strict=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "CareAdvocateMemberTransitionTemplateSchema", base class "_MakerBase" defined the type as "None")

    def create_object(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        spec_data = self.spec_class.load(spec).data  # type: ignore[has-type] # Cannot determine type of "spec_class"
        ca_member_transition_template = CareAdvocateMemberTransitionTemplate(
            message_type=spec_data.get("message_type"),
            message_description=spec_data.get("message_description"),
            message_body=spec_data.get("message_body"),
            sender=spec_data.get("sender"),
        )

        db.session.add(ca_member_transition_template)
        db.session.flush()
        return ca_member_transition_template


class CareAdvocateMembersMaker(_MakerBase):
    def create_object(self, spec_data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        result = []
        ca = UserMaker().create_object_and_flush(spec_data)
        db.session.add(ca)
        result.append(ca)
        for member in spec_data.get("members"):
            member["care_team"] = [ca.email]
            user = UserMaker().create_object_and_flush(member)
            db.session.add(user)
            result.append(user)
        for schedule_event in spec_data.get("schedule_events"):
            schedule_event["practitioner"] = ca.email
            event = ScheduleEventMaker().create_object_and_flush(schedule_event)
            db.session.add(event)
        db.session.flush()
        return result
