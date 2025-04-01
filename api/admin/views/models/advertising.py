from typing import Type

from wtforms import validators

from admin.views.base import AdminCategory, AdminViewT, MavenAuditedView
from models.advertising import AutomaticCodeApplication
from models.referrals import ReferralCode
from storage.connection import RoutingSQLAlchemy, db


class AutomaticCodeApplicationView(MavenAuditedView):
    create_permission = "create:automatic-code-application"
    edit_permission = "edit:automatic-code-application"
    delete_permission = "delete:automatic-code-application"
    read_permission = "read:automatic-code-application"

    required_capability = "admin_automatic_code_application"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    column_sortable_list = ("created_at", "install_campaign")
    column_exclude_list = ("modified_at",)
    column_filters = ("install_campaign", ReferralCode.code, ReferralCode.id)

    form_excluded_columns = ["created_at", "modified_at"]
    form_ajax_refs = {"code": {"fields": ("code", "id"), "page_size": 10}}
    form_args = {"install_campaign": {"validators": (validators.DataRequired(),)}}

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
            AutomaticCodeApplication,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
