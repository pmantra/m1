from typing import Type

from flask_admin.form import Select2Field

from admin.views.base import AdminCategory, AdminViewT, ContainsFilter, MavenAuditedView
from models.tracks import TrackName
from provider_matching.models.practitioner_track_vgc import PractitionerTrackVGC
from provider_matching.models.vgc import VGC
from storage.connection import RoutingSQLAlchemy, db


class TrackFilter(ContainsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value == "":
            return query
        value_camel_case = value.replace(" ", "_").lower()
        return query.filter(PractitionerTrackVGC.track.contains(value_camel_case))


class CareTeamAssignmentView(MavenAuditedView):
    read_permission = "read:update-care-teams"
    delete_permission = "delete:update-care-teams"
    create_permission = "create:update-care-teams"

    can_view_details = True

    column_list = (
        "practitioner_id",
        "practitioner.user.full_name",
        "practitioner.active",
        "track",
        "vgc",
        "created_at",
    )
    column_sortable_list = (
        "practitioner_id",
        "practitioner.active",
        "track",
        "vgc",
        "created_at",
    )
    column_filters = (
        "practitioner_id",
        "practitioner.active",
        TrackFilter(None, "Track"),
        "vgc",
    )

    column_labels = {
        "practitioner_id": "Practitioner ID",
        "practitioner.user.full_name": "Practitioner Name",
        "practitioner.active": "Active",
        "created_at": "Added On",
        "track": "Track",
        "vgc": "VGC",
    }
    column_formatters = {
        "track": lambda v, c, m, p: m.track.replace("_", " ").capitalize(),
    }
    column_searchable_list = ("practitioner_id", "track", "vgc")

    form_widget_args = {
        "created_at": {"disabled": True},
        "modified_at": {"disabled": True},
    }
    form_ajax_refs = {"practitioner": {"fields": ("user_id",), "page_size": 10}}

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            PractitionerTrackVGC,
            session or db.session,
            category=category,
            name="Update Care Teams",
            endpoint=endpoint,
            **kwargs,
        )

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()
        form_class.track = Select2Field(
            label="Track",
            choices=[
                (track.value, track.value.replace("_", " ").capitalize())
                for track in TrackName
            ],
            allow_blank=False,
        )
        form_class.vgc = Select2Field(
            label="VGC",
            choices=[(vgc.value, vgc.value) for vgc in VGC],
            allow_blank=False,
        )
        return form_class
