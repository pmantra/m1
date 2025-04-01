from __future__ import annotations

from typing import Type

from flask import flash

from admin.views.base import (
    AdminCategory,
    AdminViewT,
    AmountDisplayCentsInDollarsField,
    MavenAuditedView,
    cents_to_dollars_formatter,
)
from storage.connection import RoutingSQLAlchemy, db
from utils.log import logger
from wallet.models.reimbursement_organization_settings import (
    EmployerHealthPlan,
    EmployerHealthPlanCostSharing,
    EmployerHealthPlanCoverage,
    FertilityClinicLocationEmployerHealthPlanTier,
)

log = logger(__name__)


class EmployerHealthPlanView(MavenAuditedView):
    create_permission = "create:employer-health-plan"
    edit_permission = "edit:employer-health-plan"
    delete_permission = "delete:employer-health-plan"
    read_permission = "read:employer-health-plan"

    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    column_default_sort = ("id", True)
    column_list = (
        "id",
        "name",
        "reimbursement_organization_settings",
        "is_hdhp",
        "is_payer_not_integrated",
        "start_date",
        "end_date",
        "cost_sharings",
        "coverage",
        "rx_integrated",
        "group_id",
        "carrier_number",
        "benefits_payer",
        "hra_enabled",
    )

    column_labels = {
        "group_id": "Rx Group ID",
        "carrier_number": "Medical Group ID",
    }

    column_filters = (
        "id",
        "name",
        "reimbursement_org_settings_id",
    )

    form_excluded_columns = ("id", "created_at", "modified_at")

    form_columns = [
        "name",
        "reimbursement_organization_settings",
        "is_hdhp",
        "is_payer_not_integrated",
        "start_date",
        "end_date",
        "cost_sharings",
        "coverage",
        "group_id",
        "carrier_number",
        "rx_integrated",
        "group_id",
        "carrier_number",
        "benefits_payer_id",
        "hra_enabled",
    ]

    inline_models = (
        (
            EmployerHealthPlanCoverage,
            {
                "column_descriptions": {
                    "individual_deductible": """(Individual Deductible Limit)""",
                    "individual_oop": """(Individual Out-of-Pocket Limit)""",
                    "family_deductible": """(Family Deductible Limit)""",
                    "family_oop": """(Family Out-of-Pocket Limit)""",
                    "max_oop_per_covered_individual": """(Maximum Out-of-Pocket per covered Individual)""",
                    "tier": """(Tier should be left blank for non-tiered plans)""",
                    "plan_type": """(Plan type used to match with MemberHealthPlan plan type)""",
                },
                "form_columns": (
                    "id",
                    "individual_deductible",
                    "individual_oop",
                    "family_deductible",
                    "family_oop",
                    "max_oop_per_covered_individual",
                    "is_deductible_embedded",
                    "is_oop_embedded",
                    "plan_type",
                    "coverage_type",
                    "tier",
                ),
                "form_overrides": {
                    "individual_deductible": AmountDisplayCentsInDollarsField,
                    "individual_oop": AmountDisplayCentsInDollarsField,
                    "family_deductible": AmountDisplayCentsInDollarsField,
                    "family_oop": AmountDisplayCentsInDollarsField,
                    "max_oop_per_covered_individual": AmountDisplayCentsInDollarsField,
                },
            },
        ),
        (
            EmployerHealthPlanCostSharing,
            {
                "form_columns": (
                    "id",
                    "cost_sharing_type",
                    "cost_sharing_category",
                    "absolute_amount",
                    "percent",
                    "second_tier_absolute_amount",
                    "second_tier_percent",
                )
            },
        ),
        (
            FertilityClinicLocationEmployerHealthPlanTier,
            {
                "form_columns": (
                    "id",
                    "fertility_clinic_location",
                    "start_date",
                    "end_date",
                )
            },
        ),
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
            EmployerHealthPlan,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )

    def validate_form(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not form.rx_integrated.data and not form.group_id.data:
            flash(
                "Group ID cannot be blank for Non Rx Integrated Employer Health Plans.",
                "error",
            )
            return False
        return super().validate_form(form)


class EmployerHealthPlanCoverageView(MavenAuditedView):
    create_permission = "create:employer-health-plan-coverage"
    edit_permission = "edit:employer-health-plan-coverage"
    delete_permission = "delete:employer-health-plan-coverage"
    read_permission = "read:employer-health-plan-coverage"

    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    column_default_sort = ("id", True)
    column_list = (
        "id",
        "employer_health_plan",
        "individual_deductible",
        "individual_oop",
        "family_deductible",
        "family_oop",
        "max_oop_per_covered_individual",
        "is_deductible_embedded",
        "is_oop_embedded",
        "plan_type",
        "coverage_type",
        "tier",
    )
    column_labels = {
        "individual_deductible": "Individual Deductible ($)",
        "individual_oop": "Individual Out-of-pocket ($)",
        "family_deductible": "Family Deductible ($)",
        "family_oop": "Family Out-of-pocket ($)",
        "max_oop_per_covered_individual": "Max OOP Per Individual ($)",
        "plan_type": "Plan Type/Size",
        "coverage_type": "Type of Coverage",
    }

    column_formatters = {
        "individual_deductible": cents_to_dollars_formatter,
        "individual_oop": cents_to_dollars_formatter,
        "family_deductible": cents_to_dollars_formatter,
        "family_oop": cents_to_dollars_formatter,
        "max_oop_per_covered_individual": cents_to_dollars_formatter,
    }

    column_filters = (
        "id",
        EmployerHealthPlan.id,
        "tier",
    )

    form_overrides = {
        "ind_deductible_limit": AmountDisplayCentsInDollarsField,
        "ind_oop_max_limit": AmountDisplayCentsInDollarsField,
        "fam_deductible_limit": AmountDisplayCentsInDollarsField,
        "fam_oop_max_limit": AmountDisplayCentsInDollarsField,
        "max_oop_per_covered_individual": AmountDisplayCentsInDollarsField,
    }

    form_columns = (
        "id",
        "employer_health_plan",
        "individual_deductible",
        "individual_oop",
        "family_deductible",
        "family_oop",
        "max_oop_per_covered_individual",
        "is_deductible_embedded",
        "is_oop_embedded",
        "plan_type",
        "coverage_type",
        "tier",
    )

    form_widget_args = {
        "id": {"readonly": True},
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
            EmployerHealthPlanCoverage,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class EmployerHealthPlanCostSharingView(MavenAuditedView):
    create_permission = "create:employer-health-plan-cost-sharing"
    edit_permission = "edit:employer-health-plan-cost-sharing"
    delete_permission = "delete:employer-health-plan-cost-sharing"
    read_permission = "read:employer-health-plan-cost-sharing"

    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    column_default_sort = ("id", True)
    column_list = (
        "id",
        "employer_health_plan_id",
        "cost_sharing_type",
        "cost_sharing_category",
        "absolute_amount",
        "percent",
        "second_tier_absolute_amount",
        "second_tier_percent",
    )

    column_labels = {
        "absolute_amount": "Absolute Amount ($)",
        "second_tier_absolute_amount": "Second Tier Absolute Amount ($)",
    }

    column_filters = ("id", EmployerHealthPlan.id)

    column_formatters = {
        "absolute_amount": cents_to_dollars_formatter,
        "second_tier_absolute_amount": cents_to_dollars_formatter,
    }
    form_overrides = {
        "absolute_amount": AmountDisplayCentsInDollarsField,
        "second_tier_absolute_amount": AmountDisplayCentsInDollarsField,
    }

    form_columns = (
        "id",
        "employer_health_plan",
        "cost_sharing_type",
        "cost_sharing_category",
        "absolute_amount",
        "percent",
        "second_tier_absolute_amount",
        "second_tier_percent",
    )

    form_widget_args = {
        "id": {"readonly": True},
    }

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
            EmployerHealthPlanCostSharing,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
