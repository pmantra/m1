from typing import Type

from flask import flash
from flask_admin.actions import action
from flask_admin.contrib.sqla.ajax import QueryAjaxModelLoader
from flask_admin.contrib.sqla.fields import InlineModelFormList, QuerySelectField
from flask_admin.contrib.sqla.form import InlineModelConverter
from flask_admin.form import RenderTemplateWidget, rules
from flask_admin.model import InlineFormAdmin
from flask_admin.model.ajax import DEFAULT_PAGE_SIZE
from flask_login import current_user
from markupsafe import Markup
from sqlalchemy import or_
from sqlalchemy.orm.interfaces import MapperProperty
from wtforms import fields, validators

from admin.views.base import USER_AJAX_REF, AdminCategory, AdminViewT, MavenAuditedView
from models.programs import CareProgram, CareProgramPhase, Enrollment, Module, Phase
from models.tracks import ChangeReason, lifecycle
from storage.connection import RoutingSQLAlchemy, db
from utils.log import logger

log = logger(__name__)


class InlinePhaseView(MavenAuditedView):
    required_capability = "admin_module"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")
    form_columns = (
        "id",
        "name",
        "frontend_name",
        "is_entry",
        "is_transitional",
        "auto_transition_module",
        "onboarding_assessment_lifecycle",
    )

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()
        form_class.id = fields.HiddenField()
        return form_class

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
            Phase,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ModuleView(MavenAuditedView):
    read_permission = "read:module"
    create_permission = "create:module"
    edit_permission = "edit:module"

    required_capability = "admin_module"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    column_list = (
        "id",
        "name",
        "partner_module",
        "number_of_phases",
        "admin_module_configured",
    )

    column_labels = {
        "number_of_phases": "# Phases",
        "admin_module_configured": "Module Configured",
        "onboarding_display_label": "Display Label",
        "onboarding_display_order": "Display Order",
        "onboarding_as_partner": "As Partner",
    }
    form_rules = [
        "name",
        "frontend_name",
        rules.FieldSet(
            ("phase_logic", "program_length_logic", "days_in_transition", "duration"),
            "Characteristics",
        ),
        rules.FieldSet(("is_maternity",), "Eligibility"),
        rules.FieldSet(("partner_module",), "Enrollments"),
        rules.FieldSet(
            (
                "onboarding_display_label",
                "onboarding_display_order",
                "onboarding_as_partner",
            ),
            "Onboarding",
        ),
        rules.FieldSet(
            ("restrict_booking_verticals", "vertical_groups"), "Booking Flow"
        ),
    ]
    _inline_models = None

    @property
    def inline_models(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self._inline_models is None:
            self._inline_models = (InlinePhaseView.factory(session=self.session),)
        return self._inline_models

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()
        form_class.partner_module = QuerySelectField(
            query_factory=lambda: Module.query,
            validators=[validators.Optional()],
            allow_blank=True,
        )
        return form_class

    def get_list(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        page,
        sort_column,
        sort_desc,
        search,
        filters,
        execute=True,
        page_size=None,
    ):
        if any(any(m.module_configuration_errors) for m in self.model.query):
            flash(
                "Modules must be configured correctly before they can be allowed for a new organization."
            )
        return super().get_list(
            page, sort_column, sort_desc, search, filters, execute, page_size
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
            Module,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class PromptDashboardLoader(QueryAjaxModelLoader):
    def get_list(self, term, offset=0, limit=DEFAULT_PAGE_SIZE):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        query = self.session.query(self.model).filter(self.model.is_prompt)

        filters = (field.ilike("%%%s%%" % term) for field in self._cached_fields)
        query = query.filter(or_(*filters))

        if self.order_by:
            query = query.order_by(self.order_by)

        return query.offset(offset).limit(limit).all()


class EnrollmentView(MavenAuditedView):
    read_permission = "read:enrollment"
    delete_permission = "delete:enrollment"
    create_permission = "create:enrollment"
    edit_permission = "edit:enrollment"

    required_capability = "admin_care_program"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")
    column_filters = ("organization_id", "care_programs.id", "care_programs.user_id")
    column_list = ("organization", "care_programs", "modifed_at", "created_at")

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
            Enrollment,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class PhaseHistoryWidget(RenderTemplateWidget):
    def __init__(self) -> None:
        super().__init__("phase_history_with_split.html")


class PhaseHistoryFormList(InlineModelFormList):
    widget = PhaseHistoryWidget()


class PhaseHistoryConverter(InlineModelConverter):
    inline_field_list_type = PhaseHistoryFormList
    exclude_properties = frozenset(("first_phase", "last_phase", "current_phase"))

    def _calculate_mapping_key_pair(self, model, info):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """HOLD YOUR NOSE - super shitty hack comin at ya.

        Flask-Admin doesn't support one-to-one relationships on Inline Model Forms.
        It ALSO doesn't support multiple relationships of the same child.

        ALSO ALSO this all occurs BEFORE we actually render the fields,
        so just using `form_excluded_columns` on the view doesn't work.

        In order to make sure these one-to-one fields don't break admin,
        we have to manually exclude them.

        This is an EXACT copy of the original implementation, EXCEPT for the noted lines.
        """
        mapper = model._sa_class_manager.mapper

        # Find property from target model to current model
        # Use the base mapper to support inheritance
        target_mapper = info.model._sa_class_manager.mapper.base_mapper

        reverse_prop = None
        prop: MapperProperty
        for prop in target_mapper.iterate_properties:
            if hasattr(prop, "direction") and prop.direction.name in (
                "MANYTOONE",
                "MANYTOMANY",
            ):
                if issubclass(model, prop.mapper.class_):
                    reverse_prop = prop
                    break
        else:
            raise Exception(f"Cannot find reverse relation for model {info.model}")

        # Find forward property
        forward_prop = None

        if prop.direction.name == "MANYTOONE":
            candidate = "ONETOMANY"
        else:
            candidate = "MANYTOMANY"

        for prop in mapper.iterate_properties:
            # -*- Entering HACK: ignore defined properties (which we assume will break).
            if prop.key in self.exclude_properties:
                continue
            # Exiting HACK -*-
            if hasattr(prop, "direction") and prop.direction.name == candidate:
                if prop.mapper.class_ == target_mapper.class_:
                    forward_prop = prop
                    break
        else:
            raise Exception(f"Cannot find forward relation for model {info.model}")

        return forward_prop.key, reverse_prop.key


class PhaseHistoryForm(InlineFormAdmin):
    form_columns = ("id", "phase", "started_at", "ended_at")

    def __init__(self) -> None:
        super().__init__(CareProgramPhase)


class CareProgramView(MavenAuditedView):
    edit_permission = "edit:care-program"
    read_permission = "read:care-program"

    required_capability = "admin_care_program"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")
    column_filters = ("user_id",)
    column_list = (
        "id",
        "user",
        "current_module_name",
        "current_phase_name",
        "scheduled_end",
        "ended_at",
    )

    form_excluded_columns = (
        "ignore_transitions",
        "first_phase",
        "current_phase",
        "last_phase",
    )

    form_ajax_refs = {
        "user": USER_AJAX_REF,
        "enrollment": {
            "fields": ("id",),
            "page_size": 10,
            "placeholder": "(new enrollment)",
        },
    }

    inline_model_form_converter = PhaseHistoryConverter
    inline_models = (PhaseHistoryForm(),)

    form_widget_args = {
        "granted_extension": {"disabled": True},
        "ended_at": {
            "readonly": True,
            "title": "Please use the terminate action in the list view to end this program.",
        },
    }

    form_args = {"enrollment": {"description": "Clear for new enrollment ^"}}

    def create_model(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.preprocess_form(form)
        return super().create_model(form)

    def update_model(self, form, model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.preprocess_form(form)
        return super().update_model(form, model)

    @action(
        "terminate",
        "Terminate",
        "Are you sure you want to terminate selected care programs?",
    )
    def action_terminate(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if len(ids) != 1:
            flash(
                "Please terminate just one care program at a time...",
                category="warning",
            )
            return
        program = db.session.query(CareProgram).get(ids[0])
        lifecycle.terminate(
            track=program.user.current_member_track,
            modified_by=str(current_user.id or ""),
            change_reason=ChangeReason.ADMIN_PROGRAM_TERMINATE,
        )
        db.session.commit()

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
            CareProgram,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )

    def render(self, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        flash(
            Markup(
                "NOTE: Editing CarePrograms is no longer supported--your changes here "
                "will not affect the user. If you want to make changes to the user's "
                "tracks, check out "
                "<a href='/admin/membertrack/'>the MemberTrack section</a>."
            ),
            "error",
        )

        return super().render(*args, **kwargs)


class PhaseView(MavenAuditedView):
    read_permission = "read:phase"
    delete_permission = "delete:phase"
    create_permission = "create:phase"
    edit_permission = "edit:phase"

    required_capability = "admin_phase"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    column_list = ("id", "module.name", "name", "is_entry", "is_transitional")
    form_columns = (
        "module",
        "name",
        "frontend_name",
        "is_entry",
        "is_transitional",
        "auto_transition_module",
        "onboarding_assessment_lifecycle",
        "created_at",
        "modified_at",
    )
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
            Phase,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
