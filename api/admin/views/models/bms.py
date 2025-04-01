import datetime
from typing import Type

from flask import Response, flash
from flask_admin.actions import action
from wtforms import fields

from admin.views.base import (
    USER_AJAX_REF,
    AdminCategory,
    AdminViewT,
    ManyToOneInlineForm,
    MavenAdminView,
    MavenAuditedView,
    PerInlineModelConverterMixin,
)
from audit_log.utils import (
    emit_audit_log_read,
    emit_bulk_audit_log_read,
    emit_bulk_audit_log_update,
)
from bms.models.bms import (
    BMSOrder,
    BMSProduct,
    BMSShipment,
    BMSShipmentProducts,
    OrderStatus,
)
from bms.utils.bms import generate_bms_orders_csv
from models.profiles import Address
from models.tracks import MemberTrack
from storage.connection import RoutingSQLAlchemy, db
from tracks import service as tracks_svc
from utils.braze_events import send_bms_tracking_email
from utils.log import logger

INDICIA_ITEM_NUMBERS = {
    "pump_and_post": "2-85228-K",
    "pump_and_carry": "S-21606-K",
    "pump_and_check": "231564-K",
}

log = logger(__name__)


class BMSShipmentView(PerInlineModelConverterMixin, MavenAdminView):
    form_columns = [
        "recipient_name",
        "friday_shipping",
        "residential_address",
        "shipped_at",
        "shipment_method",
        "tracking_numbers",
        "tracking_email",
        "accommodation_name",
        "cost",
        "tel_number",
        "tel_region",
        "products",
        "address",
    ]
    column_labels = {
        "friday_shipping": "Friday Shipping (ignore for Shipment #1)",
        "shipment_method": "Shipping Method",
    }

    inline_models = (
        (BMSShipmentProducts, {"form_excluded_columns": ("created_at", "modified_at")}),
        ManyToOneInlineForm(
            Address, form_excluded_columns=("user", "modified_at", "created_at")
        ),
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
            BMSShipment,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class BMSOrderView(PerInlineModelConverterMixin, MavenAuditedView):
    read_permission = "read:bms-order"
    edit_permission = "edit:bms-order"
    create_permission = "create:bms-order"
    delete_permission = "delete:bms-order"

    audit_model_view = True  # type: ignore[assignment] # Incompatible types in assignment (expression has type "bool", base class "MavenAuditedView" defined the type as "None")
    list_template = "process_bms_orders.html"
    column_default_sort = ("id", True)
    column_display_pk = True
    column_filters = (
        "id",
        "created_at",
        "fulfilled_at",
        "is_work_travel",
        "is_maven_in_house_fulfillment",
        "status",
        "cancellation_reason",
        "travel_start_date",
        "user.first_name",
        "user.last_name",
        "user.email",
        "user.id",
    )
    column_list = (
        "id",
        "user.id",
        "user.email",
        "user.full_name",
        "is_work_travel",
        "is_maven_in_house_fulfillment",
        "status",
        "cancellation_reason",
        "travel_start_date",
        "created_at",
        "fulfilled_at",
        "first_shipped_at",
        "organization_name",
    )
    column_sortable_list = (
        "id",
        "user.id",
        "user.email",
        "travel_start_date",
        "status",
        "created_at",
        "fulfilled_at",
        "first_shipped_at",
    )

    form_columns = (
        "id",
        "user",
        "created_at",
        "fulfilled_at",
        "is_maven_in_house_fulfillment",
        "status",
        "cancellation_reason",
        "travel_start_date",
        "travel_end_date",
        "shipments",
    )
    form_ajax_refs = {"user": USER_AJAX_REF}
    form_widget_args = {
        "id": {"readonly": True},
        "created_at": {"readonly": True},
    }

    _inline_models = None

    @property
    def inline_models(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if self._inline_models is None:
            self._inline_models = (BMSShipmentView(BMSShipment, self.session),)
        return self._inline_models

    def _get_org_name(view, context, model, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # Note: organization_employee will be deprecated, use eligibility verification record instead
        # check verification record instead of organization_employee

        user = model.user
        track_svc = tracks_svc.TrackSelectionService()
        organization = track_svc.get_organization_for_user(user_id=user.id)
        if not organization:
            log.warning(
                "Failed to get organization associated with eligibility verification record for the user"
            )

        # check if the user is in an active member_track
        is_active = (
            db.session.query(MemberTrack)
            .filter(MemberTrack.user_id == user.id)
            .filter(MemberTrack.active == True)
        )
        if is_active and organization:
            emit_audit_log_read(organization)
            return organization.marketing_name
        return None

    column_formatters = {"organization_name": _get_org_name}

    @action("mark_fulfilled", "Mark as fulfilled", "You Sure?")
    def mark_fulfilled(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        now = datetime.datetime.utcnow()
        orders = db.session.query(BMSOrder).filter(BMSOrder.id.in_(ids)).all()
        for order in orders:
            order.fulfilled_at = now
            order.status = OrderStatus.FULFILLED
        emit_bulk_audit_log_update(orders)
        db.session.commit()

    @action("mark_unfulfilled", "Mark as unfulfilled", "You Sure?")
    def mark_unfulfilled(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        orders = db.session.query(BMSOrder).filter(BMSOrder.id.in_(ids)).all()
        for order in orders:
            order.fulfilled_at = None
            order.status = OrderStatus.NEW
        emit_bulk_audit_log_update(orders)
        db.session.commit()

    @action("generate_csv", "Generate Orders CSV")
    def generate_csv(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        orders = db.session.query(BMSOrder).filter(BMSOrder.id.in_(ids)).all()
        emit_bulk_audit_log_read(orders)
        report = generate_bms_orders_csv(orders)
        response = Response(report)

        filename = (
            f"bms-orders-{datetime.datetime.now().strftime('%y_%m_%d-%H_%M_%S')}.csv"
        )
        response.headers["Content-Description"] = "File Transfer"
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Content-Type"] = "text/csv"
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"

        return response

    def get_create_form(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        form = self.scaffold_form()
        delattr(form, "id")
        return form

    def after_model_change(self, form, model, is_created):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().after_model_change(form, model, is_created)
        old_status = (
            form.status.object_data if is_created else form.status.object_data.value
        )
        new_status = form.status.data

        if new_status != old_status and new_status == OrderStatus.FULFILLED.value:
            shipments = model.shipments
            try:
                first_shipment = shipments[0]
                first_product = first_shipment.products[0]
                product = first_product.bms_product
                if product.name == "pump_and_post":
                    if len(shipments) == 2:
                        second_shipment = shipments[1]
                        to_hotel_tracking = first_shipment.tracking_numbers
                        to_home_tracking = second_shipment.tracking_numbers
                        if to_hotel_tracking is None or to_home_tracking is None:
                            flash(
                                "No Braze email was sent. In order to send email each shipment must have a tracking "
                                "number."
                            )
                            return
                    else:
                        flash("Pump and post product must have 2 shipments.")
                        return
            except IndexError:
                index_error_msg = (
                    "No Braze email was sent. In order to send email each shipment and product must be available. Make "
                    "sure shipments and/or products are available."
                )
                flash(index_error_msg)
                return
            except TypeError:
                none_type_error_msg = (
                    "No Braze email was sent. In order to send email make sure shipments or "
                    "products are available. "
                )
                flash(none_type_error_msg)
                return

            send_bms_tracking_email(shipments, product, model)
            flash("Successfully triggered BMS email.")

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
            BMSOrder,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class BMSProductView(MavenAuditedView):
    read_permission = "read:bms-product"
    edit_permission = "edit:bms-product"
    create_permission = "create:bms-product"
    delete_permission = "delete:bms-product"

    audit_model_view = True  # type: ignore[assignment] # Incompatible types in assignment (expression has type "bool", base class "MavenAuditedView" defined the type as "None")

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
            BMSProduct,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
