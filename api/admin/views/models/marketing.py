from __future__ import annotations

import urllib
from typing import Any, List, Optional, Type

from flask import Markup, flash, request
from flask_admin import expose
from flask_admin.actions import action
from flask_admin.contrib.sqla.filters import BooleanEqualFilter
from flask_admin.form import rules
from flask_pagedown.fields import PageDownField
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import joinedload, noload
from sqlalchemy.sql import and_
from wtforms import ValidationError, fields, form, validators

from admin.common import (
    Select2MultipleField,
    TimeDeltaField,
    slug_re_check,
    snake_case_check,
)
from admin.views.base import (
    AdminCategory,
    AdminViewT,
    ContainsFilter,
    FormToJSONField,
    MavenAuditedView,
)
from admin.views.models.images import ImageUploadField
from audit_log import utils as audit_utils
from authn.models.user import User
from authz.models.roles import ROLES, Role
from learn.models.migration import ContentfulMigrationStatus
from models.marketing import (
    ConnectedContentField,
    IosNonDeeplinkUrl,
    PopularTopic,
    Resource,
    ResourceConnectedContent,
    ResourceConnectedContentTrackPhase,
    ResourceContentTypes,
    ResourceOnDemandClass,
    ResourceTrack,
    ResourceTrackPhase,
    ResourceTypes,
    Tag,
    TextCopy,
    URLRedirect,
    URLRedirectPath,
)
from models.profiles import PractitionerProfile
from models.tracks import TrackName
from models.tracks.phase import generate_phase_names
from models.virtual_events import (
    VirtualEvent,
    VirtualEventCategory,
    VirtualEventCategoryTrack,
)
from storage.connection import RoutingSQLAlchemy, db
from utils import zoom
from utils.log import logger

log = logger(__name__)


def _format_track_phase(track, phase):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return f"{track}/{phase}"


