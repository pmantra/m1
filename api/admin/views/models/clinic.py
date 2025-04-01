import datetime
import re
from typing import List, Type

from flask import flash, redirect, request
from flask_admin.actions import action
from flask_admin.contrib.sqla.fields import QuerySelectMultipleField
from flask_admin.contrib.sqla.filters import FilterInList, FilterLike
from flask_admin.form import BaseForm
from flask_admin.form.fields import Select2Field
from flask_admin.helpers import get_form_data
from flask_admin.model.fields import InlineModelFormField
from sqlalchemy import func
from wtforms.fields import HiddenField, SelectField, StringField
from wtforms.validators import DataRequired, ValidationError

from admin.views.base import (
    AdminCategory,
    AdminViewT,
    AmountDisplayCentsInDollarsField,
    MavenAuditedView,
)
from authn.domain.service.user import UserService
from authn.models.user import User
from authz.services.permission import add_role_to_user
from common.global_procedures import procedure
from common.stats import PodNames, increment
from direct_payment.clinic.models.clinic import (
    FertilityClinic,
    FertilityClinicAllowedDomain,
    FertilityClinicLocation,
    FertilityClinicLocationContact,
)
from direct_payment.clinic.models.fee_schedule import (
    FeeSchedule,
    FeeScheduleGlobalProcedures,
)
from direct_payment.clinic.models.questionnaire_global_procedure import (
    QuestionnaireGlobalProcedure,
)
from direct_payment.clinic.models.user import AccountStatus, FertilityClinicUserProfile
from direct_payment.clinic.services.user import FertilityClinicUserService
from direct_payment.clinic.utils.clinic_helpers import (
    duplicate_fee_schedule,
    get_user_email_domain,
)
from geography import SubdivisionRepository
from storage.connection import db
from storage.connector import RoutingSQLAlchemy
from tasks.braze import send_password_setup
from tasks.marketing import track_user_in_braze
from tasks.users import send_existing_fertility_user_password_reset
from utils.log import logger
from wallet.models.reimbursement_organization_settings import (
    EmployerHealthPlan,
    FertilityClinicLocationEmployerHealthPlanTier,
)

log = logger(__name__)


class FCLFilterByFertilityClinicNetwork(FilterLike):
    """
    Filter the Fertility Clinic Location by the affiliated network.
    Notice that this is akin to a "startswith" query
    """

    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(
            FertilityClinic,
            FertilityClinic.id == FertilityClinicLocation.fertility_clinic_id,
        ).filter(FertilityClinic.affiliated_network.like(f"{value.strip()}%"))


class FCLFilterByFertilityClinicName(FilterLike):
    """
    Filter the Fertility Clinic Location by the Clinic Name.
    Notice that this is akin to a "startswith" query
    """

    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(
            FertilityClinic,
            FertilityClinic.id == FertilityClinicLocation.fertility_clinic_id,
        ).filter(FertilityClinic.name.like(f"{value.strip()}%"))


class FCLCFilterByFertilityClinicNetwork(FilterLike):
    """
    Filter the Fertility Clinic Location Contacts by the affiliated network.
    Notice that this is akin to a "startswith" query
    """

    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            query.join(
                FertilityClinicLocation,
                FertilityClinicLocation.id
                == FertilityClinicLocationContact.fertility_clinic_location_id,
            )
            .join(
                FertilityClinic,
                FertilityClinic.id == FertilityClinicLocation.fertility_clinic_id,
            )
            .filter(FertilityClinic.affiliated_network.like(f"{value.strip()}%"))
        )


class FCLCFilterByFertilityClinicName(FilterLike):
    """
    Filter the Fertility Clinic Location Contacts by the Clinic Name.
    Notice that this is akin to a "startswith" query
    """

    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            query.join(
                FertilityClinicLocation,
                FertilityClinicLocation.id
                == FertilityClinicLocationContact.fertility_clinic_location_id,
            )
            .join(
                FertilityClinic,
                FertilityClinic.id == FertilityClinicLocation.fertility_clinic_id,
            )
            .filter(FertilityClinic.name.like(f"{value.strip()}%"))
        )


