import logging
from datetime import date, datetime, timedelta, timezone
from typing import Type

from flask import flash, request, url_for
from flask_admin import expose
from flask_admin.actions import action
from flask_admin.contrib.sqla.ajax import QueryAjaxModelLoader
from flask_admin.model.ajax import DEFAULT_PAGE_SIZE
from flask_admin.model.helpers import get_mdict_item_or_list
from flask_login import current_user
from markupsafe import Markup
from sqlalchemy import String, and_, cast, or_
from wtforms import fields

from admin.views.base import (
    USER_AJAX_REF,
    AdminCategory,
    AdminViewT,
    MavenAdminView,
    MavenAuditedView,
)
from audit_log import utils as audit_utils
from common.constants import Environment
from models import tracks
from models.enterprise import Organization
from models.tracks import (
    ChangeReason,
    TrackLifecycleError,
    TrackName,
    cancel_transition,
    get_track,
    renew,
)
from models.tracks.client_track import ClientTrack
from models.tracks.member_track import MemberTrack, TrackChangeReason
from storage.connection import RoutingSQLAlchemy, db
from utils import member_tracks
from utils.migrations.tracks.migrate_client_track_length import (
    create_tracks,
    terminate_pending_renewals,
    update_existing_member_tracks,
)


class ClientTrackView(MavenAuditedView):
    read_permission = "read:client-track"
    can_view_details = True

    column_list = ("id", "organization", "track", "active", "launch_date", "ended_at")
    form_rules = ("organization", "track", "active")
    form_choices = {"track": [(track.value, track.name) for track in TrackName]}

    column_filters = (
        "id",
        "organization_id",
    )
    column_descriptions = {
        "launch_date": "If populated, the date the ClientTrack becomes available to members."
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
            ClientTrack,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ClientTrackQueryAjaxModelLoader(QueryAjaxModelLoader):
    def format(self, model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if model is None:
            return ""
        assert isinstance(model, ClientTrack)
        return getattr(model, self.pk), str(model)

    def get_list(self, term, offset=0, limit=DEFAULT_PAGE_SIZE):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        query = self.session.query(self.model).join(Organization)

        filters = (
            cast(field, String).ilike("%%%s%%" % term) for field in self._cached_fields
        )
        query = query.filter(or_(*filters))

        if self.filters:
            filters = [  # type: ignore[assignment] # Incompatible types in assignment (expression has type "List[str]", variable has type "Generator[Any, None, None]")
                f"{self.model.__tablename__.lower()}.{value}" for value in self.filters
            ]
            query = query.filter(and_(*filters))

        if self.order_by:
            query = query.order_by(self.order_by)

        return query.offset(offset).limit(limit).all()


class MemberTrackView(MavenAuditedView):
    read_permission = "read:member-track"
    edit_permission = "edit:member-track"

    can_view_details = False

    edit_template = "member_track_edit_template.html"

    column_filters = ("id", "user_id")
    column_list = (
        "id",
        "user",
        "name",
        "active",
        "activated_at",
        "ended_at",
        "scheduled_end_date",
        "organization",
        "eligibility_verification",
    )

    def _user_formatter(self, context, model, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if model.user_id is None:
            return "None"
        if model.user_id == 0:
            return "GDPR Deleted"
        url = url_for("user.edit_view", id=model.user_id)
        return Markup(f"<a href='{url}'>{model.user_id}</a>")

    def _scheduled_end_date_formatter(self, context, model, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return model.get_scheduled_end_date()

    def _organization_formatter(self, context, model, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        organization_url = url_for("organization.edit_view", id=model.organization.id)
        client_track_url = url_for("clienttrack.edit_view", id=model.client_track_id)
        return Markup(
            f"<a href='{organization_url}'>Organization {model.organization.id}</a></br>"
            f"<a href='{client_track_url}'>Client Track {model.client_track_id}</a>"
        )

    def _eligibility_verification_formatter(self, context, model, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if model.eligibility_verification_id is None:
            return "None"
        url = f"/eligibility-admin/verification/details/?id={model.eligibility_verification_id}"
        return Markup(f"<a href='{url}'>{model.eligibility_verification_id}</a>")

    column_formatters = {
        "user": _user_formatter,
        "scheduled_end_date": _scheduled_end_date_formatter,
        "organization": _organization_formatter,
        "eligibility_verification": _eligibility_verification_formatter,
    }

    form_widget_args = {
        "anchor_date": {"disabled": True},
        "user": {"disabled": True},
        "auto_transitioned": {"disabled": True},
        "transitioning_to": {"disabled": True},
        "ended_at": {"disabled": True},
        "modified_at": {"disabled": True},
        "created_at": {"disabled": True},
        "bucket_id": {"disabled": True},
        "scheduled_end_date": {"disabled": True},
        "closure_reason": {"disabled": True},
        "name": {"readonly": True},
    }

    form_excluded_columns = (
        "legacy_program",
        "legacy_module",
        "organization_employee",
        "statuses",
        "current_status",
    )

    form_ajax_refs = {
        "user": USER_AJAX_REF,
        "client_track": ClientTrackQueryAjaxModelLoader(
            "client_track",
            db.session,
            ClientTrack,
            fields=["id", "track", Organization.id, Organization.name],
            page_size=10,
        ),
    }

    def on_form_prefill(self, form, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().on_form_prefill(form, id)
        track = db.session.query(self.model).get(id)
        form.scheduled_end_date.process_formdata(
            (track.get_scheduled_end_date().isoformat(),)  # must be a tuple
        )

        if track.sub_population_id is not None:
            # sub_population_id is read-only when sub_population_id is valid
            form.sub_population_id.render_kw = {"disabled": True}
        else:
            form.sub_population_id.render_kw = {"disabled": False}

    def scaffold_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form_class = super().scaffold_form()
        form_class.scheduled_end_date = fields.DateField()
        return form_class

    @expose("/edit/", methods=("GET", "POST"))
    def edit_view(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        id = get_mdict_item_or_list(request.args, "id")
        model = None
        if id:
            model = self.get_one(id)

        if model:
            self._template_args["transitions"] = get_track(model.name).transitions
            self._template_args["member_profile_url"] = url_for(
                "memberprofile.edit_view", id=model.user_id
            )
            self._template_args["track_change_reasons"] = db.session.query(
                TrackChangeReason
            ).all()

        return super().edit_view()

    @action(
        "reactivate",
        "Reactivate",
        "Are you sure you want to re-activate the selected member track?",
    )
    def action_reactivate(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if len(ids) != 1:
            flash("Please reactivate one member track at a time.", category="warning")
            return

        member_track_id = ids[0]
        member_track = db.session.query(MemberTrack).get(member_track_id)

        if member_track.is_deprecated:
            flash(
                "Cannot reactivate a member track that has been deprecated.",
                category="warning",
            )
            return

        if member_track.ended_at is None:
            flash(
                "This member track is already active and does not need to be reactivated.",
                category="info",
            )
            return

        if member_track.get_scheduled_end_date() < date.today():
            flash(
                "Cannot reactivate a member track with a scheduled end date in the past.",
                category="warning",
            )
            return

        member_track.transitioning_to = None
        member_track.ended_at = None
        member_track.set_anchor_date()
        member_track.modified_by = str(current_user.id or "")
        member_track.change_reason = ChangeReason.ADMIN_REACTIVATE

        # TODO: [Tracks] Delete next 2 lines after we're no longer supporting CarePrograms.
        if member_track.legacy_program:
            member_track.legacy_program.ended_at = None
            member_track.legacy_program.last_phase.ended_at = None

        user_id = member_track.user_id
        # refill credit for the user
        if user_id:
            from appointments.tasks.credits import refill_credits_for_enterprise_member

            refill_credits_for_enterprise_member(user_id)
        audit_utils.emit_audit_log_update(member_track)
        db.session.commit()

    @action(
        "terminate",
        "Terminate",
        "Are you sure you want to terminate the selected member track? The client will still get billed for this track. ",
    )
    def action_terminate(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._terminate_track(ids, revoke_billing=False)

    @action(
        "cancel_transition",
        "Cancel Transition",
        "Are you sure you want to cancel the transition for selected member track?",
    )
    def action_cancel_transition(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        member_track_id = ids[0]
        member_track = db.session.query(MemberTrack).get(member_track_id)
        cancel_transition(
            track=member_track, change_reason=ChangeReason.ADMIN_CANCEL_TRANSITION
        )
        audit_utils.emit_audit_log_update(member_track)
        db.session.commit()

    @action(
        "terminate_and_revoke_billing",
        "Terminate and Revoke Billing",
        "Are you sure you want to terminate the selected member track and revoke billing? The client will NOT be billed for this track.",
    )
    def action_terminate_and_revoke_billing(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._terminate_track(ids, revoke_billing=True)

    def _terminate_track(self, ids, revoke_billing):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if len(ids) != 1:
            flash("Please terminate one member track at a time.", category="warning")
            return

        member_track_id = ids[0]
        member_track = db.session.query(MemberTrack).get(member_track_id)
        if member_track:
            member_tracks.terminate_track(
                member_track_id=member_track_id,
                revoke_billing=revoke_billing,
                user_id=current_user.id,
                change_reason=ChangeReason.ADMIN_TERMINATE_TRACK,
            )
            audit_utils.emit_audit_log_update(member_track)

    @action(
        "test_for_opt_in_renewal",
        "mark for opt in renewal test",
        "Does this track belong to a testing account? This function is for testing only",
    )
    def action_mark_track_for_optin_renewal_test(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if len(ids) != 1:
            flash("Please test one member track at a time.", category="warning")
            return

        member_track_id = ids[0]
        member_track = db.session.query(MemberTrack).get(member_track_id)

        self._reject_renewal_test_for_invalid_track(member_track)

        # Add 10 days to the current date
        future_date = datetime.now(timezone.utc) + timedelta(days=10)
        date_part = future_date.date()
        member_track.set_scheduled_end_date(date_part)

        tracks.check_track_state(member_track)
        audit_utils.emit_audit_log_update(member_track)

        db.session.commit()

    @action(
        "test_for_opt_out_renewal",
        "mark for opt out renewal test",
        "Does this track belong to a testing account? This function is for testing only",
    )
    def action_mark_track_for_optout_renewal_test(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if len(ids) != 1:
            flash("Please test one member track at a time.", category="warning")
            return

        member_track_id = ids[0]
        member_track = db.session.query(MemberTrack).get(member_track_id)

        self._reject_renewal_test_for_invalid_track(member_track)

        # Add 30 days to the current date
        future_date = datetime.now(timezone.utc) + timedelta(days=30)
        date_part = future_date.date()
        member_track.set_scheduled_end_date(date_part)

        tracks.check_track_state(member_track)

        try:
            renew(
                track=member_track,
                is_auto_renewal=True,
                change_reason=ChangeReason.OPT_OUT_JOB_RENEW,
            )
            member_track.qualified_for_optout = True
        except TrackLifecycleError as e:
            db.session.rollback()
            logging.error(e)
            member_track.qualified_for_optout = False
        audit_utils.emit_audit_log_update(member_track)

        db.session.add(member_track)
        db.session.commit()

    def _reject_renewal_test_for_invalid_track(self, member_track):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        org_name = member_track.organization.name
        if Environment.current() == Environment.PRODUCTION:
            if org_name != "Maven_Clinic2":
                flash(
                    "The track belongs to a real member. Test member should be in the org Maven_Clinic2",
                    category="warning",
                )
                return

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
            MemberTrack,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class TracksExtensionView(MavenAdminView):

    read_permission = "read:tracks-extension"
    delete_permission = "delete:tracks-extension"
    create_permission = "create:tracks-extension"
    edit_permission = "edit:tracks-extension"

    @expose("/")
    def index(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return self.render("track_extension.html")

    @expose("/do_extend", methods=("POST",))
    def extend_tracks(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        This endpoint takes in these parameters:
        org_id (optional), track name, old length, and new length
        1. Create new tracks, and de-activate the old ones
        2. Migrate member tracks referencing old ones to the new ones
        3. Cancel any pending renewals for the member tracks that have been migrated
        """
        track_name = request.form.get("track_name")
        old_length = request.form.get("old_length")
        new_length = request.form.get("new_length")
        if not track_name:
            return {"error": "Track name required"}, 400
        track_name = TrackName[track_name.upper()]
        if not track_name:
            return {"error": "Track name not found"}, 400

        if old_length is not None:
            try:
                old_length = int(old_length)
            except ValueError:
                return {"error": "Invalid old length (not an integer)"}, 400
        else:
            return {"error": "Old length required"}, 400

        if new_length is not None:
            try:
                new_length = int(new_length)
            except ValueError:
                return {"error": "Invalid new length (not an integer)"}, 400
        else:
            return {"error": "New length required"}, 400

        if old_length >= new_length:
            return {"error": "Only support extension for track(s)"}, 400

        org_id = request.form.get("org_id")
        if org_id:
            try:
                org_id = int(org_id)
            except ValueError:
                return {"error": "Invalid org id (not an integer)"}, 400

        id_mapping = create_tracks(
            old_length, new_length, track_name, None, False, org_id  # type: ignore[arg-type] # Argument 4 to "create_tracks" has incompatible type "None"; expected "List[int]"
        )

        if not id_mapping:
            return {"error": "no such track found"}, 400

        # TODO: revert dry_run
        mt_ids = update_existing_member_tracks(id_mapping, True)
        terminate_pending_renewals(mt_ids, track_name, True)
        return "", 200

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
            MemberTrack,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
