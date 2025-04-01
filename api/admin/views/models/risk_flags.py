from __future__ import annotations

from typing import Type

from admin.views.base import (
    AdminCategory,
    AdminViewT,
    MavenAuditedView,
    ReadOnlyFieldRule,
)
from health.data_models.risk_flag import RiskFlag
from storage.connection import RoutingSQLAlchemy, db
from utils.log import logger

log = logger(__name__)


class RiskFlagView(MavenAuditedView):
    read_permission = "read:user-flag"
    create_permission = "create:user-flag"
    edit_permission = "edit:user-flag"

    required_capability = "admin_user_flag"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    column_searchable_list = ("name",)

    editable_columns = (
        "name",
        "severity",
        "ecp_qualifier_type",
        "is_mental_health",
        "is_physical_health",
        "relevant_to_maternity",
        "relevant_to_fertility",
        "is_utilization",
        "is_situational",
        "is_ttc_and_treatment",
        "uses_value",
        "value_unit",
        "ecp_program_qualifier",
        "is_chronic_condition",
    )
    column_list = editable_columns + (
        "created_at",
        "modified_at",
    )
    column_sortable_list = column_list
    column_filters = ("id",) + column_list
    form_columns = ("id", "created_at", "modified_at") + editable_columns
    form_edit_rules = (
        ReadOnlyFieldRule("ID", lambda risk_flag: risk_flag.id),
        ReadOnlyFieldRule("Created", lambda risk_flag: risk_flag.created_at),
        ReadOnlyFieldRule("Modified", lambda risk_flag: risk_flag.modified_at),
    ) + editable_columns

    can_export = True
    page_size = 300

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
            RiskFlag,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
