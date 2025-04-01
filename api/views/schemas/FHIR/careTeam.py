from __future__ import annotations

from typing import Tuple

from marshmallow import Schema, fields

from models.profiles import MemberPractitionerAssociation, PractitionerProfile


class VerticalSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    pluralized_display_name = fields.String()
    description = fields.String()


class FHIRCareTeamMemberSchema(Schema):
    id = fields.Method("get_user_id")
    name = fields.Method("get_user_name")
    verticals = fields.Method("get_verticals")
    careTeamType = fields.Method("get_care_team_type")

    def get_user_id(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, obj: Tuple[PractitionerProfile, MemberPractitionerAssociation]
    ):
        (practitioner_profile, _) = obj
        return practitioner_profile.user_id

    def get_user_name(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, obj: Tuple[PractitionerProfile, MemberPractitionerAssociation]
    ):
        (practitioner_profile, _) = obj
        return f"{practitioner_profile.first_name} {practitioner_profile.last_name}"

    def get_verticals(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, obj: Tuple[PractitionerProfile, MemberPractitionerAssociation]
    ):
        (practitioner_profile, _) = obj
        return VerticalSchema(many=True).dump(practitioner_profile.verticals)

    def get_care_team_type(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self, obj: Tuple[PractitionerProfile, MemberPractitionerAssociation]
    ):
        (_, member_practitioner_association) = obj
        return member_practitioner_association.type.value  # type: ignore[attr-defined] # "str" has no attribute "value"
