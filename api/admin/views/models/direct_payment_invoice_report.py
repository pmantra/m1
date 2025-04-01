from typing import Type

from flask import url_for
from markupsafe import Markup
from sqlalchemy.engine import ResultProxy
from sqlalchemy.orm import Query

from admin.views.base import AdminCategory, AdminViewT, MavenAuditedView
from direct_payment.invoicing.invoicing_service import DirectPaymentInvoicingService
from direct_payment.invoicing.models import OrgDirectPaymentInvoiceReport
from storage.connection import db
from storage.connector import RoutingSQLAlchemy


def _format_ros_invoice_ids(view, context, model, name) -> Markup:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    ros_invoice_ids = str(model.ros_invoice_ids)
    to_return = ""
    if ros_invoice_ids and (ros_invoice_ids_list := ros_invoice_ids.split(",")):
        ros_invoice_id_urls = [
            f'<a href="{url_for("directpaymentinvoice.details_view", id=ros_invoice_id)}" target="_blank">{ros_invoice_id}</a>'
            for ros_invoice_id in ros_invoice_ids_list
        ]
        to_return += ", ".join(ros_invoice_id_urls)
    return Markup(to_return)


class DirectPaymentInvoiceReportView(MavenAuditedView):
    def __init__(self, model, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().__init__(model, *args, **kwargs)
        self._invoice_service = DirectPaymentInvoicingService(session=db.session)

    read_permission = "read:direct-payment-invoice-report"

    column_filters = [
        "organization_id",
        "organization_name",
    ]

    # sort in descending order by cutoff start date and ascending order by organization id
    column_default_sort = [
        ("bill_creation_cutoff_start_at", True),
        ("organization_id", False),
    ]

    column_sortable_list = (
        "organization_id",
        "organization_name",
        "bill_creation_cutoff_start_at",
        "bill_creation_cutoff_end_at",
    )

    column_formatters = {"ros_invoice_ids": _format_ros_invoice_ids}

    def get_query(self) -> Query:
        return self._invoice_service.get_org_level_invoice_report_data_query()

    def get_count_query(self) -> ResultProxy:
        return self._invoice_service.get_org_level_invoice_report_count_query()

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
            # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            OrgDirectPaymentInvoiceReport,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
