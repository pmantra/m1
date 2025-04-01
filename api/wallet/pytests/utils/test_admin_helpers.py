from unittest import mock

from wallet.models.constants import (
    ReimbursementRequestExpenseTypes,
    TaxationStateConfig,
    WalletState,
)
from wallet.pytests.factories import (
    ReimbursementOrgSettingsExpenseTypeFactory,
    ReimbursementRequestCategoryExpenseTypesFactory,
    ReimbursementWalletFactory,
)
from wallet.utils.admin_helpers import org_setting_expense_type_config_form_data


def test_organization_expense_type_data_format():
    labels_with_max_and_currency_code = [
        ("label_1", None, None),
        ("label_2", None, None),
    ]
    wallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings__allowed_reimbursement_categories=labels_with_max_and_currency_code,
        state=WalletState.QUALIFIED,
    )
    ros_et_1 = ReimbursementOrgSettingsExpenseTypeFactory.create(
        reimbursement_organization_settings_id=wallet.reimbursement_organization_settings_id,
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
        taxation_status=TaxationStateConfig.SPLIT_DX_INFERTILITY,
    )
    ros_et_2 = ReimbursementOrgSettingsExpenseTypeFactory.create(
        reimbursement_organization_settings_id=wallet.reimbursement_organization_settings_id,
        expense_type=ReimbursementRequestExpenseTypes.PRESERVATION,
        taxation_status=TaxationStateConfig.NON_TAXABLE,
    )
    ros_et_3 = ReimbursementOrgSettingsExpenseTypeFactory.create(
        reimbursement_organization_settings_id=wallet.reimbursement_organization_settings_id,
        expense_type=ReimbursementRequestExpenseTypes.ADOPTION,
        taxation_status=TaxationStateConfig.ADOPTION_QUALIFIED,
    )
    ros_ets = [ros_et_1, ros_et_2, ros_et_3]
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category_id=wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category_id,
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
    )
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category_id=wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            1
        ].reimbursement_request_category_id,
        expense_type=ReimbursementRequestExpenseTypes.PRESERVATION,
    )
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category_id=wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            1
        ].reimbursement_request_category_id,
        expense_type=ReimbursementRequestExpenseTypes.ADOPTION,
    )
    categories = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories
    )
    expense_type_data, errors = org_setting_expense_type_config_form_data(
        categories, ros_ets
    )
    assert len(errors) == 0
    assert expense_type_data == {
        None: {"categories": []},
        "ADOPTION": {
            "categories": [{"label": "label_2", "reimbursement_category_id": mock.ANY}],
            "reimbursement_method": None,
            "ros_expense_type_id": mock.ANY,
            "taxation_status": "ADOPTION_QUALIFIED",
        },
        "PRESERVATION": {
            "categories": [{"label": "label_2", "reimbursement_category_id": mock.ANY}],
            "reimbursement_method": None,
            "ros_expense_type_id": mock.ANY,
            "taxation_status": "NON_TAXABLE",
        },
        "FERTILITY": {
            "categories": [{"label": "label_1", "reimbursement_category_id": mock.ANY}],
            "reimbursement_method": None,
            "ros_expense_type_id": mock.ANY,
            "taxation_status": "SPLIT_DX_INFERTILITY",
        },
    }


def test_organization_expense_type_data_format_with_errors():
    labels_with_max_and_currency_code = [
        ("label_1", None, None),
        ("label_2", None, None),
    ]
    wallet = ReimbursementWalletFactory.create(
        reimbursement_organization_settings__allowed_reimbursement_categories=labels_with_max_and_currency_code,
        state=WalletState.QUALIFIED,
    )
    ros_et_1 = ReimbursementOrgSettingsExpenseTypeFactory.create(
        reimbursement_organization_settings_id=wallet.reimbursement_organization_settings_id,
        expense_type=ReimbursementRequestExpenseTypes.PRESERVATION,
        taxation_status=TaxationStateConfig.NON_TAXABLE,
    )
    ros_et_2 = ReimbursementOrgSettingsExpenseTypeFactory.create(
        reimbursement_organization_settings_id=wallet.reimbursement_organization_settings_id,
        expense_type=ReimbursementRequestExpenseTypes.ADOPTION,
        taxation_status=TaxationStateConfig.ADOPTION_QUALIFIED,
    )
    ros_ets = [ros_et_1, ros_et_2]
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category_id=wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            0
        ].reimbursement_request_category_id,
        expense_type=ReimbursementRequestExpenseTypes.FERTILITY,
    )
    ReimbursementRequestCategoryExpenseTypesFactory.create(
        reimbursement_request_category_id=wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
            1
        ].reimbursement_request_category_id,
        expense_type=ReimbursementRequestExpenseTypes.PRESERVATION,
    )
    categories = (
        wallet.reimbursement_organization_settings.allowed_reimbursement_categories
    )
    expense_type_data, errors = org_setting_expense_type_config_form_data(
        categories, ros_ets
    )
    assert len(errors) == 2
    assert errors == [
        "No reimbursement request category mapped to expense type: ADOPTION",
        "Expense type FERTILITY is missing a org settings expense type configuration",
    ]
    assert expense_type_data == {
        None: {"categories": []},
        "ADOPTION": {
            "reimbursement_method": None,
            "ros_expense_type_id": mock.ANY,
            "taxation_status": "ADOPTION_QUALIFIED",
        },
        "PRESERVATION": {
            "categories": [{"label": "label_2", "reimbursement_category_id": mock.ANY}],
            "reimbursement_method": None,
            "ros_expense_type_id": mock.ANY,
            "taxation_status": "NON_TAXABLE",
        },
        "FERTILITY": {
            "categories": [{"label": "label_1", "reimbursement_category_id": mock.ANY}]
        },
    }