class ResourceViewTagFilter(ContainsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(Resource.tags).filter(Tag.name.contains(value))  # type: ignore[attr-defined] # "str" has no attribute "contains"


class ResourceViewConnectedContentPhasesFilter(ContainsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(Resource.connected_content_track_phases).filter(
            ResourceConnectedContentTrackPhase.phase_name.contains(value)
        )


class ResourceViewTrackFilter(ContainsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(Resource.allowed_tracks).filter(
            ResourceTrack.track_name.contains(value)
        )


class ResourceViewHasTrackFilter(BooleanEqualFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value == "1":
            return query.filter(
                Resource.id.in_(
                    db.session.query(Resource.id).join(Resource.allowed_tracks)
                )
            )
        else:
            return query.filter(
                Resource.id.notin_(
                    db.session.query(Resource.id).join(Resource.allowed_tracks)
                )
            )


class ResourceViewHasTagFilter(BooleanEqualFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value == "1":
            return query.filter(
                Resource.id.in_(db.session.query(Resource.id).join(Resource.tags))
            )
        else:
            return query.filter(
                Resource.id.notin_(db.session.query(Resource.id).join(Resource.tags))
            )


class ConnectedContentFormField(fields.FormField):
    def populate_obj(self, resource, _):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        existing_fields = {
            rcc.field.name: rcc for rcc in resource.connected_content_fields
        }
        cc_fields = {f.name: f for f in ConnectedContentField.query.all()}
        for name, value in self.form.data.items():
            if name in existing_fields:
                existing_fields[name].value = value
            else:
                resource.connected_content_fields.append(
                    ResourceConnectedContent(
                        resource=resource, value=value, field=cc_fields[name]
                    )
                )


class ResourceView(MavenAuditedView):
    read_permission = "read:resource"
    delete_permission = "delete:resource"
    create_permission = "create:resource"
    edit_permission = "edit:resource"

    required_capability = "admin_resource"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    audit_model_view = True  # type: ignore[assignment] # Incompatible types in assignment (expression has type "bool", base class "MavenAuditedView" defined the type as "None")

    edit_template = "resource_edit_template.html"
    create_template = "resource_edit_template.html"

    column_list = (
        "id",
        "title",
        "slug",
        "webflow_url",
        "published_at",
        "resource_type",
        "content_type",
        "tags",
        "allowed_track_names",
        "allowed_track_phase_names",
        "connected_content_track_phases",
        "contentful_status",
    )
    column_editable_list = ["tags", "content_type"]
    column_searchable_list = ["title", "body"]
    column_filters = (
        "id",
        "resource_type",
        "content_type",
        "contentful_status",
        "published_at",
        "title",
        "slug",
        "webflow_url",
        ResourceViewTagFilter(None, "Tag Name"),
        ResourceViewTrackFilter(None, "Track Name"),
        ResourceViewHasTrackFilter(None, "Has Track"),
        ResourceViewHasTagFilter(None, "Has Tag"),
        ResourceViewConnectedContentPhasesFilter(None, "Connected content phases"),
    )

    form_columns = (
        "title",
        "subhead",
        "tags",
        "webflow_url",
        "body",
        "resource_type",
        "content_type",
        "contentful_status",
        "published_at",
        "allowed_organizations",
        "connected_content_type",
        "slug",
        "image_id",
    )

    form_choices = {"content_type": [(c.name, c.value) for c in ResourceContentTypes]}

    column_labels = {
        "allowed_track_names": "Allowed tracks (modules)",
        "allowed_track_phase_names": "Allowed phases (for dashboards)",
        "connected_content_track_phases": "Connected content phases",
    }

    column_formatters = {
        "title": lambda v, c, m, p: Markup(
            f"<a href='{m.content_url if m.resource_type == ResourceTypes.ENTERPRISE else m.custom_url}' target='_blank'><span class='glyphicon icon-share'></span> {m.title}</a>"
        ),
        "allowed_track_names": lambda v, c, m, p: [
            name.value for name in m.allowed_track_names
        ],
        "connected_content_track_phases": lambda v, c, m, p: [
            _format_track_phase(content_phase.track_name, content_phase.phase_name)
            for content_phase in m.connected_content_track_phases
        ],
        "webflow_url": lambda v, c, m, p: bool(m.webflow_url),
    }

    @action(
        "unpublish_resources",
        "Unpublish Resources",
        "You sure? This will unpublish all the selected resources!",
    )
    def unpublish_resources(self, resource_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        db.session.bulk_update_mappings(
            Resource,
            [{"id": resource_id, "published_at": None} for resource_id in resource_ids],
        )
        resources = db.session.query(Resource).filter(Resource.id.in_(resource_ids))
        audit_utils.emit_bulk_audit_log_update(resources)
        db.session.commit()

    # these bulk actions are in the UI in alphabetical order, hence the 1, 2, 3
    @action(
        "contentful_status_1_not_started",
        "Set Contentful status to NOT_STARTED",
        "You sure? This will set Contentful status to NOT_STARTED for all the selected resources!",
    )
    def contentful_status_1_not_started(self, resource_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.set_bulk_contentful_status(
            resource_ids, ContentfulMigrationStatus.NOT_STARTED
        )

    @action(
        "contentful_status_2_in_progress",
        "Set Contentful status to IN_PROGRESS",
        "You sure? This will set Contentful status to IN_PROGRESS for all the selected resources!",
    )
    def contentful_status_2_in_progress(self, resource_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.set_bulk_contentful_status(
            resource_ids, ContentfulMigrationStatus.IN_PROGRESS
        )

    @action(
        "contentful_status_3_live",
        "Set Contentful status to LIVE",
        "You sure? This will set Contentful status to LIVE for all the selected resources and the article content will now start coming from Contentful!",
    )
    def contentful_status_3_live(self, resource_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        any_resources_not_started = (
            db.session.query(Resource)
            .filter(
                and_(
                    Resource.contentful_status == ContentfulMigrationStatus.NOT_STARTED,
                    Resource.id.in_(resource_ids),
                )
            )
            .first()
        )
        if any_resources_not_started:
            flash(
                "At least one resource was set to NOT_STARTED and cannot be moved directly to LIVE. Please try again. ",
                category="error",
            )
            return
        self.set_bulk_contentful_status(resource_ids, ContentfulMigrationStatus.LIVE)

    @staticmethod
    def set_bulk_contentful_status(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        resource_ids: List[int], status: ContentfulMigrationStatus
    ):
        resources = (
            db.session.query(Resource).filter(Resource.id.in_(resource_ids)).all()
        )
        for resource in resources:
            resource.contentful_status = status

        audit_utils.emit_bulk_audit_log_update(resources)

        db.session.commit()
        flash(
            f"Successfully set selected resources to Contentful status of {status.value}",
            category="success",
        )

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()

        phase_names = [
            _format_track_phase(track_name, phase_name)
            for track_name in TrackName
            for phase_name in generate_phase_names(track_name)
        ]

        form_class.connected_content_track_phases_field = Select2MultipleField(
            label="Connected content phases (for Braze connected content emails)",
            choices=[(p, p) for p in phase_names],
        )

        form_class.tracks = Select2MultipleField(
            label="Allowed tracks (for library/dashboards)",
            choices=[(track.value, track.value) for track in TrackName],
        )

        form_class.track_phases = Select2MultipleField(
            label="Allowed phases (for library/dashboards)",
            choices=[(p, p) for p in phase_names],
        )

        form_class.slug = fields.StringField(
            label="Slug (leave blank to generate from title)",
            validators=[slug_re_check],
        )
        form_class.body = PageDownField(render_kw={"rows": 20})
        form_class.image_id = ImageUploadField(
            label="Image", allowed_extensions=["jpg", "png"]
        )

        try:
            form_class.connected_content_info = ConnectedContentFormField(
                type(
                    "_ConnectedContentFieldsForm",
                    (form.Form,),
                    {
                        c.name: fields.StringField(c.name)
                        for c in ConnectedContentField.query
                    },
                )
            )
        except (ProgrammingError, RuntimeError):
            # this will happen when the app is first starting (can't query yet)
            pass

        form_class.on_demand_class_length = TimeDeltaField(
            label="Class Length",
            validators=[
                required_if_field_value(
                    "content_type", ResourceContentTypes.on_demand_class.name
                )
            ],
        )
        form_class.on_demand_class_instructor = fields.StringField(
            label="Class Instructor's Provider Type/Speciality",
            description='This field will be prefixed with "Led by". For example: "Led by Postpartum Doula" or "Led by '
            'Mental Health Provider"',
            validators=[
                validators.length(max=120),
                required_if_field_value(
                    "content_type", ResourceContentTypes.on_demand_class.name
                ),
            ],
        )

        return form_class

    def on_form_prefill(self, form, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_form_prefill(form, id)
        resource = db.session.query(self.model).get(id)
        if resource is None:
            return
        form.connected_content_info.form.process(
            data={c.field.name: c.value for c in resource.connected_content_fields}
        )

        form.tracks.process_formdata([n.value for n in resource.allowed_track_names])
        form.track_phases.process_formdata(
            [str(n) for n in resource.allowed_track_phase_names]
        )

        form.connected_content_track_phases_field.process_formdata(
            [str(n) for n in resource.connected_content_track_phase_names]
        )

        if resource.on_demand_class_fields:
            form.on_demand_class_length.data = resource.on_demand_class_fields.length
            form.on_demand_class_instructor.data = (
                resource.on_demand_class_fields.instructor
            )

    @expose("/edit/", methods=("GET", "POST"))
    def edit_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self._refresh_forms_cache()
        return super().edit_view()

    @expose("/new/", methods=("GET", "POST"))
    def create_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self._refresh_forms_cache()
        return super().create_view()

    def create_model(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not self._check_unique_cc_phase(form):
            return False
        return super().create_model(form)

    def update_model(self, form, model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # skip the check in list view
        if hasattr(
            form, "connected_content_track_phases_field"
        ) and not self._check_unique_cc_phase(form, model):
            return False
        return super().update_model(form, model)

    def on_model_change(self, form, resource, is_created):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_model_change(form, resource, is_created)
        if resource.webflow_url:
            try:
                resource.pull_image_from_webflow()
            except Exception as e:
                log.exception(e)
                flash(
                    "Warning: unable to fetch image automatically from webflow. Try saving the resource again.",
                    "warning",
                )

        resource.allowed_tracks = [
            ResourceTrack(track_name=track, resource_id=resource.id)
            for track in request.form.getlist("tracks")  # multiple
        ]

        allowed_track_phases = []
        for tp in request.form.getlist("track_phases"):
            # keep this consistent with how we format names in scaffold_form
            track_name, phase_name = tp.split("/")
            allowed_track_phases.append(
                ResourceTrackPhase(
                    resource_id=resource.id,
                    track_name=track_name,
                    phase_name=phase_name,
                )
            )
        resource.allowed_track_phases = allowed_track_phases

        connected_content_track_phases = []
        for tp in request.form.getlist("connected_content_track_phases_field"):
            # keep this consistent with how we format names in scaffold_form
            track_name, phase_name = tp.split("/")
            connected_content_track_phases.append(
                ResourceConnectedContentTrackPhase(
                    resource_id=resource.id,
                    track_name=track_name,
                    phase_name=phase_name,
                )
            )
        resource.connected_content_track_phases = connected_content_track_phases

        if resource.content_type == ResourceContentTypes.on_demand_class.name:
            if resource.on_demand_class_fields:
                resource.on_demand_class_fields.length = resource.on_demand_class_length
                resource.on_demand_class_fields.instructor = (
                    resource.on_demand_class_instructor
                )
            else:
                resource.on_demand_class_fields = ResourceOnDemandClass(
                    length=resource.on_demand_class_length,
                    instructor=resource.on_demand_class_instructor,
                )
        else:
            resource.on_demand_class_fields = None

    def _check_unique_cc_phase(self, form, resource=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        existing_relationships = db.session.query(
            ResourceConnectedContentTrackPhase
        ).all()
        ok = True
        for cc_phase in form.connected_content_track_phases_field.data:
            for relationship in existing_relationships:
                phase_name = _format_track_phase(
                    relationship.track_name, relationship.phase_name
                )
                if cc_phase == phase_name:
                    existing_resource_id = relationship.resource_id
                    if resource and resource.id == existing_resource_id:
                        continue
                    if (
                        Resource.query.get(existing_resource_id).connected_content_type
                        == form.data["connected_content_type"]
                    ):
                        ok = False
                        flash(
                            "Resource id {} already points to connected content phase id {}, "
                            "and has connected content type of {}".format(
                                existing_resource_id,
                                phase_name,
                                form.connected_content_type.data,
                            ),
                            category="error",
                        )
        return ok

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
            Resource,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class VirtualEventView(MavenAuditedView):
    read_permission = "read:virtual-event"
    delete_permission = "delete:virtual-event"
    create_permission = "create:virtual-event"
    edit_permission = "edit:virtual-event"

    required_capability = "admin_resource"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")
    audit_model_view = True  # type: ignore[assignment] # Incompatible types in assignment (expression has type "bool", base class "MavenAuditedView" defined the type as "None")
    create_template = "virtual_event_create_edit_template.html"
    edit_template = "virtual_event_create_edit_template.html"

    column_list = (
        "title",
        "registration_form_url",
        "scheduled_start",
        "scheduled_end",
        "active",
        "rsvp_required",
        "host_name",
        "host_image_url",
    )

    form_columns = (
        "title",
        "registration_form_url",
        "description",
        "webinar_id",
        "scheduled_start",
        "scheduled_end",
        "active",
        "rsvp_required",
        "host_name",
        "host_specialty",
        "host_image_url",
        "provider_profile_url",
        "cadence",
        "event_image_url",
        "description_body",
        "what_youll_learn_body",
        "what_to_expect_body",
        "virtual_event_category",
    )

    form_widget_args = {
        "registration_form_url": {"type": "url"},
        "description": {"maxlength": 200},
        "description_body": {"rows": 5, "maxlength": 500},
        "what_youll_learn_body": {"rows": 5, "maxlength": 500},
        "what_to_expect_body": {"rows": 5, "maxlength": 500},
    }

    form_overrides = {
        "description": fields.TextAreaField,
        "description_body": fields.TextAreaField,
        "what_youll_learn_body": fields.TextAreaField,
        "what_to_expect_body": fields.TextAreaField,
    }

    column_descriptions = {
        "description": "Character limit: 200 - Shorter description used on the event card",
        "host_specialty": 'This field will be prefixed with "Host:". For example: "Host: Postpartum Doula" or "Host: '
        'Mental Health Provider"',
        "provider_profile_url": 'Populates after choosing practitioner from dropdown. Format: "/practitioner/:id"',
        "description_body": "Character limit: 500 - Longer description used on the registration page.",
        "what_youll_learn_body": "Character limit: 500",
        "what_to_expect_body": "Character limit: 500",
        "webinar_id": "The 10 or 11 digit webinar id from Zoom",
    }

    form_rules = (
        "title",
        "registration_form_url",
        "description",
        "webinar_id",
        rules.HTML('<div id="webinar_info"></div><hr />'),
        "scheduled_start",
        "scheduled_end",
        "active",
        "rsvp_required",
        "host_name",
        "host_specialty",
        "host_image_url",
        "provider_profile_url",
        "cadence",
        "event_image_url",
        "description_body",
        "what_youll_learn_body",
        "what_to_expect_body",
        "virtual_event_category",
    )

    def create_form(self, obj=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return self._form_class_with_validator(super().create_form(obj))

    def edit_form(self, obj=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return self._form_class_with_validator(super().edit_form(obj))

    def _form_class_with_validator(self, form_class):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        form_class.registration_form_url.validators = [
            required_if_field_value("rsvp_required", False)
        ]

        return form_class

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if model.registration_form_url:
            model.registration_form_url = model.registration_form_url.strip()
        super().on_model_change(form, model, is_created)

    @expose("/new/", methods=("GET", "POST"))
    def create_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self.fetch_practitioner_info()
        return super().create_view()

    @expose("/edit/", methods=("GET", "POST"))
    def edit_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self.fetch_practitioner_info()
        return super().edit_view()

    @expose("/zoom_info", methods=("GET",))
    def zoom_info(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        webinar_id_str = request.args.get("id", "")
        if not webinar_id_str.isnumeric():
            return {
                "errors": [
                    {
                        "status": 400,
                        "title": "Bad request",
                        "detail": "Must provide numeric webinar_id",
                    }
                ]
            }, 400
        resp = zoom.get_webinar_info(int(webinar_id_str))
        return resp.json()

    def fetch_practitioner_info(self) -> None:
        practitioners = (
            User.query.join(PractitionerProfile)
            .join(Role)
            .distinct(PractitionerProfile.user_id)
            .filter(
                Role.name == ROLES.practitioner, PractitionerProfile.active.is_(True)
            )
            .options(
                joinedload(User.image),
                # Would get eager loaded otherwise
                noload("roles"),
                noload("member_profile"),
            )
            .order_by(User.first_name)
            .all()
        )
        self._template_args["practitioner_dict"] = {}
        for practitioner in practitioners:
            self._template_args["practitioner_dict"][practitioner.id] = {
                "name": f"{practitioner.first_name or ''} {practitioner.last_name or ''}",
                "image_url": practitioner.image
                and practitioner.image.asset_url()
                or "",
                "id": practitioner.id,
                "specialty": practitioner.practitioner_profile.verticals
                and practitioner.practitioner_profile.verticals[0].display_name,
            }
        self._template_args["practitioner_ids"] = list(
            self._template_args["practitioner_dict"].keys()
        )

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
            VirtualEvent,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ConnectedContentFieldView(MavenAuditedView):
    read_permission = "read:connected-content-field"
    create_permission = "create:connected-content-field"

    required_capability = "admin_connected_content_field"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

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
            ConnectedContentField,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class TagView(MavenAuditedView):
    read_permission = "read:tag"
    delete_permission = "delete:tag"
    create_permission = "create:tag"
    edit_permission = "edit:tag"

    required_capability = "admin_tag"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    audit_model_view = True  # type: ignore[assignment] # Incompatible types in assignment (expression has type "bool", base class "MavenAuditedView" defined the type as "None")

    form_columns = ("name", "display_name", "modified_at")

    form_args = {"name": {"validators": [snake_case_check]}}

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
            Tag,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class TextCopyView(MavenAuditedView):
    read_permission = "read:text-copy"
    delete_permission = "delete:text-copy"
    create_permission = "create:text-copy"
    edit_permission = "edit:text-copy"

    column_exclude_list = ("created_at", "modified_at")
    can_view_details = True

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: Optional[str] = None,
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            TextCopy,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class URLRedirectPathView(MavenAuditedView):
    read_permission = "read:url-redirect-path"
    delete_permission = "delete:url-redirect-path"
    create_permission = "create:url-redirect-path"
    edit_permission = "edit:url-redirect-path"

    required_capability = "admin_url_redirects"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    column_exclude_list = ("created_at", "modified_at")
    form_widget_args = {
        "created_at": {"readonly": True},
        "modified_at": {"readonly": True},
    }

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
            URLRedirectPath,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class URLRedirectView(MavenAuditedView):
    read_permission = "read:url-redirect"
    delete_permission = "delete:url-redirect"
    create_permission = "create:url-redirect"
    edit_permission = "edit:url-redirect"

    required_capability = "admin_url_redirects"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    edit_template = "url_redirect_edit_template.html"
    create_template = "url_redirect_edit_template.html"

    column_list = (
        "path",
        "active",
        "dest_url_redirect_path",
        "dest_url_args",
        "organization",
    )
    form_columns = ("path", "active", "dest_url_redirect_path", "organization")
    form_rules = [
        "path",
        "active",
        "dest_url_redirect_path",
        "dest_url_args",
        "organization",
        rules.HTML(
            '<h4>Preview:</h4><strong><a href="" id="url-preview-link">'
            '</a><span id="url-preview"></span></strong>'
        ),
    ]

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if (
            not is_created
            and "_continue_editing" in request.form
            and request.args["id"] != model.path
        ):
            url_parts = list(urllib.parse.urlparse(request.url))
            query = dict(urllib.parse.parse_qsl(url_parts[4]))
            query["id"] = model.path
            url_parts[4] = urllib.parse.urlencode(query)
            request.url = urllib.parse.urlunparse(url_parts)
        super().on_model_change(form, model, is_created)

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()
        form_class.dest_url_args = FormToJSONField(
            {name: "" for name in URLRedirect.DEST_URL_ARG_NAMES}
        )
        return form_class

    @classmethod
    def factory(
        cls: Type[AdminViewT],
        *,
        session: Optional[RoutingSQLAlchemy] = None,
        category: Optional[AdminCategory] = None,
        name: Optional[str] = None,
        endpoint: Optional[str] = None,
        **kwargs: Any,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            URLRedirect,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class PopularTopicView(MavenAuditedView):
    read_permission = "read:popular-topic"
    delete_permission = "delete:popular-topic"
    create_permission = "create:popular-topic"
    edit_permission = "edit:popular-topic"

    required_capability = "admin_resource"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")
    audit_model_view = True  # type: ignore[assignment] # Incompatible types in assignment (expression has type "bool", base class "MavenAuditedView" defined the type as "None")
    can_view_details = True
    column_default_sort = [("track_name", False), ("sort_order", False)]
    column_descriptions = {
        "sort_order": "The popular topics will be sorted in ascending order"
    }
    column_editable_list = ("sort_order",)
    column_exclude_list = ("created_at", "modified_at")
    column_filters = (
        "track_name",
        "topic",
    )
    column_searchable_list = ("track_name", "topic")
    form_choices = {"track_name": [(track.value, track.value) for track in TrackName]}
    form_excluded_columns = ("created_at", "modified_at")

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
            PopularTopic,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


def required_if_field_value(other_field_name, value):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    message = f'This field is required when [{other_field_name}] is "{value}"'

    def _required_if_field_value(form, field):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        other_field_value = form._fields.get(other_field_name).data
        if other_field_value == value and not field.data:
            raise ValidationError(message)

    return _required_if_field_value


# TODO: No longer used, remove as part of COCO-2433
class IosNonDeeplinkUrlView(MavenAuditedView):
    read_permission = "read:ios-non-deeplink-url"
    delete_permission = "delete:ios-non-deeplink-url"
    create_permission = "create:ios-non-deeplink-url"
    edit_permission = "edit:ios-non-deeplink-url"

    required_capability = "admin_resource"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")
    column_list = ("url",)
    form_columns = ("url",)

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
            IosNonDeeplinkUrl,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_model_change(form, model, is_created)
        IosNonDeeplinkUrl.clear_cache()

    def on_model_delete(self, model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_model_delete(model)
        IosNonDeeplinkUrl.clear_cache()


class VirtualEventCategoryView(MavenAuditedView):
    read_permission = "read:virtual-event-category"
    delete_permission = "delete:virtual-event-category"
    create_permission = "create:virtual-event-category"
    edit_permission = "edit:virtual-event-category"

    required_capability = "admin_resource"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")
    column_list = ("name",)
    form_excluded_columns = ("created_at", "modified_at")

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
            VirtualEventCategory,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class VirtualEventCategoryTrackView(MavenAuditedView):
    read_permission = "read:virtual-event-category-track"
    delete_permission = "delete:virtual-event-category-track"
    create_permission = "create:virtual-event-category-track"
    edit_permission = "edit:virtual-event-category-track"

    required_capability = "admin_resource"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")
    column_list = (
        "category.name",
        "track_name",
        "availability_start_week",
        "availability_end_week",
    )
    form_excluded_columns = ("created_at", "modified_at")

    form_choices = {"track_name": [(track.value, track.value) for track in TrackName]}

    column_descriptions = {
        "availability_start_week": "The week at which a user should start seeing events in this category",
        "availability_end_week": "The last week at which a user should still see events in this category",
    }

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy | None = None,
        category: AdminCategory | None = None,
        name: str | None = None,
        endpoint: str | None = None,
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            VirtualEventCategoryTrack,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
