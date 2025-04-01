from typing import Type

from admin.views.base import AdminCategory, AdminViewT, MavenAuditedView
from health.data_models.member_risk_flag import MemberRiskFlag
from storage.connection import RoutingSQLAlchemy, db


# Readonly View to view/search MemberRiskFlags.
# To Edit, use the Member Profile -> Risk Flags -> Add Risk / Remove Risk features
class MemberRiskFlagView(MavenAuditedView):
    read_permission = "read:user-flag"
    create_permission = "create:user-flag"
    edit_permission = "edit:user-flag"
    delete_permission = "delete:user-flag"

    list_template = "member_risk_flag_list.html"

    required_capability = "admin_user_flag"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")
    column_searchable_list = (
        "user_id",
        "risk_flag.name",
    )

    column_list = (
        "id",
        "user_id",
        "risk_flag.name",
        "value",
        "start",
        "end",
        "confirmed_at",
        "modified_by",
        "modified_reason",
    )
    column_sortable_list = column_list
    column_filters = column_list

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
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" Unexpected keyword argument "category" for "object" Unexpected keyword argument "name" for "object"  Unexpected keyword argument "endpoint" for "object"
            MemberRiskFlag,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
