from typing import Type

from flask_admin.contrib.sqla.filters import FilterLike

from admin.views.base import USER_AJAX_REF, AdminCategory, AdminViewT, MavenAuditedView
from authn.models.user import User
from models.products import Product
from models.verticals_and_specialties import Vertical
from storage.connection import RoutingSQLAlchemy, db


class ProductView(MavenAuditedView):
    read_permission = "read:product"
    delete_permission = "delete:product"
    create_permission = "create:product"
    edit_permission = "edit:product"

    column_list = (
        "id",
        "practitioner.full_name",
        "minutes",
        "price",
        "is_active",
        "vertical.name",
    )
    column_labels = {
        "practitioner.full_name": "Practitioner",
        "vertical.name": "Vertical",
    }
    column_sortable_list = ("created_at", "practitioner", "minutes", "price")
    column_exclude_list = ("modified_at", "description")
    column_filters = (
        User.id,
        User.email,
        User.last_name,
        FilterLike(column=Vertical.name, name="Vertical"),
    )

    form_excluded_columns = ["appointments"]
    form_ajax_refs = {"practitioner": USER_AJAX_REF}

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
            Product,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