class FCLCFilterByFertilityClinicLocationName(FilterLike):
    """
    Filter the Fertility Clinic Location Contacts by the Fertility Clinic Location Name.
    Notice that this is akin to a "startswith" query
    """

    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(
            FertilityClinicLocation,
            FertilityClinicLocation.id
            == FertilityClinicLocationContact.fertility_clinic_location_id,
        ).filter(FertilityClinicLocation.name.like(f"{value.strip()}%"))


class GlobalProcedureSelectField(Select2Field):
    def __init__(self, _form, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.form = _form
        self.allow_blank = False
        self.service = procedure.ProcedureService(internal=True)
        super().__init__(_form=_form, **kwargs)

    def iter_choices(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        valid_global_procedures = self.service.list_all_procedures(
            headers=request.headers  # type: ignore[arg-type] # Argument "headers" to "list_all_procedures" of "ProcedureService" has incompatible type "EnvironHeaders"; expected "Optional[Mapping[str, str]]"
        )
        choices = [("", self.blank_text, self.data is None)]

        # Sort global procedures alphabetically by name
        valid_global_procedures = sorted(
            valid_global_procedures, key=lambda gp: gp["name"]  # type: ignore[typeddict-item] # TypedDict "PartialProcedure" has no key "name"
        )

        choices.extend(
            (str(gp["id"]), gp["name"], gp["id"] == self.data)  # type: ignore[typeddict-item] # TypedDict "PartialProcedure" has no key "id" #type: ignore[typeddict-item] # TypedDict "PartialProcedure" has no key "name"
            for gp in valid_global_procedures
        )

        yield from choices

    def pre_validate(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not self.data:
            raise ValidationError("A Global Procedure is required.")


class FeeScheduleView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    read_permission = "read:fertility-clinic-fee-schedules"
    edit_permission = "edit:fertility-clinic-fee-schedules"
    create_permission = "create:fertility-clinic-fee-schedules"
    delete_permission = "delete:fertility-clinic-fee-schedules"

    create_template = "fee_schedule_edit_template.html"
    edit_template = "fee_schedule_edit_template.html"
    can_view_details = False
    column_list = (
        "name",
        "clinics",
        "created_at",
        "modified_at",
    )
    column_labels = {
        "name": "Fee Schedule",
        "clinics": "Fertility Clinics",
        "created_at": "Created At",
        "modified_at": "Last Updated",
    }
    column_formatters = dict(
        clinics=lambda v, c, m, p: ", ".join(clinic.name for clinic in m.schedules)
    )
    form_columns = ("name",)
    form_excluded_columns = ("deleted_at",)
    column_sortable_list = (
        "created_at",
        "modified_at",
    )
    column_filters = (
        "id",
        "name",
    )
    form_widget_args = {
        "name": {"placeholder": "Enter fee schedule name"},
    }

    def validate_cost(self, field):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not field.data:
            raise ValidationError("Please enter a rate")
        if field.data < 0:
            raise ValidationError("Invalid Rate")
        if field.data > 50000:  # dollars, not cents
            raise ValidationError("Rate exceeds limit of $50,000")

    inline_models = (
        (
            FeeScheduleGlobalProcedures,
            {
                "form_excluded_columns": (
                    "modified_at",
                    "created_at",
                ),
                "form_columns": [
                    "id",
                    "global_procedure_id",
                    "cost",
                ],
                "form_label": "Global Procedure",
                "column_labels": dict(
                    global_procedure_id="Global Procedure",
                    cost="Rate ($)",
                ),
                "form_overrides": {
                    "cost": AmountDisplayCentsInDollarsField,
                    "global_procedure_id": GlobalProcedureSelectField,
                },
                "form_args": dict(cost=dict(validators=[validate_cost])),
                "form_widget_args": {
                    "cost": {
                        "data-cost": "cost",
                    },
                },
            },
        ),
    )

    def get_query(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return FeeSchedule.query.filter_by(deleted_at=None)

    def get_count_query(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # As per Flask admin documentation:
        #
        #   A ``query(self.model).count()`` approach produces an excessive
        #   subquery, so ``query(func.count('*'))`` should be used instead.
        return (
            self.session.query(func.count("*"))
            .select_from(self.model)
            .filter_by(deleted_at=None)
        )

    def delete_model(self, model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # cannot delete if has associated clinics
        associated_clinics = FertilityClinic.query.filter_by(
            fee_schedule_id=model.id
        ).first()
        if associated_clinics:
            flash(
                message="Cannot delete a fee schedule that is associated with active clinics."
                "Please remove the fee schedule from associated clinics first.",
                category="error",
            )
            return False

        self.on_model_delete(model)
        # Soft delete by adding a datestamp to "deleted_at" column
        model.deleted_at = datetime.datetime.now()
        model.name = f"{model.name} DELETED {datetime.datetime.now()}"
        db.session.commit()
        self.after_model_delete(model)
        return True

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
            FeeSchedule,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )

    @action("duplicate", "Duplicate", "Duplicate Fee Schedule and Global Procedures?")
    def duplicate_fee_schedule(self, fee_schedule_ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if len(fee_schedule_ids) > 1:
            flash(
                "Only a single Fee Schedule can be duplicated at a time.",
                category="error",
            )
            return redirect(self.get_url(".index_view"))
        original_fee_schedule = self.get_one(fee_schedule_ids[0])
        flash_messages, success, redirect_id = duplicate_fee_schedule(
            original_fee_schedule
        )
        if flash_messages:
            for flash_message in flash_messages:
                flash(
                    message=flash_message.message,
                    category=flash_message.category.value,
                )
        if success:
            return redirect(self.get_url(".edit_view", id=redirect_id))
        else:
            return redirect(self.get_url(".index_view"))


class QuestionnaireGlobalProcedureView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    create_permission = "create:questionnaire-global-procedures"
    edit_permission = "edit:questionnaire-global-procedures"
    delete_permission = "delete:questionnaire-global-procedures"
    read_permission = "read:questionnaire-global-procedures"

    can_view_details = False
    column_list = (
        "id",
        "questionnaire_id",
        "global_procedure_id",
    )
    column_labels = {
        "id": "ID",
        "questionnaire_id": "Questionnaire",
        "global_procedure_id": "Global Procedure",
    }
    column_sortable_list = (
        "id",
        "questionnaire_id",
        "global_procedure_id",
    )
    form_overrides = {
        "global_procedure_id": GlobalProcedureSelectField,
    }
    column_formatters = dict(questionnaire_id=lambda v, c, m, p: m.questionnaire.oid)

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
            QuestionnaireGlobalProcedure,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


def model_would_have_no_inline_entries(entries: List[InlineModelFormField]):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if len(entries) < 1:
        return True

    return all(entry._should_delete is True for entry in entries)


class FertilityClinicForm(BaseForm):
    def __init__(self, formdata=None, obj=None, prefix="", **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().__init__(formdata, obj, prefix, **kwargs)
        self.fc_user_service = FertilityClinicUserService()

    def validate(self, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        is_valid = super().validate(*args, **kwargs)

        if not (hasattr(self, "locations") and hasattr(self, "allowed_domains")):
            # fields are missing on DeleteForm, which is a local class defined within
            # the parent BaseForm delete_form method
            # extra validation is not required on delete
            return True

        if model_would_have_no_inline_entries(self.locations.entries):
            flash("Fertility Clinics require at least one Location.", category="error")
            is_valid = False

        if model_would_have_no_inline_entries(self.allowed_domains.entries):
            flash(
                "Fertility Clinics require at least one Allowed Domain.",
                category="error",
            )
            is_valid = False

        for domain in self.allowed_domains:
            if domain._should_delete:
                active_users_on_domain = (
                    self.fc_user_service.get_active_user_ids_on_allowed_domain(
                        domain.object_data
                    )
                )
                if len(active_users_on_domain) > 0:
                    flash(
                        f'Cannot delete Allowed Domain "{domain.object_data.domain}" due to active user(s) {active_users_on_domain}',
                        category="error",
                    )
                    is_valid = False

        return is_valid


class UnitedStatesSubdivisionSelect(Select2Field):
    def __init__(self, _form, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.form = _form
        self.allow_blank = False
        super().__init__(_form=_form, **kwargs)

    def iter_choices(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if not self.form.country_code:
            return "", self.blank_text, self.data is None

        subdivision_repository = SubdivisionRepository()
        subdivisions = subdivision_repository.get_subdivisions_by_country_code(
            country_code="US"
        )
        if subdivisions is None:
            return "", self.blank_text, self.data is None

        for sd in subdivisions:
            yield str(sd.code), sd.name, str(sd.code) == self.data

    def pre_validate(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not self.data:
            raise ValueError("A Subdivision Code is required.")


class FertilityClinicView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    read_permission = "read:fertility-clinic"
    edit_permission = "edit:fertility-clinic"
    create_permission = "create:fertility-clinic"
    delete_permission = "delete:fertility-clinic"

    form_base_class = FertilityClinicForm
    can_view_details = True
    column_list = (
        "name",
        "locations",
        "created_at",
        "modified_at",
        "self_pay_discount_rate",
    )

    column_labels = {
        "name": "Clinic Name",
        "locations": "Locations",
        "created_at": "Created At",
        "modified_at": "Last Updated",
        "self_pay_discount_rate": "Self-Pay Discount Rate (%)",
    }

    column_formatters = dict(
        locations=lambda v, c, m, p: ", ".join(loc.name for loc in m.locations)
    )
    column_filters = ("name", "locations.name")

    form_excluded_columns = (
        "id",
        "uuid",
        "created_at",
        "modified_at",
        "fee_schedule_id",
    )

    inline_models = (
        (
            FertilityClinicLocation,
            {
                "form_excluded_columns": (
                    "uuid",
                    "created_at",
                    "modified_at",
                    "fertility_clinic_id",
                ),
                "form_overrides": {
                    "subdivision_code": UnitedStatesSubdivisionSelect,
                },
                "form_widget_args": {
                    "country_code": {"disabled": True, "value": "US"},
                },
                "column_labels": {
                    "subdivision_code": "State",
                    "country_code": "Country",
                },
            },
        ),
        (
            FertilityClinicAllowedDomain,
            {
                "form_excluded_columns": (
                    "uuid",
                    "created_at",
                    "modified_at",
                    "fertility_clinic_id",
                ),
                "column_labels": {
                    "domain": "Allowed Email Domains (part after @)",
                },
            },
        ),
    )

    def create_form(self, obj=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        form = super().create_form(obj)
        # Hide deleted Fee Schedules
        form.fee_schedule.query = self.session.query(FeeSchedule).filter(
            FeeSchedule.deleted_at == None
        )
        return form

    def edit_form(self, obj=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        form = super().edit_form(obj)
        # Hide deleted Fee Schedules
        form.fee_schedule.query = self.session.query(FeeSchedule).filter(
            FeeSchedule.deleted_at == None
        )
        return form

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
            FertilityClinic,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class FertilityClinicLocationView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    create_permission = "create:fertility-clinic-location"
    edit_permission = "edit:fertility-clinic-location"
    delete_permission = "delete:fertility-clinic-location"
    read_permission = "read:fertility-clinic-location"

    can_view_details = True

    column_list = (
        "id",
        "fertility_clinic.name",
        "fertility_clinic.affiliated_network",
        "fertility_clinic_id",
        "name",
        "address_1",
        "address_2",
        "city",
        "tin",
        "npi",
        "subdivision_code",
        "postal_code",
        "country_code",
        "phone_number",
        "email",
    )

    column_labels = {
        "fertility_clinic.name": "Clinic Name",
        "fertility_clinic.affiliated_network": "Affiliated Network",
        "tin": "TIN",
        "npi": "NPI",
    }

    column_filters = (
        "id",
        "uuid",
        "fertility_clinic_id",
        "name",
        "address_1",
        "city",
        "phone_number",
        "tin",
        "npi",
        FCLFilterByFertilityClinicName(None, "Fertility Clinic name starts with"),
        FCLFilterByFertilityClinicNetwork(
            None, "Fertility Clinic affiliated network starts with"
        ),
    )

    inline_models = (
        (
            FertilityClinicLocationContact,
            {
                "form_excluded_columns": ("modified_at",),
            },
        ),
    )

    form_widget_args = {
        "tin": {"placeholder": "xxx-xx-xxxx"},
    }

    @staticmethod
    def _is_valid_tin(tin: str) -> bool:
        us_tin_pattern = r"^\d{3}-\d{2}-\d{4}$"
        return bool(re.match(us_tin_pattern, tin))

    @staticmethod
    def _is_valid_npi(npi: str) -> bool:
        us_npi_pattern = r"^\d{10}$"
        return bool(re.match(us_npi_pattern, npi))

    # Validate form before saving the data
    def validate_form(self, form) -> bool:  # type: ignore[no-untyped-def] # Function is missing a type annotation
        errors = []

        # If other fields require validation in the future,
        # add additional validation checks and corresponding error messages here
        validations = [
            (
                self._is_valid_tin,
                form.tin.data.strip() if form.tin.data else None,
                "TIN must be in the format xxx-xx-xxxx, e.g., 123-45-6789",
            ),
            (
                self._is_valid_npi,
                form.npi.data.strip() if form.npi.data else None,
                "NPI must be a 10-digit number, e.g., 1234567890",
            ),
        ]

        for validation_func, input_data, error_message in validations:
            if input_data is not None and not validation_func(input_data):
                errors.append(error_message)

        if errors:
            flash(errors[0], "error")
            return False

        return super().validate_form(form)

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
            FertilityClinicLocation,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class FertilityClinicLocationContactView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    create_permission = "create:fertility-clinic-location-contact"
    edit_permission = "edit:fertility-clinic-location-contact"
    delete_permission = "delete:fertility-clinic-location-contact"
    read_permission = "read:fertility-clinic-location-contact"

    can_view_details = True

    column_list = (
        "id",
        "uuid",
        "fertility_clinic_location_id",
        "name",
        "phone_number",
        "email",
        "created_at",
        "modified_at",
        "location.address1",
    )

    column_filters = (
        "id",
        "uuid",
        "fertility_clinic_location_id",
        FCLCFilterByFertilityClinicName(None, "Clinic Name"),
        FCLCFilterByFertilityClinicNetwork(None, "Affiliated Network Name"),
        FCLCFilterByFertilityClinicLocationName(None, "Fertility Clinic Location Name"),
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
            FertilityClinicLocationContact,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class FertilityClinicLocationEmployerHealthPlanTierView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    create_permission = "create:fertility-clinic-location-employer-health-plan-tier"
    edit_permission = "edit:fertility-clinic-location-employer-health-plan-tier"
    delete_permission = "delete:fertility-clinic-location-employer-health-plan-tier"
    read_permission = "read:fertility-clinic-location-employer-health-plan-tier"

    can_view_details = True

    column_list = (
        "id",
        "fertility_clinic_location",
        "employer_health_plan",
        "start_date",
        "end_date",
    )

    column_filters = (
        "id",
        FertilityClinicLocation.id,
        EmployerHealthPlan.id,
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
            FertilityClinicLocationEmployerHealthPlanTier,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class EmailInClinicAllowedDomains:
    """
    Custom validator for ensuring that email domains for FertilityClinic users are in the allowed_domain list for the FertilityClinic.
    """

    def __call__(self, form, field):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """
        FertilityClinics specify a set of allowed domains to which user email addresses must belong.
        """
        # Get the domain for the email
        domain = get_user_email_domain(field.data)
        clinic_ids = [c.id for c in form.clinics.data]
        # The domain must be an allowed domain for ALL selected clinics
        matching_domains = (
            db.session.query(FertilityClinicAllowedDomain.fertility_clinic_id)
            .filter(
                FertilityClinicAllowedDomain.domain == domain,
                FertilityClinicAllowedDomain.fertility_clinic_id.in_(clinic_ids),
            )
            .all()
        )
        count = len(matching_domains)
        if count == 0 or count != len(clinic_ids):
            unmatched_clinic_ids = set(clinic_ids) - {
                fcad.fertility_clinic_id for fcad in matching_domains
            }
            unmatched_clinics = (
                db.session.query(FertilityClinic.name)
                .filter(FertilityClinic.id.in_(unmatched_clinic_ids))
                .all()
            )
            log.info(
                "EmailInClinicAllowedDomains validation failed",
                domain=domain,
                clinic_ids=clinic_ids,
                count=count,
                unmatched_clinic_ids=unmatched_clinic_ids,
            )
            raise ValidationError(
                f"The email domain '{domain}' does not match the allowed domains for selected clinic(s): "
                + (", ".join(fc.name for fc in unmatched_clinics))
            )


class FertilityClinicUserProfileForm(BaseForm):
    """
    Form used to populate the FertilityClinicUserProfile object using the built-in fancy copy magic.
    """

    clinics = QuerySelectMultipleField(
        validators=[DataRequired()],
        query_factory=lambda: FertilityClinic.query,
        get_label=lambda x: x.name,
    )
    first_name = StringField(
        label="First Name",
        validators=[DataRequired()],
    )
    last_name = StringField(
        label="Last Name",
        validators=[DataRequired()],
    )
    user_id = HiddenField()
    status = SelectField(
        validators=[DataRequired()], choices=[(s.value, s.name) for s in AccountStatus]
    )


class FertilityClinicUserForm(FertilityClinicUserProfileForm):
    """
    Form that captures fields that are related to the User created and not the profile.

    To collect all of this data in one form, this class is the form class used by the view.
    """

    email = StringField(
        label="Email",
        validators=[DataRequired(), EmailInClinicAllowedDomains()],
    )
    role = SelectField(
        label="Role",
        choices=[
            ("fertility_clinic_user", "Standard User"),
            ("fertility_clinic_billing_user", "Billing User"),
        ],
        validators=[DataRequired()],
    )


class FilterByClinic(FilterInList):
    """
    Custom filter to filter by FertilityClinic with its many-to-many relationship to FertilityClinicUserProfile
    """

    # Override to create an appropriate query and apply a filter to said query with the passed value from the filter UI
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(FertilityClinicUserProfile.clinics).filter(
            FertilityClinic.id.in_(value)
        )

    # Override to provide the options for the filter - in this case it's a list of the names of the FertilityClinic model
    def get_options(self, view):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return [
            (fc.id, fc.name)
            for fc in FertilityClinic.query.order_by(FertilityClinic.name)
        ]


class FilterByEmail(FilterLike):
    """
    Email is on the User entity to which FertilityClinicUserProfile has no FK link. This method of filtering will support User being moved to another service.
    """

    # Override to create an appropriate query and apply a filter to said query with the passed value from the filter UI
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user_service = UserService()
        users = user_service.fetch_users(filters={"email_like": f"%{value}%"})
        return query.filter(
            FertilityClinicUserProfile.user_id.in_([u.id for u in users])
        )


class FertilityClinicUserProfileView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    read_permission = "read:fertility-clinic-users"
    edit_permission = "edit:fertility-clinic-users"
    create_permission = "create:fertility-clinic-users"

    form = FertilityClinicUserForm
    column_list = (
        "full_name",
        "email",
        "clinics",
        "status",
        "role",
        "created_at",
    )
    column_sortable_list = (
        "created_at",
        "full_name",
        ("clinics", "clinics.name"),
    )
    column_searchable_list = (
        "first_name",
        "last_name",
    )
    column_filters = (
        "id",
        "first_name",
        "last_name",
        FilterByEmail(column=None, name="Email"),
        FilterByClinic(column=None, name="Fertility Clinic"),
    )
    column_formatters = {
        "clinics": lambda v, c, m, p: [clinic.name for clinic in m.clinics],
    }
    form_excluded_columns = ("created_at", "updated_at", "user_id", "uuid")

    def create_model(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            trimmed_email = form.email.data.strip()
            trimmed_first_name = form.first_name.data.strip()
            trimmed_last_name = form.last_name.data.strip()

            # Check for duplicate entries in the user table
            found_user = UserService().get_by_email(email=trimmed_email)
            if found_user:
                raise ValueError("A user with this email already exists")

            new_user = UserService().create_user(
                email=trimmed_email, role_name=form.role.data, is_active=True
            )

            # new instance of the FertilityClinicUserProfileForm so we can use the auto population in create_model
            f = FertilityClinicUserProfileForm(formdata=get_form_data())
            f.first_name.data = trimmed_first_name
            f.last_name.data = trimmed_last_name
            f.user_id.data = new_user.id

            send_password_setup.delay(new_user.id)
            return super().create_model(f)
        except Exception as e:
            flash(str(e), "error")
            return

    def update_model(self, form, model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            found_user = None
            trimmed_new_email = form.email.data.strip()

            if model.email != trimmed_new_email:
                found_user = UserService().get_by_email(email=trimmed_new_email)

            if found_user:
                raise ValueError("A user with this email already exists")

            with db.session.no_autoflush:
                UserService().update_user(
                    user_id=form.user_id.data,
                    email=trimmed_new_email,
                )
                # Have to get the 'old' User type for using the 'old' Role mapping
                user = User.query.get(form.user_id.data)
                add_role_to_user(user, form.role.data)
                db.session.add(user)
            self.session.flush()
            self.session.commit()

            # new instance of the FertilityClinicUserProfileForm so we can use the auto population in update_model
            f = FertilityClinicUserProfileForm(formdata=get_form_data())
            return super().update_model(f, model)
        except Exception as e:
            flash(str(e), "error")
            return

    @action(
        "deactivate_users",
        "Deactivate Users",
        "Are you sure you want to deactivate the selected user(s)?",
    )
    def deactivate_users(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._update_status_for_users(ids, AccountStatus.INACTIVE)

    @action(
        "activate_users",
        "Activate Users",
        "Are you sure you want to activate the selected user(s)?",
    )
    def activate_users(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._update_status_for_users(ids, AccountStatus.ACTIVE)

    def _update_status_for_users(self, ids, status):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        db.session.bulk_update_mappings(
            FertilityClinicUserProfile,
            [{"id": id, "status": status} for id in ids],
        )
        db.session.commit()
        log.info(f"User(s) {ids} status changes to {status}")

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_model_change(form, model, is_created)
        track_user_in_braze.delay(model.user.id, caller=self.__class__.__name__)

    @action(
        "send_password_reset_email",
        "Send Password Reset Email",
    )
    def send_password_reset_email(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        for id in ids:
            fc_user_profile = self.model.query.get(id)
            user = fc_user_profile.user

            if user:
                log.info("Sending password reset E-Mail")
                send_existing_fertility_user_password_reset.delay(user.id)

            increment(
                metric_name="api.admin.views.fertility_clinic_user_profile.password_reset",
                pod_name=PodNames.MPRACTICE_CORE,
            )

            flash(
                f"Reset password for fertility clinic user profile id {id} sent",
                "success",
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
            FertilityClinicUserProfile,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
