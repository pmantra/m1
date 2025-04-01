import dataclasses
from enum import Enum
from typing import Dict, List, Tuple

from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrgSettingCategoryAssociation,
    ReimbursementOrgSettingsExpenseType,
)


class FlashMessageCategory(str, Enum):
    INFO = "info"
    WARNING = "message"
    ERROR = "error"
    SUCCESS = "success"


@dataclasses.dataclass
class FlashMessage:
    """Wrapper for messages to be flashed in Admin"""

    __slots__ = ("message", "category")

    message: str
    category: FlashMessageCategory


def org_setting_expense_type_config_form_data(
    categories: List[ReimbursementOrgSettingCategoryAssociation],
    ros_expense_types: List[ReimbursementOrgSettingsExpenseType],
) -> Tuple[Dict, List[str]]:
    """
    Given a list of all org setting category associations and a list of all org settings expense types,
    we want to outer join both lists on expense type into a dict that we can display in admin.

    Errors to surface for ops to resolve:
    1) An org has a ReimbursementRequestCategoryExpenseType without a matching expense type
        in ReimbursementOrgSettingsExpenseType
    2) An org has a ReimbursementOrgSettingsExpenseType expense type without a matching
        ReimbursementRequestCategoryExpenseType
    3) There are multiple ReimbursementRequestCategoryExpenseType assigned to an org with the same expense type
        (There are db restrictions for ReimbursementOrgSettingsExpenseType)
    """
    form_data = {None: {"categories": []}}
    errors = []

    # Parse reimbursement request categories to add to forms
    for c in categories:
        category_data = {
            "reimbursement_category_id": c.reimbursement_request_category_id,
            "label": c.label,
        }
        category_expense_types = c.reimbursement_request_category.expense_types
        if category_expense_types:
            for et in category_expense_types:
                expense_type = et.name
                if expense_type in form_data:
                    # There are multiple RR categories mapped to an expense type, and should show an error
                    form_data[expense_type]["categories"].append(category_data)
                    errors.append(
                        f"Multiple reimbursement request categories mapped to expense type: {expense_type}"
                    )
                else:
                    form_data[expense_type] = {"categories": [category_data]}
        else:
            form_data[None]["categories"].append(category_data)

    # Parse reimbursement org settings expense types to add to forms
    for et in ros_expense_types:
        expense_type = et.expense_type.name
        et_data = {
            "ros_expense_type_id": et.id,
            "taxation_status": et.taxation_status and et.taxation_status.name,
            "reimbursement_method": et.reimbursement_method,
        }
        if expense_type in form_data:
            form_data[expense_type].update(et_data)
        else:
            # There are zero RR categories mapped to an expense type, and should show an error
            form_data[expense_type] = et_data
            errors.append(
                f"No reimbursement request category mapped to expense type: {expense_type}"
            )

    # Look for rr category expense types missing ros expense types
    for expense_type, data in form_data.items():
        if expense_type is not None and "ros_expense_type_id" not in data:
            errors.append(
                f"Expense type {expense_type} is missing a org settings expense type configuration"
            )

    return form_data, errors
