from typing import Type

from wtforms import validators

from admin.views.base import USER_AJAX_REF, AdminCategory, AdminViewT, MavenAuditedView
from models.referrals import (
    ReferralCode,
    ReferralCodeCategory,
    ReferralCodeSubCategory,
    ReferralCodeValue,
)
from storage.connection import RoutingSQLAlchemy, db


class ReferralCodeView(MavenAuditedView):
    required_capability = "admin_referral_codes"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    create_permission = "create:referral-code"
    edit_permission = "edit:referral-code"
    delete_permission = "delete:referral-code"
    read_permission = "read:referral-code"

    edit_template = "referral_code_edit_template.html"

    column_exclude_list = ("id", "user", "description", "modified_at")
    column_sortable_list = ("expires_at", "allowed_uses", "created_at")
    column_filters = ("user.email", "category_name", "subcategory_name")
    column_searchable_list = ("code",)

    form_rules = [
        "user",
        "code",
        "expires_at",
        "allowed_uses",
        "only_use_before_booking",
        "values",
        "activity",
        "total_code_cost",
        "subcategory",
    ]
    form_excluded_columns = ["uses"]
    form_ajax_refs = {"user": USER_AJAX_REF}
    form_args = {"subcategory": {"validators": [validators.DataRequired()]}}

    inline_models = (
        (
            ReferralCodeValue,
            {
                "form_columns": (
                    "id",
                    "for_user_type",
                    "value",
                    "expires_at",
                    "payment_rep",
                    "rep_email_address",
                    "payment_user",
                    "user_payment_type",
                )
            },
        ),
    )

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        for value in model.values:
            if not value.value and not (value.user_payment_type and value.payment_user):
                raise validators.ValidationError(
                    "Must specify a value or payment user/user payment type"
                )
        super().on_model_change(form, model, is_created)

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
            ReferralCode,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ReferralCodeCategoryView(MavenAuditedView):
    required_capability = "admin_referral_codes"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    create_permission = "create:referral-code-category"
    read_permission = "read:referral-code-category"

    column_display_pk = True
    form_columns = ("name",)

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
            ReferralCodeCategory,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class ReferralCodeSubCategoryView(MavenAuditedView):
    required_capability = "admin_referral_codes"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    create_permission = "create:referral-code-sub-category"
    read_permission = "read:referral-code-sub-category"

    form_columns = ("category", "name")
    column_list = ("category_name", "name")

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
            ReferralCodeSubCategory,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )
