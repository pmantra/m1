from __future__ import annotations

import datetime
import json
from typing import Optional, Type

import phonenumbers
from flask import Response, flash, request
from flask_admin import expose
from flask_admin.actions import action
from flask_admin.contrib.sqla.ajax import QueryAjaxModelLoader
from flask_admin.contrib.sqla.fields import (
    InlineModelFormList,
    QuerySelectField,
    get_field_id,
)
from flask_admin.contrib.sqla.filters import FilterEqual, FilterLike, FilterNotEqual
from flask_admin.contrib.sqla.form import InlineModelConverter
from flask_admin.form import DatePickerWidget, Select2Field
from flask_admin.form import fields as fa_fields
from flask_admin.form import rules
from flask_admin.model import InlineFormAdmin
from flask_admin.model.helpers import get_mdict_item_or_list
from markupsafe import Markup
from maven import feature_flags
from sqlalchemy import or_
from wtforms import BooleanField, IntegerField, SelectField, fields, validators

from admin.common import Select2MultipleField, slug_re_check
from admin.views.base import (
    USER_AJAX_REF,
    AdminCategory,
    AdminViewT,
    BaseDateTextFilter,
    ContainsFilter,
    FormToJSONField,
    IsFilter,
    MavenAuditedView,
    ReadOnlyFieldRule,
)
from admin.views.models.images import ImageUploadField
from audit_log.utils import emit_bulk_audit_log_read, emit_bulk_audit_log_update
from authn.domain.model import OrganizationAuth
from authn.domain.repository import OrganizationAuthRepository
from authn.models.user import User
from authn.util.constants import (
    COMPANY_MFA_SYNC_LAUNCH_DARKLY_CONTEXT_NAME,
    COMPANY_MFA_SYNC_LAUNCH_DARKLY_KEY,
)
from eligibility import OrganizationRepository
from geography.repository import CountryRepository
from health.data_models.risk_flag import RiskFlag
from incentives.models.incentive import (
    Incentive,
    IncentiveAction,
    IncentiveOrganization,
    IncentiveOrganizationCountry,
    IncentiveType,
)
from incentives.models.incentive_fulfillment import (
    IncentiveFulfillment,
    IncentiveStatus,
)
from incentives.services.incentive_organization import (
    IncentiveOrganizationService,
    IncentiveStatusEarnedProcessingDateEarnedRequiredException,
    IncentiveStatusFulfilledDateEarnedDateIssuedRequiredException,
    IncentiveStatusFulfilledDateIssuedRequiredException,
    IncentiveStatusSeenDateEarnedNotEmptyException,
    IncentiveStatusSeenEarnedProcessingDateIssuedNotEmptyException,
    InvalidIncentiveFulfillmentException,
    InvalidIncentiveOrganizationException,
    update_braze_incentive_offboarding_for_org_users,
    update_braze_incentive_when_org_changes_in_admin,
)
from models.enterprise import (
    DEFAULT_ORG_FIELD_MAP,
    EXTERNAL_IDENTIFIER_FIELD_MAP,
    HEALTH_PLAN_FIELD_MAP,
    USER_FLAG_INFO_TYPE_MULTI_SELECTION,
    USER_FLAG_INFO_TYPE_OBESITY_CALC,
    Assessment,
    AssessmentLifecycle,
    AssessmentLifecycleTrack,
    BusinessLead,
    InboundPhoneNumber,
    Invite,
    InviteType,
    NeedsAssessment,
    NeedsAssessmentTypes,
    Organization,
    OrganizationEligibilityField,
    OrganizationEmailDomain,
    OrganizationEmployee,
    OrganizationExternalID,
    OrganizationModuleExtension,
    UserOrganizationEmployee,
    org_inbound_phone_number,
)
from models.programs import Module
from models.tracks import MemberTrack, TrackName, get_track
from models.tracks.assessment import AssessmentTrack
from models.tracks.client_track import ClientTrack, TrackModifiers
from storage.connection import RoutingSQLAlchemy, db
from tasks.enterprise import update_organization_all_users_company_mfa
from utils import braze
from utils.cache import RedisLock
from utils.log import logger
from utils.org_search_autocomplete import OrganizationSearchAutocomplete
from utils.service_owner_mapper import service_ns_team_mapper

log = logger(__name__)


def summarize_client_tracks(organization):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Build a basic summary list of client tracks that specifically calls out tracks with
    a configurable length. Also, each client track links to its corresponding inline
    form.
    """
    if not organization:
        return ""
    client_track_links = []
    for i, ct in enumerate(organization.client_tracks):
        if not ct.active:
            continue
        name = ct.track
        lengths = ct._config.length_in_days_options
        if len(lengths) > 1 or ct.length_in_days not in lengths.values():
            selected_length = next(
                (name for name, days in lengths.items() if days == ct.length_in_days),
                "Custom",
            )
            name += f": <b>{selected_length}</b>"

        # The ID name "client_tracks-X" is built into flask admin -- let's link to it
        client_track_links.append(
            f'<a style="color: inherit" href="#client_tracks-{i}">{name}</a>'
        )
    list_items = [f"<li>{link}</li>" for link in client_track_links]
    return Markup(f"<ol>{''.join(list_items)}</ol>")


class ClientTrackLengthSelectField(Select2Field):
    """
    This is a big hack to allow admins to seamlessly edit client track lengths.
    We want client track lengths options to change depending on which track is selected.
    The actual filtering is achieved in javascript, but we need to build options for all
    client track/length combos.

    We also want to allow old, no-longer-supported lengths to still work, and not be
    overwritten or validated on save.

    See also: organization_edit.html for the jQuery code involved in making this work.
    """

    def __init__(self, _form, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.form = _form
        super().__init__(_form=_form, **kwargs)

    def iter_choices(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # Include ALL options, they are filtered using jquery
        # The track name is prepended to each option:
        #   [pregnancy] Default (294 Days)
        # (see organization_edit.html for filtering logic)
        all_valid_choices = []
        for track in TrackName:
            for name, days in get_track(track).length_in_days_options.items():
                # Example: (because 15-month maternity includes a 6-month postpartum)
                # track = postpartum, name = "15-Month Maternity", days = 168
                all_valid_choices.append(str(days))
                yield (
                    str(days),
                    f"[{get_track(track).name}] {name} ({days} days)",
                    str(days) == self.data,
                )

        if self.form.track.data:
            selected_track = get_track(self.form.track.data)
            if int(self.data) not in selected_track.length_in_days_options.values():
                # We have a custom value, let's add it as an option too so that the value
                # isn't overwritten on save
                yield (
                    str(self.data),
                    f"[{selected_track.name}] Custom ({self.data} days)",
                    True,
                )

    def pre_validate(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # The main reason this method is overwritten is so that values OUTSIDE of
        # self.choices are valid inputs -- we want to allow the occasional client track
        # to have a value that is not in the set list of options
        if not self.data:
            raise ValueError("Client track length is required")


class DataProviderOrgIDQueryAjaxModelLoader(QueryAjaxModelLoader):
    """Generate a query to return organizations that have been configured to be data providers for other orgs"""

    additional_filters = []

    def get_list(self, term, offset=0, limit=10):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        filters = self.additional_filters
        return db.session.query(self.model.id, self.model.name).filter(*filters).all()

    def __init__(self, name, session, model, **options):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().__init__(name, session, model, **options)
        self.additional_filters = options.get("filters", [])


class OrganizationInlineModelFormList(InlineModelFormList):
    def validate(self, form, extra_validators=()):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        undeletable_tracks = []
        for track_field in self.entries:
            if self.model is ClientTrack and self.should_delete(track_field):
                field_id = get_field_id(track_field)
                try:
                    result = self.session.query(self.model).get(field_id)
                    if result and result.member_tracks:
                        # has non-empty member_tracks relationship, can't delete
                        undeletable_tracks.append(result.track)
                except Exception as e:
                    message = "Unknown error occurred while validating"
                    log.error(message, e)
                    flash(message, category="error")
                    return False

        if undeletable_tracks:
            message = "client_tracks={} cannot be deleted due to existing member_track(s)".format(
                undeletable_tracks
            )
            flash(message, category="error")
            return False

        return super().validate(form, extra_validators)


class OrganizationInlineModelConverter(InlineModelConverter):
    inline_field_list_type = OrganizationInlineModelFormList


DISALLOWED_CLIENT_TRACKS = (TrackName.PARTNER_FERTILITY, TrackName.TRYING_TO_CONCEIVE)


class OrganizationView(MavenAuditedView):
    create_permission = "create:organization"
    read_permission = "read:organization"
    edit_permission = "edit:organization"

    can_view_details = True

    edit_template = "organization_edit.html"
    create_template = "organization_edit.html"

    column_list = (
        "id",
        "name",
        "directory_name",
        "alegeus_employer_id",
        "is_active",
        "data_provider",
        "created_at",
        "modified_at",
        "capture_page_type",
    )
    column_sortable_list = ("name", "directory_name")
    column_searchable_list = ("id", "name", "directory_name", "alegeus_employer_id")

    form_args = {"vertical_group_version": {"default": "Enterprise"}}

    form_extra_fields = {
        "mfa_required": BooleanField("mfa_required"),
        "bms_enabled": BooleanField("bms_enabled"),
        "session_ttl": IntegerField("Session Timeout (minutes)", default=10080),
        "data_provider": SelectField(
            description="Organization may provide mappings between external and internal org IDs",
            choices=[(0, "False"), (1, "True")],
        ),
        "capture_page_type": SelectField(
            description="Capture page has form or not",
            choices=[("NO_FORM", "No Form"), ("FORM", "Form")],
        ),
    }

    required_capability = "admin_organization"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    form_rules = (
        "name",
        "display_name",
        "internal_summary",
        "internal_type",
        "eligibility_type",
        "icon",
        "activated_at",
        "terminated_at",
        "session_ttl",
        "data_provider",
        "capture_page_type",
        "benefits_url",
        rules.FieldSet(("org_folder_link", "org_script_link"), "Care"),
        rules.FieldSet(
            (
                "bms_enabled",
                "vertical_group_version",
                "message_price",
                "rx_enabled",
                "education_only",
                "US_restricted",
                ReadOnlyFieldRule(
                    "Multitrack Enabled",
                    lambda model: model.multitrack_enabled if model else "",
                ),
            ),
            "Services",
        ),
        rules.FieldSet(
            ("mfa_required",),
            "MFA Settings",
        ),
        rules.FieldSet(
            (ReadOnlyFieldRule("Summary", summarize_client_tracks), "client_tracks"),
            "Client Tracks",
        ),
        rules.FieldSet(
            (
                "directory_name",
                "medical_plan_only",
                "employee_only",
                "alternate_verification",
                "disassociate_users",
                "org_employee_primary_key",
                "field_map",
                "optional_field_map_affiliations",
                "health_plan_field_map_affiliations",
            ),
            "Verification",
        ),
        rules.FieldSet(("external_ids",), "External Identifier Mappings"),
        rules.FieldSet(
            (
                "gift_card_allowed",
                "welcome_box_allowed",
            ),
            "Incentive Configuration",
        ),
    )

    form_ajax_refs = {
        "data_provider_organization": DataProviderOrgIDQueryAjaxModelLoader(
            "data_provider_organization",
            db.session,
            Organization,
            fields=["name"],
            filters=[Organization.data_provider == 1],
        )
    }

    inline_models = (
        InlineFormAdmin(
            OrganizationExternalID,
            form_excluded_columns=(
                "modified_at",
                "created_at",
                "reward_exports",
                "external_id",
            ),
            form_ajax_refs=form_ajax_refs,
            form_extra_fields={
                "primary_external_id": fields.StringField(
                    description="How a data provider or IDP uniquely refers to this org.",
                    validators=[validators.DataRequired()],
                ),
                "secondary_external_id": fields.StringField(
                    description="OPTIONAL: Secondary value used to identify an organization"
                ),
            },
            column_descriptions={
                "data_provider_organization": "ID/Name for the Org Supplying the External Mapping",
            },
        ),
        InlineFormAdmin(
            ClientTrack,
            column_descriptions={
                "active": """Whether the track is active or will be soon. Uncheck to 'deactivate" track.""",
                "launch_date": """Date on which to make this track available to users. Should generally be in the future.""",
                "track_modifiers": """Additional track modifiers""",
            },
            form_columns=(
                "id",
                "track",
                "length_in_days",
                "active",
                "launch_date",
                "track_modifiers",
            ),
            form_choices={
                "track": [(track.value, track.value) for track in TrackName],
                "track_modifiers": [
                    (modifier.value, modifier.value) for modifier in TrackModifiers
                ],
            },
            form_overrides={"length_in_days": ClientTrackLengthSelectField},
        ),
    )

    inline_model_form_converter = OrganizationInlineModelConverter

    column_details_list = [
        "id",
        "name",
        "alegeus_employer_id",
        "display_name",
        "employee_count",
        "bms_enabled",
        "multitrack_enabled",
        "internal_summary",
        "vertical_group_version",
        "message_price",
        "activated_at",
        "terminated_at",
        "is_active",
        "rx_enabled",
        "US_restricted",
        "education_only",
        "last_file_upload",
        "org_employee_primary_key",
        "data_provider",
        "capture_page_type",
        "benefits_url",
    ]

    def on_form_prefill(self, form, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_form_prefill(form, id)
        org = self.model.query.get(id)

        if org:
            already_active = terminated = None
            if org.activated_at:
                already_active = org.activated_at <= datetime.datetime.utcnow()
            form.activated_at.description = {
                None: "(Not Activated)",
                True: "(Activated)",
                False: "(To Be Activated)",
            }[already_active]

            if org.terminated_at:
                terminated = org.terminated_at <= datetime.datetime.utcnow()
            form.terminated_at.description = {
                None: "(Not Terminated)",
                True: "(Terminated)",
                False: "(To Be Terminated)",
            }[terminated]

            # MFA requirements for the organization
            oar = OrganizationAuthRepository()
            if org_auth := oar.get_by_organization_id(organization_id=id):
                form.mfa_required.data = org_auth.mfa_required

            # Split our externalID from the DB in to primary and secondary values to be displayed in our UI
            for model_form in form.external_ids.entries:
                external_id = model_form.object_data.external_id
                external_id_components = external_id.split(":")
                model_form.form.primary_external_id.data = external_id_components[0]
                if len(external_id_components) > 1:
                    model_form.form.secondary_external_id.data = external_id_components[
                        1
                    ]

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation

        disallowed_tracks = []

        for client_track in model.client_tracks:
            if client_track.track in DISALLOWED_CLIENT_TRACKS and client_track.active:
                disallowed_tracks.append(client_track.track)

        if disallowed_tracks:
            raise validators.ValidationError(
                "Unsupported Client Tracks: {} cannot be activated as they are deprecated. Deactivate or delete these Client Tracks to save changes to this Organization".format(
                    disallowed_tracks
                )
            )

        # Combine the form values for our primary/secondary externalID to the concatted value we actually want to store in our DB
        for ext_id in model.external_ids:
            # If values are populated, sanitize them by removing spaces
            # If we are deleting an external ID, these may not be populated and we would hit an attribute error
            try:
                ext_id.external_id = ext_id.primary_external_id.strip()
                # don't save empty string
                if not ext_id.external_id:
                    ext_id.external_id = None
            except AttributeError:
                ext_id.external_id = None
                continue

            try:
                ext_id.secondary_external_id = ext_id.secondary_external_id.strip()
                if ext_id.secondary_external_id:
                    ext_id.external_id = ":".join(
                        [ext_id.external_id, ext_id.secondary_external_id.strip()]
                    )
            except AttributeError:
                continue

        # If the organization's incentive gift card field was not previously true and NOW it's set to true,
        # OR if the organization is new and gift card field is set to true,
        # Automatically attempt to create incentive organization rows that correspond with the gift card incentive.
        # These incentive organization rows determine which incentive a member should receive depending on their organization's incentive configuration
        has_enabled_gift_card_on_existing_org = (
            not is_created
            and not form.gift_card_allowed.object_data  # original gift_card_allowed value
            and form.gift_card_allowed.data  # new gift_card_allowed_value
        )
        has_enabled_gift_card_on_new_org = is_created and form.gift_card_allowed.data
        if has_enabled_gift_card_on_existing_org or has_enabled_gift_card_on_new_org:
            (
                incentive_orgs_added,
                incentive_orgs_not_added,
            ) = IncentiveOrganizationService().create_incentive_organizations_on_organization_change(
                model
            )

            # Tell the user which rows were successfully created, and which were not
            flash(
                "Enabling incentive gift cards triggered attempt to automatically create incentive organizations:",
                category="info",
            )
            if len(incentive_orgs_added) > 0:
                message = "Successfully created incentive organization(s) for " + ", ".join(
                    [
                        f"incentive action: '{incentive_org.get('incentivized_action').value}' in track '{incentive_org.get('track')}'"
                        for incentive_org in incentive_orgs_added
                    ]
                )
                flash(message, category="success")
            if len(incentive_orgs_not_added) > 0:
                for incentive_org in incentive_orgs_not_added:
                    flash(
                        f"Error creating incentive organization for {incentive_org.get('incentivized_action').value} in track {incentive_org.get('track')} due to a duplicate incentive organization",
                        category="error",
                    )

        # if values related to incentives are changed,
        # find all active users associated with the organization and update their incentive configs in Braze
        has_welcome_box_incentive_changed = (
            form.welcome_box_allowed.object_data != form.welcome_box_allowed.data
        )
        has_gift_card_incentive_changed = (
            form.gift_card_allowed.object_data != form.gift_card_allowed.data
        )

        if (
            has_welcome_box_incentive_changed or has_gift_card_incentive_changed
        ) and form._obj:
            service_ns = "incentive"
            update_braze_incentive_when_org_changes_in_admin.delay(
                form._obj.id,
                form.welcome_box_allowed.data,
                form.gift_card_allowed.data,
                service_ns=service_ns,
                team_ns=service_ns_team_mapper.get(service_ns),
            )

        # if we are going from having a gift cards allowed or welcome boxes allowed TRUE, and are now changing the
        # value to FALSE, automatically set any incentive-organization rows with that incentive to "inactive"
        has_disabled_gift_card = (
            not is_created
            and form.gift_card_allowed.object_data  # original gift_card_allowed value
            and not form.gift_card_allowed.data  # new gift_card_allowed value
        )
        has_disabled_welcome_box = (
            not is_created
            and form.welcome_box_allowed.object_data  # original welcome_box_allowed value
            and not form.welcome_box_allowed.data  # new welcome_box_allowed value
        )
        incentive_type = None
        if has_disabled_gift_card and has_disabled_welcome_box:
            incentive_type = "ALL"
        elif has_disabled_gift_card:
            incentive_type = IncentiveType.GIFT_CARD  # type: ignore[assignment] # Incompatible types in assignment (expression has type "IncentiveType", variable has type "Optional[str]")
        elif has_disabled_welcome_box:
            incentive_type = IncentiveType.WELCOME_BOX  # type: ignore[assignment] # Incompatible types in assignment (expression has type "IncentiveType", variable has type "Optional[str]")
        if incentive_type:
            flash(
                f"Disabling {'all' if incentive_type == 'ALL' else incentive_type.name} incentives triggered the process to inactivate Incentive-Organization rows.",  # type: ignore[attr-defined] # "str" has no attribute "name"
                category="info",
            )
            incentive_orgs_disabled = IncentiveOrganizationService().inactivate_incentive_orgs_on_incentive_change(
                organization=model, incentive_type=incentive_type
            )
            if not incentive_orgs_disabled:
                flash(
                    f"No Incentive-Organization records were found for this organization with incentive type {'all' if incentive_type == 'ALL' else incentive_type.name}",  # type: ignore[attr-defined] # "str" has no attribute "name"
                    category="info",
                )
            else:
                message = (
                    "Successfully disabled Incentive-Organization row(s) for "
                    + ", ".join(
                        [
                            f"incentive action: '{incentive_org.action.value}' in track '{incentive_org.track_name}'"
                            for incentive_org in incentive_orgs_disabled
                        ]
                    )
                )
                flash(message, category="success")

        if form.mfa_required is not None:
            oar = OrganizationAuthRepository()
            if oar.get_by_organization_id(organization_id=model.id):
                oar.update_by_organization_id(
                    organization_id=model.id, new_mfa_required=model.mfa_required
                )
            else:
                org_auth = OrganizationAuth(
                    organization_id=model.id, mfa_required=model.mfa_required
                )
                oar.create(instance=org_auth)
            is_company_mfa_lts = feature_flags.bool_variation(
                COMPANY_MFA_SYNC_LAUNCH_DARKLY_KEY,
                feature_flags.Context.create(
                    COMPANY_MFA_SYNC_LAUNCH_DARKLY_CONTEXT_NAME
                ),
                default=False,
            )
            if is_company_mfa_lts:
                log.info("Initiating the company mfa sync job")
                # trigger the job to sync the company mfa data.
                update_organization_all_users_company_mfa(
                    org_id=model.id, mfa_required=model.mfa_required
                )

        super().on_model_change(form, model, is_created)
        search = OrganizationSearchAutocomplete()
        search.reload_orgs()

    def create_form(self, obj=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        form = super().create_form(obj=obj)

        # If we are not trying to save the form we just filled out, prepopulate some values
        if not self.validate_form(form):
            skip_tracks = {
                TrackName.BREAST_MILK_SHIPPING,
                TrackName.GENERAL_WELLNESS,
                TrackName.SPONSORED,
            }
            special_length_in_days_tracks = {
                TrackName.PARTNER_NEWPARENT,
                TrackName.POSTPARTUM,
            }
            special_length_in_days = "21-Month Maternity"

            for track_name in TrackName:
                if track_name in skip_tracks or track_name in DISALLOWED_CLIENT_TRACKS:
                    continue
                length_in_days_options = get_track(track_name).length_in_days_options
                new_client_track = None
                if track_name in special_length_in_days_tracks:
                    new_client_track = ClientTrack(
                        id="",
                        track=track_name,
                        length_in_days=length_in_days_options[special_length_in_days],
                        active=True,
                    )
                else:
                    new_client_track = ClientTrack(
                        id="",
                        track=track_name,
                        length_in_days=length_in_days_options["Default"],
                        active=True,
                    )
                form.client_tracks.append_entry(new_client_track)
        return form

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()
        form_class.org_employee_primary_key = fields.SelectField(
            "PK Column",
            choices=[("unique_corp_id", "Employee ID"), ("email", "E-Mail")],
        )
        form_class.field_map = FormToJSONField(DEFAULT_ORG_FIELD_MAP)
        form_class.optional_field_map_affiliations = FormToJSONField(
            EXTERNAL_IDENTIFIER_FIELD_MAP,
            label="Field Map- Affiliations",
            description="client_id is mandatory for records provided by a data provider",
        )
        form_class.health_plan_field_map_affiliations = FormToJSONField(
            HEALTH_PLAN_FIELD_MAP,
            label="Field Map- Health Plans",
        )
        form_class.mfa_required = fields.BooleanField(
            label="Require MFA for all organization users"
        )
        form_class.org_folder_link = fields.StringField()
        form_class.org_script_link = fields.StringField()
        form_class.disassociate_users = fields.BooleanField()
        form_class.alternate_verification = fields.BooleanField(
            label="Alternate employee verification (DOB/name/work_state)"
        )
        form_class.gift_card_allowed = SelectField(
            choices=[(True, "Yes"), (False, "No"), (None, "Unknown")],
            coerce=coerce_bool,
        )
        form_class.welcome_box_allowed = SelectField(
            choices=[(True, "Yes"), (False, "No")], coerce=coerce_bool
        )
        return form_class

    def validate_form(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        education_only = form.education_only.data
        rx_enabled = form.rx_enabled.data

        if education_only and rx_enabled:
            flash("organization cannot be education only and have rx_enabled", "error")
            return

        for data in form.external_ids.data:
            if data["primary_external_id"]:
                if not data["primary_external_id"].strip():
                    flash(
                        "Please ensure that for external org mappings, you provide a non-null/non-space value for the primary externalID"
                    )
                    return
                if ":" in data["primary_external_id"]:
                    flash(
                        "A primary external ID value you tried to save has a colon (:) in it- this is a restricted value. Please remove"
                    )
                    return

            if data["secondary_external_id"] and ":" in data["secondary_external_id"]:
                flash(
                    "A secondary external ID value you tried to save has a colon (:) in it- this is a restricted value. Please remove"
                )
                return

            if data["data_provider_organization"] and data["idp"]:
                flash(
                    "Please ensure that for external org mappings, you have selected only a data provider organization OR an IDP, not both."
                )
                return

        if (
            form.activated_at.data
            and form.terminated_at.data
            and form.activated_at.data > form.terminated_at.data
        ):
            flash(
                "Activation date for the organization is set to occur after the termination date"
            )

        # If organization is already created, if welcome box incentive is allowed and if we're updating gift card to allowed:
        # Check if any welcome box incentive organizations exist for this organization
        # If those welcome box incentive organizations do exist,
        # Then they must make some change to the organization or to those incentive organizations in order to enable gift cards.
        # Otherwise, user cannot enable both welcome box and gift cards
        if form._obj and form.welcome_box_allowed.data and form.gift_card_allowed.data:
            welcome_box_incentive_orgs = IncentiveOrganizationService().get_welcome_box_incentive_orgs_by_organization(
                form._obj.id
            )

            if len(welcome_box_incentive_orgs) > 0:
                # If there are welcome boxes associated with the organization,
                # then let the user know that they cannot enable gift cards unless they take a certain action
                tracks_string = ", ".join(
                    [
                        f"{incentive_org.track_name}"
                        for incentive_org in welcome_box_incentive_orgs
                    ]
                )

                flash(
                    f"Cannot enable incentive gift cards when welcome box is allowed and has active incentive organizations. Please disable incentive gift cards or deactivate/delete welcome box incentive orgs associated with incentive_action: {IncentiveAction.CA_INTRO.value} and track(s): {tracks_string}",
                    category="error",
                )
                return

        return super().validate_form(form)

    def create_model(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # All validation & etc must happen before we commit the new model
        self.validate_form(form)
        model = super().create_model(form)

        # If the model is False, super().create_model failed
        if not model:
            return model

        # create new alegeus ids only on allowed organization types
        model.create_alegeus_employer_id()
        # Set MFA settings for org
        if model.mfa_required:
            oar = OrganizationAuthRepository()
            org_auth = OrganizationAuth(organization_id=model.id, mfa_required=True)
            oar.create(instance=org_auth)
            db.session.commit()
        return model

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
            Organization,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


def coerce_bool(x):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if isinstance(x, str):
        if x == "True":
            return True
        elif x == "None":
            return None
        else:
            return False
    else:
        return bool(x) if x is not None else None


class OrganizationEligibilityFieldView(MavenAuditedView):
    create_permission = "create:org-eligibility-field"
    read_permission = "read:org-eligibility-field"
    edit_permission = "edit:org-eligibility-field"
    delete_permission = "delete:org-eligibility-field"

    form_choices = {"name": [("unique_corp_id", "unique_corp_id")]}

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
            OrganizationEligibilityField,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class OrganizationEmailDomainView(MavenAuditedView):
    create_permission = "create:org-email-domain"
    read_permission = "read:org-email-domain"
    edit_permission = "edit:org-email-domain"
    delete_permission = "delete:org-email-domain"

    column_descriptions = dict(
        domain="E.g., <code>microsoft.com</code>, <code>github.com</code>, "
        "<code>mavenclinic.com</code>. "
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
            OrganizationEmailDomain,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class OrganizationModuleExtensionView(MavenAuditedView):
    create_permission = "create:org-module-extension"
    read_permission = "read:org-module-extension"
    delete_permission = "delete:org-module-extension"

    form_rules = (
        "organization",
        "module",
        "effective_from",
        "effective_to",
        "extension_logic",
        "extension_days",
        "priority",
    )
    column_list = (
        "organization",
        "module",
        "extension_logic",
        "extension_days",
        "priority",
        "effective_from",
        "effective_to",
        "admin_extension_configured",
        "created_at",
    )
    column_editable_list = ("priority", "effective_from", "effective_to")
    column_labels = {"admin_extension_configured": "Extension Configured"}
    column_filters = ("organization_id", "module_id")

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
            OrganizationModuleExtension,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class OrgUserEmpIDFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(MemberTrack).filter(MemberTrack.user_id == value)


class DobEqualFilter(FilterEqual, BaseDateTextFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.filter(OrganizationEmployee.date_of_birth == value)


class ReadOnlyNullableBooleanField(fields.BooleanField):
    def __call__(self, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self.object_data is None:
            return '<span class="control-label muted">Not set</span>'
        return super().__call__(disabled=True, **kwargs)


class OrganizationEmployeeView(MavenAuditedView):
    create_permission = "create:org-employee"
    read_permission = "read:org-employee"
    edit_permission = "edit:org-employee"

    can_view_details = True
    edit_template = "org_employee_edit_template.html"
    list_template = "org_employee_list_template.html"
    details_template = "org_employee_details_template.html"

    column_sortable_list = ("organization", "email")
    column_list = (
        "id",
        "organization.name",
        "first_name",
        "last_name",
        "email",
        "users",
        "wallet_enabled",
        "alegeus_id",
        "verification_for_user",
    )
    column_details_list = (
        "id",
        "eligibility_member_id",
        "organization",
        "email",
        "users",
        "wallet_enabled",
        "json",
    )
    date_of_birth_filter = "Date of Birth"
    column_filters = (
        "email",
        "organization_id",
        "organization.name",
        "id",
        "eligibility_member_id",
        OrgUserEmpIDFilter(None, "User ID"),
        DobEqualFilter(None, date_of_birth_filter),
        "unique_corp_id",
        "first_name",
        "last_name",
        "retention_start_date",
        "alegeus_id",
    )
    column_searchable_list = ("organization.name",)
    column_labels = {
        "organization.name": "Organization Name",
    }

    form_excluded_columns = ["user", "users", "json", "credits", "dependents"]

    def v_formatter(view, context, model, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        all_user_ids = {uoe.user_id for uoe in model.user_organization_employees}
        if all_user_ids:
            markupstring = ""
            for user_id in all_user_ids:
                markupstring = (
                    f"{markupstring} <a href='/eligibility-admin/user-verification/%s'>%s</a>"
                    % (user_id, user_id)
                )
            return Markup(markupstring)
        else:
            return ""

    column_formatters = {
        "wallet_enabled": lambda v, c, m, p: (
            "" if m.wallet_enabled is None else m.wallet_enabled
        ),
        "verification_for_user": lambda v, c, m, p: OrganizationEmployeeView.v_formatter(
            v, c, m, p
        ),
    }

    form_ajax_refs = {
        "user_organization_employees": {"fields": ("id",), "page_size": 10},
        "organization": {"fields": ("id", "name"), "page_size": 10},
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
            OrganizationEmployee,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )

    @expose("/edit/", methods=("GET", "POST"))
    def edit_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self._template_args["user_class"] = User
        self._template_args["modules"] = Module.query.all()
        if request.method == "POST":
            with RedisLock(f"org_emp_edit_org_{request.form['organization']}"):
                return super().edit_view()
        return super().edit_view()

    @expose("/create/", methods=("GET", "POST"))
    def create_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if request.method == "POST":
            with RedisLock(f"org_emp_edit_org_{request.form['organization']}"):
                return super().create_view()
        return super().create_view()

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()
        form_class.spouse_account = fields.BooleanField()
        form_class.do_not_contact = fields.BooleanField()
        form_class.can_get_pregnant = fields.BooleanField()
        form_class.beneficiaries_enabled = fields.BooleanField()
        form_class.wallet_enabled = ReadOnlyNullableBooleanField()
        return form_class


class UserOrganizationEmployeeView(MavenAuditedView):
    create_permission = "create:user-org-employee"
    read_permission = "read:user-org-employee"
    edit_permission = "edit:user-org-employee"
    delete_permission = "delete:user-org-employee"

    column_filters = (
        UserOrganizationEmployee.id,
        UserOrganizationEmployee.user_id,
        UserOrganizationEmployee.organization_employee_id,
    )

    form_ajax_refs = {
        "user": {"fields": ("id",), "page_size": 10},
        "organization_employee": {"fields": ("id",), "page_size": 10},
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
            UserOrganizationEmployee,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class IncentiveView(MavenAuditedView):
    read_permission = "read:incentive"
    create_permission = "create:incentive"
    edit_permission = "edit:incentive"

    column_list = [
        "name",
        "type",
        "amount",
        "vendor",
        "design_asset",
        "active",
    ]

    column_labels = {"name": "Incentive Name (Internal)"}

    column_filters = ("name", "active")

    column_sortable_list = ("name", "active")

    form_excluded_columns = ("created_at", "modified_at")

    column_descriptions = {
        "name": "<i>This is for internal purposes only and will not be displayed to the user. Recommended format for gift cards: [amount] [vendor] [gift card]. Example: $25 Amazon gift card.</i>",
        "vendor": "<i>Use this field to denote the vendor for gift cards (e.g. Amazon, Walmart). For welcome boxes, please write ‘Maven’.</i>",
    }

    form_create_rules = (
        "name",
        "type",
        "amount",
        "vendor",
        "design_asset",
        "active",
    )

    # To make fields not editable in edit view.
    form_edit_rules = (
        ReadOnlyFieldRule("Type", lambda model: model.type.value),
        ReadOnlyFieldRule("Name", lambda model: model.name),
        ReadOnlyFieldRule("Amount", lambda model: model.amount),
        ReadOnlyFieldRule("Vendor", lambda model: model.vendor),
        ReadOnlyFieldRule("Design asset", lambda model: model.design_asset.value),
        "active",
    )

    def _form_has_incentive_fields(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            hasattr(form, "_obj")
            and form._obj is not None
            and form._obj.id is not None
            and hasattr(form, "active")
            and form.active
        )

    def validate_form(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            if self._form_has_incentive_fields(form):
                IncentiveOrganizationService().validate_incentive_not_used_when_deactivating(
                    incentive_id=form._obj.id, active=form.active.data
                )
        except InvalidIncentiveOrganizationException as e:
            db.session.rollback()
            flash(e.message, category="error")  # type: ignore[attr-defined] # "InvalidIncentiveOrganizationException" has no attribute "message"
            return
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
            Incentive,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class CountriesFilter(ContainsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value == "":
            return query
        if country := CountryRepository(session=db.session).get_by_name(name=value):
            country_code = country.alpha_2
        else:
            country_code = value
        return query.join(IncentiveOrganization.countries).filter(
            IncentiveOrganizationCountry.country_code.contains(country_code)
        )


def get_all_countries():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    all_countries = CountryRepository().all()
    return [(country.name, country.name) for country in all_countries]


class IncentiveOrganizationView(MavenAuditedView):
    read_permission = "read:incentive-organization"
    delete_permission = "delete:incentive-organization"
    create_permission = "create:incentive-organization"
    edit_permission = "edit:incentive-organization"

    column_list = (
        "id",
        "created_at",
        "modified_at",
        "incentive",
        "organization",
        "action",
        "track_name",
        "countries",
        "active",
    )
    column_filters = (
        FilterLike(column=Organization.name, name="Organization"),
        "action",
        FilterLike(column=Incentive.name, name="Incentive Name (internal)"),
        FilterEqual(
            column=IncentiveOrganization.track_name,
            name="Track",
            options=[(track.name, track.name) for track in TrackName],
        ),
        CountriesFilter(None, "Countries", options=get_all_countries),
    )
    column_sortable_list = ("created_at", "modified_at")

    column_labels = {
        "incentive": "Incentive Name (internal)",
    }

    form_excluded_columns = ("countries", "created_at", "modified_at")

    form_create_rules = (
        "incentive",
        "organization",
        "action",
        "track_name",
        rules.Text("<p>Countries that allow gift cards include:", escape=False),
        rules.Text(
            "United Arab Emirates, Australia, Canada, Germany, Spain, France, United Kingdom, Italy, Japan, Mexico, Sweden, Singapore, United States</p>",
            escape=False,
        ),
        "incentive_org_countries_list",
        "active",
    )

    # Sometimes we cache the incentives list we can choose from, so we need to refresh it in case we just added a new one
    @expose("/new/", methods=("GET", "POST"))
    def create_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self._refresh_forms_cache()
        return super().create_view()

    # Display list of already selected countries for the given IncentiveOrganization
    def on_form_prefill(self, form, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_form_prefill(form, id)
        incentive_org = self.get_one(id)
        form.incentive_org_countries_list.process_formdata(
            [c.country_code for c in incentive_org.countries]
        )

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()

        # Display list of tracks user can choose from
        form_class.track_name = Select2Field(
            label="Track Name",
            choices=[(track.value, track.value) for track in TrackName],
            validators=[validators.DataRequired()],
        )

        # Only display active incentives user can choose from
        form_class.incentive = QuerySelectField(
            label="Incentive Name (internal)",
            validators=[validators.InputRequired()],
            query_factory=lambda: Incentive.query.filter(Incentive.active == True),
        )

        # Display countries user can choose from
        # Displayed value will be country.name but selected will be country.alpha_2
        country_repo = CountryRepository(session=db.session)
        # Add "select all"-type options
        select_all = ("all_countries", "ALL")  # selects all countries
        select_all_with_gift_cards_allowed = (  # selects a preselected list of countries
            "all_with_gift_cards_allowed",
            "All countries where gift cards are allowed",
        )
        countries_list = [
            select_all,
            select_all_with_gift_cards_allowed,
            *[(c.alpha_2, c.name) for c in country_repo.all()],
        ]
        form_class.incentive_org_countries_list = Select2MultipleField(
            label="Countries",
            choices=countries_list,
            validators=[validators.DataRequired()],
        )

        return form_class

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_model_change(form, model, is_created)

        # At this point, we only have incentive_org_countries_list in the form, which is a list of strings
        # We need to grab these selected countries and create/delete IncentiveOrganizationCountry entities for each
        current_country_codes = set(
            incentive_org_country.country_code
            for incentive_org_country in model.countries
        )
        requested_country_codes = set(
            request.form.getlist("incentive_org_countries_list")
        )

        # If 'all_countries' is selected, select all countries.
        if "all_countries" in requested_country_codes:
            country_repo = CountryRepository(session=db.session)
            requested_country_codes = [  # type: ignore[assignment] # Incompatible types in assignment (expression has type "List[str]", variable has type "Set[Any]")
                country.alpha_2 for country in country_repo.all()
            ]
        # If 'all_with_gift_cards_allowed' is selected, add all countries to the existing list of requested_country_codes
        # For example, if 'Hong Kong' and 'all_with_gift_cards_allowed' is selected, then the final list would include
        # the hardcoded list below + 'Hong Kong'
        elif "all_with_gift_cards_allowed" in requested_country_codes:
            # Remove this option before extending the list
            requested_country_codes.remove("all_with_gift_cards_allowed")
            # United Arab Emirates, Australia, Canada, Germany, Spain, France, United Kingdom, Italy, Japan, Mexico, Sweden, Singapore, United States
            requested_country_codes.update(
                [
                    "AE",
                    "AU",
                    "CA",
                    "DE",
                    "ES",
                    "FR",
                    "GB",
                    "IT",
                    "JP",
                    "MX",
                    "SE",
                    "SG",
                    "US",
                ]
            )

        # From here, determine which countries need to be created and which should be removed
        # -
        # If no countries currently exist on incentive_org, just create the requested ones
        if len(current_country_codes) < 1:
            model.countries = [
                IncentiveOrganizationCountry(
                    incentive_organization_id=model.id, country_code=country_code
                )
                for country_code in requested_country_codes
            ]
        # If countries exist on incentive_org, remove and/or add according to difference between existing and requested
        else:
            difference_country_codes = current_country_codes ^ requested_country_codes
            for country_code in difference_country_codes:
                # If country_code does not exist in current_country_codes, create it
                if country_code not in current_country_codes:
                    new_incentive_org_country = IncentiveOrganizationCountry(
                        incentive_organization_id=model.id, country_code=country_code
                    )
                    model.countries.append(new_incentive_org_country)
                # Else, country_code exists in current_country_codes but not in requested_country_codes, hence, must be deleted
                else:
                    IncentiveOrganizationCountry.query.filter_by(
                        incentive_organization_id=model.id, country_code=country_code
                    ).delete()

        if model.organization_id:
            # Trigger job to update Braze with incentives for each user in org being changed
            service_ns = "incentive"
            update_braze_incentive_offboarding_for_org_users.delay(
                model.organization_id,
                service_ns=service_ns,
                team_ns=service_ns_team_mapper.get(service_ns),
            )

    def _form_has_incentive_org_fields(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            hasattr(form, "organization")
            and form.organization.data
            and hasattr(form, "incentive")
            and form.incentive.data
            and hasattr(form, "action")
            and form.action.data
            and hasattr(form, "track_name")
            and form.track_name.data
            and hasattr(form, "active")
            and form.active
        )

    def validate_form(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            if self._form_has_incentive_org_fields(form):
                # check to confirm that the organization is eligible for the incentive type selected
                IncentiveOrganizationService().check_eligibility(
                    organization=form.organization.data,
                    incentive=form.incentive.data,
                )
                # check to confirm there is not already an active incentive-org created for given
                # organization, incentivized action, track
                IncentiveOrganizationService().check_for_duplicates(
                    organization=form.organization.data,
                    action=form.action.data,
                    track_name=form.track_name.data,
                    active=form.active.data,
                    incentive_organization_id=form._obj.id if form._obj else None,
                )
        except InvalidIncentiveOrganizationException as e:
            db.session.rollback()
            flash(e.message, category="error")  # type: ignore[attr-defined] # "InvalidIncentiveOrganizationException" has no attribute "message"
            return
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
            IncentiveOrganization,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class CountryFilter(FilterEqual):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from models.profiles import MemberProfile

        if value == "":
            return query
        if country := CountryRepository(session=db.session).get_by_name(name=value):
            country_code = country.alpha_2
        else:
            country_code = value
        joined_tables = [mapper.class_ for mapper in query._join_entities]
        joined_table_names = [
            joined_table.__table__.name for joined_table in joined_tables
        ]
        if (
            "member_track" in joined_table_names
        ):  # a filter with member_track is already applied
            return query.join(
                MemberProfile, MemberTrack.user_id == MemberProfile.user_id
            ).filter(MemberProfile.country_code.contains(country_code))
        return (
            query.join(MemberTrack)
            .join(MemberProfile, MemberTrack.user_id == MemberProfile.user_id)
            .filter(MemberProfile.country_code.contains(country_code))
        )


class NotCountryFilter(FilterNotEqual):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from models.profiles import MemberProfile

        if value == "":
            return query
        if country := CountryRepository(session=db.session).get_by_name(name=value):
            country_code = country.alpha_2
        else:
            country_code = value
        joined_tables = [mapper.class_ for mapper in query._join_entities]
        joined_table_names = [
            joined_table.__table__.name for joined_table in joined_tables
        ]
        if (
            "member_track" in joined_table_names
        ):  # a filter with member_track is already applied
            return query.join(
                MemberProfile, MemberTrack.user_id == MemberProfile.user_id
            ).filter(
                or_(
                    MemberProfile.country_code != country_code,
                    MemberProfile.country_code == None,
                )
            )
        return (
            query.join(MemberTrack)
            .join(MemberProfile, MemberTrack.user_id == MemberProfile.user_id)
            .filter(
                or_(
                    MemberProfile.country_code != country_code,
                    MemberProfile.country_code == None,
                )
            )
        )


class TrackFilterIncentiveFulfillment(FilterEqual):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        joined_tables = [mapper.class_ for mapper in query._join_entities]
        joined_table_names = [
            joined_table.__table__.name for joined_table in joined_tables
        ]
        if (
            "member_track" in joined_table_names
        ):  # a filter with member_track is already applied
            return query.filter(MemberTrack.name == value)

        return query.join(MemberTrack).filter(MemberTrack.name == value)


class IncentiveFulfillmentView(MavenAuditedView):
    read_permission = "read:incentive-fulfillment"
    create_permission = "create:incentive-fulfillment"
    edit_permission = "edit:incentive-fulfillment"

    column_list = [
        "member_track.user_id",
        "member_track.user.email",
        "member_country_name",
        "incentive.name",
        "incentive.vendor",
        "incentive.amount",
        "incentivized_action",
        "member_track.name",
        "status",
        "date_earned",
        "date_issued",
    ]

    column_labels = {
        "member_track.user_id": "Member ID",
        "member_track.user.email": "Member Email",
        "member_country_name": "Member Country",
        "incentive.name": "Incentive Name",
        "incentive.vendor": "Vendor",
        "incentive.amount": "Amount",
        "member_track.name": "Track",
    }

    column_filters = (
        "member_track.user_id",
        "member_track.user.email",
        CountryFilter(None, "Member Country", options=get_all_countries),
        NotCountryFilter(None, "Member Country", options=get_all_countries),
        FilterLike(column=Incentive.name, name="Incentive Name (internal)"),
        "incentive.vendor",
        "incentive.amount",
        TrackFilterIncentiveFulfillment(
            None, "Track", options=[(track.value, track.value) for track in TrackName]
        ),
        "incentivized_action",
        "status",
        "date_earned",
        "date_issued",
    )

    column_sortable_list = (
        "status",
        "date_earned",
        "date_issued",
        ("member_country_name", "member_track.user.member_profile.country_code"),
        "incentivized_action",
    )

    form_excluded_columns = ("created_at", "modified_at")

    form_create_rules = (
        "user_id",
        "incentive",
        "incentivized_action",
        "track_name",
        "status",
        "date_seen",
        "date_earned",
        "date_issued",
        "tracking_number",
        "member_track_id",
    )

    form_edit_rules = (
        ReadOnlyFieldRule("Member ID", lambda model: model.member_track.user_id),
        ReadOnlyFieldRule("Member Email", lambda model: model.member_track.user.email),
        ReadOnlyFieldRule(
            "Incentive Name (Internal)",
            lambda model: model.incentive.name,
        ),
        ReadOnlyFieldRule(
            "Incentivized Action", lambda model: model.incentivized_action.value
        ),
        ReadOnlyFieldRule("Track", lambda model: model.member_track.name),
        "status",
        ReadOnlyFieldRule("Date Seen", lambda model: model.date_seen),
        ReadOnlyFieldRule("Date Earned", lambda model: model.date_earned),
        "date_issued",
        "tracking_number",
    )

    def validate_user_id(self, form, field):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = User.query.get(field.data)
        if not user:
            raise validators.ValidationError("Invalid Member ID")

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()

        # Display all valid user_ids
        form_class.user_id = IntegerField(
            label="Member ID",
            validators=[validators.InputRequired(), self.validate_user_id],
        )

        # Display list of tracks user can choose from
        form_class.track_name = Select2Field(
            label="Track Name",
            choices=[(track.value, track.value) for track in TrackName],
            validators=[validators.DataRequired()],
        )

        # Display all incentives
        form_class.incentive = QuerySelectField(
            label="Incentive Name (Internal)",
            validators=[validators.InputRequired()],
            query_factory=lambda: Incentive.query,
        )

        form_class.date_seen = fields.DateField(
            label="Date Seen",
            widget=DatePickerWidget(),
            validators=[validators.InputRequired()],
        )

        form_class.date_earned = fields.DateField(
            label="Date Earned",
            widget=DatePickerWidget(),
            validators=[validators.Optional()],
        )

        form_class.date_issued = fields.DateField(
            label="Date Issued",
            widget=DatePickerWidget(),
            validators=[validators.Optional()],
        )

        # we need to add the field to the form to use it in `create_model`,
        # but don't want to display the field
        form_class.member_track_id = fields.HiddenField("")

        return form_class

    def create_model(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # if there are multiple member tracks for same user_id/track take most recent
        member_track_id_query = (
            db.session.query(MemberTrack.id)
            .filter(
                MemberTrack.user_id == form.user_id.data,
                MemberTrack.name == form.track_name.data,
            )
            .order_by(MemberTrack.start_date.desc())
        )
        # for Offboarding Assessments we may not have an active member_track so only add
        # active filter if the incentivized action is CA Intro
        if form.incentivized_action.data == IncentiveAction.CA_INTRO:
            member_track_id_query = member_track_id_query.filter(
                MemberTrack.active == True,
            )
        member_track_id = member_track_id_query.first()
        if not member_track_id or not member_track_id[0]:
            flash("Invalid track selection for this member", category="error")
            return False
        # get first element because query value is (x,)
        form.member_track_id.data = member_track_id[0]

        # check for duplicates
        incentive_fulfillment = (
            db.session.query(IncentiveFulfillment)
            .filter(
                IncentiveFulfillment.member_track_id == member_track_id[0],
                IncentiveFulfillment.incentivized_action
                == form.incentivized_action.data,
            )
            .first()
        )
        if incentive_fulfillment:
            db.session.rollback()
            flash(
                "Incentive-Fulfillment record already exists for this User, Track, and Incentivized Action.",
                category="error",
            )
            return False

        return super().create_model(form)

    def _form_has_incentive_fulfillment_create_fields(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return hasattr(form, "status") and form.status.data and not form._obj

    def _form_has_incentive_fulfillment_edit_fields(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            hasattr(form, "status")
            and form.status.data
            and hasattr(form, "_obj")
            and form._obj.id
        )

    def _validate_status_seen_earned_processing_date_issued_empty(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if (
            form.status.data == IncentiveStatus.EARNED.name
            or form.status.data == IncentiveStatus.SEEN.name
            or form.status.data == IncentiveStatus.PROCESSING.name
        ) and (hasattr(form, "date_issued") and form.date_issued.data):
            raise IncentiveStatusSeenEarnedProcessingDateIssuedNotEmptyException

    def _validate_status_fulfilled_date_issued_populated(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if form.status.data == IncentiveStatus.FULFILLED.name and not (
            hasattr(form, "date_issued") and form.date_issued.data
        ):
            raise IncentiveStatusFulfilledDateIssuedRequiredException

    def _validate_status_fulfilled_date_earned_and_date_issued_populated(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if form.status.data == IncentiveStatus.FULFILLED.name and not (
            hasattr(form, "date_earned")
            and form.date_earned.data
            and hasattr(form, "date_issued")
            and form.date_issued.data
        ):
            raise IncentiveStatusFulfilledDateEarnedDateIssuedRequiredException

    def _validate_status_earned_processing_date_earned_populated(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if (
            form.status.data == IncentiveStatus.EARNED.name
            or form.status.data == IncentiveStatus.PROCESSING.name
        ) and not (hasattr(form, "date_earned") and form.date_earned.data):
            raise IncentiveStatusEarnedProcessingDateEarnedRequiredException

    def _validate_status_seen_date_earned_empty(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if form.status.data == IncentiveStatus.SEEN.name and (
            hasattr(form, "date_earned") and form.date_earned.data
        ):
            raise IncentiveStatusSeenDateEarnedNotEmptyException

    def validate_form(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            if self._form_has_incentive_fulfillment_create_fields(form):
                self._validate_status_fulfilled_date_earned_and_date_issued_populated(
                    form
                )
                self._validate_status_earned_processing_date_earned_populated(form)
                self._validate_status_seen_earned_processing_date_issued_empty(form)
                self._validate_status_seen_date_earned_empty(form)
            elif self._form_has_incentive_fulfillment_edit_fields(form):
                self._validate_status_fulfilled_date_issued_populated(form)
                self._validate_status_seen_earned_processing_date_issued_empty(form)
        except InvalidIncentiveFulfillmentException as e:
            db.session.rollback()
            flash(e.message, category="error")  # type: ignore[attr-defined] # "InvalidIncentiveFulfillmentException" has no attribute "message"
            return
        return super().validate_form(form)

    @action(
        "mark_earned",
        "Mark as Earned",
        "Are you sure? This will mark all selected records as 'earned'",
    )
    def mark_earned(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        now = datetime.datetime.utcnow()
        records = IncentiveOrganizationService().get_incentive_fulfillments(ids)
        records_updated = []
        for record in records:
            if record.status == IncentiveStatus.SEEN and not record.date_earned:
                record.date_earned = now
                record.status = IncentiveStatus.EARNED
                records_updated.append(record)
            else:
                flash(
                    f"Not able to update status to EARNED for record with member id {record.member_track.user_id} that is {record.status.name}",
                    category="error",
                )
        if records_updated:
            emit_bulk_audit_log_update(records_updated)
            db.session.commit()
            flash(
                f"{len(records_updated)} records marked as EARNED", category="success"
            )

    @action(
        "mark_processing",
        "Mark as Processing",
        "Are you sure? This will mark all selected records as 'processing'",
    )
    def mark_processing(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        now = datetime.datetime.utcnow()
        records = IncentiveOrganizationService().get_incentive_fulfillments(ids)
        records_updated = []
        for record in records:
            if (
                record.status in [IncentiveStatus.SEEN, IncentiveStatus.EARNED]
                and not record.date_issued
            ):
                record.status = IncentiveStatus.PROCESSING
                if not record.date_earned:
                    record.date_earned = now

                records_updated.append(record)
            else:
                flash(
                    f"Not able to update status to PROCESSING for record with member id {record.member_track.user_id} that is {record.status.name}",
                    category="error",
                )
        if records_updated:
            emit_bulk_audit_log_update(records_updated)
            db.session.commit()
            flash(
                f"{len(records_updated)} records marked as PROCESSING",
                category="success",
            )

    @action(
        "mark_fulfilled",
        "Mark as Fulfilled",
        "Are you sure? This will mark all selected records as 'fulfilled'",
    )
    def mark_fulfilled(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        now = datetime.datetime.utcnow()
        records = IncentiveOrganizationService().get_incentive_fulfillments(ids)
        records_updated = []
        for record in records:
            if record.status != IncentiveStatus.FULFILLED and not record.date_issued:
                record.date_issued = now
                record.status = IncentiveStatus.FULFILLED
                if not record.date_earned:
                    record.date_earned = now
                records_updated.append(record)
            else:
                flash(
                    f"Not able to update status to FULFILLED for record with member id {record.member_track.user_id} that is {record.status.name}",
                    category="error",
                )
        if records_updated:
            emit_bulk_audit_log_update(records_updated)
            db.session.commit()
            flash(
                f"{len(records_updated)} records marked as FULFILLED",
                category="success",
            )

    @action("generate_csv", "Download CSV")
    def generate_csv(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        records = IncentiveOrganizationService().get_incentive_fulfillments(ids)

        report = IncentiveOrganizationService().create_incentive_fulfillment_csv(
            records
        )
        emit_bulk_audit_log_read(records)

        response = Response(report)

        filename = f"incentive-fulfillments-{datetime.datetime.now().strftime('%y_%m_%d-%H_%M_%S')}.csv"
        response.headers["Content-Description"] = "File Transfer"
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Content-Type"] = "text/csv"
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"

        return response

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
            IncentiveFulfillment,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class InviteView(MavenAuditedView):
    create_permission = "create:invite"
    read_permission = "read:invite"
    edit_permission = "edit:invite"
    delete_permission = "delete:invite"

    column_filters = (User.id, User.email, Invite.email, Invite.type)
    column_list = (
        "created_by_user",
        "created_at",
        "email",
        "name",
        "type",
        "claimed",
        "expires_at",
    )
    form_widget_args = {
        "created_at": {"disabled": True},
        "expires_at": {"disabled": True},
    }
    column_sortable_list = ("created_at", "claimed")

    form_ajax_refs = {"created_by_user": USER_AJAX_REF}

    edit_template = "invite_edit_template.html"

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
            Invite,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if model.invite_type in (
            InviteType.FILELESS_EMPLOYEE,
            InviteType.FILELESS_DEPENDENT,
        ):
            braze.track_fileless_email_from_invite(model)
        super().on_model_change(form, model, is_created)


class BusinessLeadView(MavenAuditedView):
    create_permission = "create:business-lead"
    read_permission = "read:business-lead"
    edit_permission = "edit:business-lead"

    form_columns = ("json",)

    form_overrides = dict(json=fa_fields.JSONField)

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
            BusinessLead,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


DEFAULT_BATCH_SIZE = 50


class AssessmentView(MavenAuditedView):
    read_permission = "read:assessment"
    delete_permission = "delete:assessment"
    create_permission = "create:assessment"
    edit_permission = "edit:assessment"

    required_capability = "admin_assessment"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")
    edit_template = "assessment_edit.html"
    create_template = "assessment_edit.html"
    column_list = ("lifecycle", "version", "title", "estimated_time")
    form_excluded_columns = ("user_assessments", "created_at")
    form_args = {
        "estimated_time": {"label": "Estimated Time (secs)"},
        "slug": {"validators": [slug_re_check]},
    }

    column_filters = ("id", "title")

    form_overrides = dict(quiz_body=fa_fields.JSONField, score_band=fa_fields.JSONField)

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()
        form_class.image_id = ImageUploadField(
            label="Image", allowed_extensions=["jpg", "png"]
        )
        return form_class

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._validate_user_flag_info(model)
        super().on_model_change(form, model, is_created)

    def _validate_user_flag_info(self, assessment):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        errors = []
        for question in assessment.quiz_body["questions"]:
            if not question.get("user_flag_info"):
                continue

            if question["user_flag_info"].get("type") not in {
                USER_FLAG_INFO_TYPE_MULTI_SELECTION,
                USER_FLAG_INFO_TYPE_OBESITY_CALC,
            }:
                errors.append(
                    f"user_flag_info type must be one of {USER_FLAG_INFO_TYPE_MULTI_SELECTION}, {USER_FLAG_INFO_TYPE_OBESITY_CALC}."
                )

            option_values = [o["value"] for o in question["widget"]["options"]]
            for option_name, user_flag_name in (
                question["user_flag_info"].get("meta", {}).items()
            ):
                if option_name not in option_values:
                    errors.append(
                        f"Invalid option name: {option_name} not found "
                        f"in option values: {option_values}"
                    )
                flag = RiskFlag.query.filter(
                    RiskFlag.name == user_flag_name
                ).one_or_none()
                if not flag:
                    errors.append(f"Flag not found: {user_flag_name}")
        if errors:
            raise validators.ValidationError(", ".join(errors))

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
            Assessment,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class AssessmentLifecycleView(MavenAuditedView):
    read_permission = "read:assessment-lifecycle"
    delete_permission = "delete:assessment-lifecycle"
    create_permission = "create:assessment-lifecycle"
    edit_permission = "edit:assessment-lifecycle"

    required_capability = "admin_assessment_lifecycle"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")
    column_exclude_list = ("modified_at", "created_at")

    # Hide tracks because relationship is now set at the Track rather than phase level.
    # Hide allowed_tracks to not expose the AssessmentLifecycleTrack implementation detail.
    form_excluded_columns = ("phases", "allowed_tracks")

    form_args = {"type": {"choices": [nat.value for nat in NeedsAssessmentTypes]}}

    form_ajax_refs = {"assessments": {"fields": ("title",), "page_size": 10}}

    inline_models = (
        (
            Assessment,
            {
                "form_columns": (
                    "version",
                    "title",
                    "description",
                    "icon",
                    "slug",
                    "estimated_time",
                    "id",
                )
            },
        ),
    )

    def on_form_prefill(self, form, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_form_prefill(form, id)
        a = self.get_one(id)
        form.type.process_data(a.type.value)
        form.tracks.process_formdata([t.value for t in a.allowed_track_names])

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()
        form_class.tracks = Select2MultipleField(
            label="Tracks", choices=[(track.value, track.value) for track in TrackName]
        )
        return form_class

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_model_change(form, model, is_created)
        model.allowed_tracks = [
            AssessmentLifecycleTrack(track_name=track, assessment_lifecycle_id=model.id)
            for track in request.form.getlist(
                "tracks"
            )  # support selecting multiple tracks
        ]

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
            AssessmentLifecycle,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class AssessmentLifecycleTypeFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(Assessment.lifecycle).filter(
            AssessmentLifecycle.type == value
        )


class NeedsAssessmentView(MavenAuditedView):
    read_permission = "read:needs-assessment"
    delete_permission = "delete:needs-assessment"
    create_permission = "create:needs-assessment"
    edit_permission = "edit:needs-assessment"
    write_permission = "write:needs-assessment"

    required_capability = "admin_needs_assessment"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")
    audit_model_view = True  # type: ignore[assignment] # Incompatible types in assignment (expression has type "bool", base class "MavenAuditedView" defined the type as "None")

    column_exclude_list = ("modified_at", "created_at", "json")
    column_filters = (
        "user_id",
        AssessmentLifecycleTypeFilter(
            None,
            "Lifecycle Type",
            options=[(x.value, x.value) for x in NeedsAssessmentTypes],
        ),
    )
    edit_template = "needs_assessment_edit_template.html"

    form_excluded_columns = ["appointment"]
    form_ajax_refs = {"user": USER_AJAX_REF}

    @expose("/edit/", methods=("GET", "POST"))
    def edit_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        na_id = get_mdict_item_or_list(request.args, "id")
        model = None
        if na_id:
            model = self.get_one(na_id)

        if model:
            answers = {}
            for answer in model.json.get("answers", []):
                if isinstance(answer, (dict, list)):
                    answers[answer["id"]] = json.dumps(  # type: ignore[call-overload] # No overload variant of "__getitem__" of "list" matches argument type "str"
                        answer["body"], indent=2  # type: ignore[call-overload] # No overload variant of "__getitem__" of "list" matches argument type "str"
                    ).replace(
                        "\n", "<br/>"
                    )
                else:
                    answers[answer["id"]] = answer["body"]

            quiz_content = []
            for question in model.assessment_template.quiz_body.get("questions", []):
                display_answer = answers.get(question["id"], "")
                if (
                    "widget" in question
                    and question["widget"]["type"]
                    in ["c-quiz-question", "m-quiz-question-single"]
                    and "options" in question["widget"]
                ):
                    answer_options = next(
                        (
                            option
                            for option in question["widget"]["options"]
                            if (
                                str(option["value"]) == str(display_answer)
                                or (option["value"] == "0" and display_answer == '"0"')
                            )
                        ),
                        {},
                    )
                    display_answer = (
                        answer_options.get("label", "") + f" ({display_answer})"
                    )
                quiz_content.append((question["body"], display_answer))

            self._template_args["quiz_content"] = quiz_content

        return super().edit_view()

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
            NeedsAssessment,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class HDCAssessmentView(MavenAuditedView):
    read_permission = "read:assessment-track"
    delete_permission = "delete:assessment-track"
    create_permission = "create:assessment-track"
    edit_permission = "edit:assessment-track"

    required_capability = "admin_assessment"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    form_excluded_columns = ["modified_at"]

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
            AssessmentTrack,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class InboundPhoneNumberViewOrganizationsFilter(ContainsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if value == "":
            return query
        if organization := OrganizationRepository(
            session=db.session
        ).get_organization_by_name(name=value):
            organization_name = organization.name
        else:
            organization_name = value
        return query.join(InboundPhoneNumber.organizations).filter(
            Organization.name.contains(organization_name)
        )


def get_all_organizations() -> list[tuple[str, str]]:
    organization_names = db.session.query(Organization.name).all()
    return [(name[0], name[0]) for name in organization_names]


def normalize_phone_number(
    phone_number: str, default_region: str = "US"
) -> Optional[str]:
    try:
        # attempt to parse the phone number with the default region
        parsed_number = phonenumbers.parse(phone_number, default_region)

        # if the number has a country code, it should start with +
        if phonenumbers.format_number(
            parsed_number, phonenumbers.PhoneNumberFormat.E164
        ).startswith("+"):
            normalized = phonenumbers.format_number(
                parsed_number, phonenumbers.PhoneNumberFormat.E164
            )
        else:
            # Attempt to parse without a specific region
            parsed_number = phonenumbers.parse(phone_number, None)
            normalized = phonenumbers.format_number(
                parsed_number, phonenumbers.PhoneNumberFormat.E164
            )

        # Remove the leading '+' for comparison purposes
        return normalized[1:]
    except phonenumbers.NumberParseException:
        return None


def reset_org_inbound_phone_number(org_id: int) -> None:
    """
    Removes the existing organization <> inbound phone number relationship
    :param org_id:
    :return:
    """
    db.session.execute(
        org_inbound_phone_number.delete().where(
            org_inbound_phone_number.c.org_id == org_id
        )
    )
    db.session.commit()


class InboundPhoneNumberView(MavenAuditedView):
    create_permission = "create:org-phone-support"
    read_permission = "read:org-phone-support"
    edit_permission = "edit:org-phone-support"
    delete_permission = "delete:org-phone-support"

    can_view_details = True

    column_list = (
        "id",
        "number",
        "organizations",
    )

    column_filters = (
        InboundPhoneNumber.number,
        InboundPhoneNumberViewOrganizationsFilter(
            None, "Organizations", options=get_all_organizations
        ),
    )

    column_descriptions = {
        "number": "Please use the following format: XXX-XXX-XXXX.",
    }

    form_edit_rules = (
        ReadOnlyFieldRule("Phone Number", lambda model: model.number),
        "organizations",
    )

    def create_model(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        organizations = form.organizations.data
        phone_number = form.number.data
        normalized_input_phone_number = normalize_phone_number(phone_number)

        # get all org phone numbers
        existing_org_phone_numbers = db.session.query(InboundPhoneNumber).all()
        normalized_existing_phone_numbers = [
            normalize_phone_number(phone.number) for phone in existing_org_phone_numbers
        ]

        # if the telephone number already exists, do not allow the user to create a new item
        if normalized_input_phone_number in normalized_existing_phone_numbers:
            flash(f"Phone number {phone_number} already exists in the list view")
            return

        # if the telephone number already exists for an organization, raise an error when a user attempts to click save
        for organization in organizations:
            for inbound_phone_number in existing_org_phone_numbers:
                if any(
                    org.id == organization.id
                    for org in inbound_phone_number.organizations
                ):
                    flash(
                        f"Organization {organization.name} is already tied to another phone number"
                    )
                    return

        return super().create_model(form)

    def update_model(self, form, model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        organizations = form.organizations.data

        # get all org phone numbers
        existing_org_phone_numbers = db.session.query(InboundPhoneNumber).all()

        # if the telephone number already exists for an organization, raise an error when a user attempts to click save
        for organization in organizations:
            for inbound_phone_number in existing_org_phone_numbers:
                # if a telephone number already exists for the org, update the number
                if any(
                    org.id == organization.id
                    for org in inbound_phone_number.organizations
                ):
                    reset_org_inbound_phone_number(org_id=organization.id)

        return super().update_model(form, model)

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
        return cls(
            # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"git st
            InboundPhoneNumber,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
