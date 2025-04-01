import csv
import datetime
from unittest.mock import patch

from wallet.pytests.factories import (
    ReimbursementOrganizationSettingsFactory,
    ReimbursementOrgSettingCategoryAssociationFactory,
    ReimbursementRequestCategoryFactory,
)
from wallet.utils.alegeus.edi_processing.edi_record_imports import (
    create_file_list,
    format_ib_import_file,
    format_il_export_file,
    format_is_import_file,
    format_it_import_file,
    format_iu_import_file,
    format_iv_import_file,
)


def _add_org_settings(enterprise_user, plan=None, hdhp=None):
    org = enterprise_user.organization
    org.alegeus_employer_id = "MVNAB12"
    org_settings = ReimbursementOrganizationSettingsFactory(
        organization_id=enterprise_user.organization.id,
        organization=enterprise_user.organization,
        debit_card_enabled=True,
    )
    # Configure Reimbursement Plan
    if plan:
        category = ReimbursementRequestCategoryFactory.create(
            label="fertility", reimbursement_plan=plan
        )
        ReimbursementOrgSettingCategoryAssociationFactory.create(
            reimbursement_organization_settings=org_settings,
            reimbursement_request_category=category,
            reimbursement_request_category_maximum=5000,
        )
    if hdhp:
        category = ReimbursementRequestCategoryFactory.create(
            label="fertility", reimbursement_plan=hdhp
        )
        ReimbursementOrgSettingCategoryAssociationFactory.create(
            reimbursement_organization_settings=org_settings,
            reimbursement_request_category=category,
            reimbursement_request_category_maximum=5000,
        )

    return org


def banking_info(org, payroll_only=False):
    return {
        "org_id": org.id,
        "bank_account_usage_code": "3",
        "financial_institution": "Test Bank",
        "account_number": "123456789",
        "routing_number": "234567891",
        "payroll_only": payroll_only,
    }


def test_format_il_export_file__success(enterprise_user):
    _add_org_settings(enterprise_user)
    today = datetime.datetime.now().strftime("%Y%m%d")
    filename, csv_contents = format_il_export_file(None, None, None)
    export_csv = list(csv.reader(csv_contents.split("\n"), delimiter=","))
    header = export_csv[0]
    export_row_en = export_csv[1]
    export_row_em = export_csv[2]
    export_row_ek = export_csv[3]

    assert header[0] == "IA"
    assert header[1] == "4"  # How many records are being sent over including the header
    assert export_row_en[3] == "EN"
    assert export_row_em[3] == "EM"
    assert export_row_ek[3] == "EK"
    assert filename == f"MAVENIL{today}.mbi"


def test_format_il_export_variable_dates(enterprise_user):
    _add_org_settings(enterprise_user)
    today = datetime.datetime.now()
    filter_from = today - datetime.timedelta(days=5)
    filename, csv_contents = format_il_export_file(None, filter_from, today)
    export_csv = list(csv.reader(csv_contents.split("\n"), delimiter=","))
    header = export_csv[0]
    export_row_en = export_csv[1]
    export_row_em = export_csv[2]
    export_row_ek = export_csv[3]

    today_file = today.strftime("%Y%m%d")

    assert header[0] == "IA"
    assert header[1] == "4"  # How many records are being sent over including the header
    assert export_row_en[3] == "EN"
    assert export_row_em[3] == "EM"
    assert export_row_ek[3] == "EK"
    assert export_row_en[4] == filter_from.strftime("%Y%m%d")
    assert export_row_en[5] == today.strftime("%Y%m%d")
    assert filename == f"MAVENIL{today_file}.mbi"


def test_format_is_import_file(enterprise_user):
    org = _add_org_settings(enterprise_user)
    filename, csv_contents = format_is_import_file([org.id])
    export_csv = list(csv.reader(csv_contents.split("\n"), delimiter=","))
    header = export_csv[0]
    export_row_data = export_csv[1]

    assert len(export_row_data) == 35
    assert header[1] == "2"  # rows sent
    assert (
        export_row_data[3] == org.alegeus_employer_id[3:]
    )  # checking the prefix MVN was removed for this file
    assert filename == f"MAVEN_IS_{org.id}.mbi"


def test_format_it_import_file(enterprise_user):
    org = _add_org_settings(enterprise_user)
    filename, csv_contents = format_it_import_file([org.id])
    export_csv = list(csv.reader(csv_contents.split("\n"), delimiter=","))
    header = export_csv[0]
    export_row_data = export_csv[1]

    assert len(export_row_data) == 11
    assert header[1] == "2"  # rows sent
    assert filename == f"MAVEN_IT_{org.id}.mbi"


def test_format_iu_import_file(
    enterprise_user,
    valid_alegeus_plan_hra,
    valid_alegeus_account_hdhp,
    valid_alegeus_plan_hdhp,
):
    # Setup for HRA and DTR
    org = _add_org_settings(
        enterprise_user, valid_alegeus_plan_hra, valid_alegeus_plan_hdhp
    )

    filename, csv_contents = format_iu_import_file([org.id])
    export_csv = list(csv.reader(csv_contents.split("\n"), delimiter=","))
    header = export_csv[0]
    export_row_data = export_csv[1]

    assert len(export_row_data) == 23
    assert header[1] == "3"  # rows sent
    assert filename == f"MAVEN_IU_{org.id}.mbi"


def test_format_iv_import_file(enterprise_user):
    org = _add_org_settings(enterprise_user)
    filename, csv_contents = format_iv_import_file([org.id])
    export_csv = list(csv.reader(csv_contents.split("\n"), delimiter=","))
    header = export_csv[0]
    export_row_data = export_csv[1]

    assert len(export_row_data) == 12
    assert header[1] == "2"  # rows sent
    assert export_row_data[5] == ""  # No bank account information set
    assert filename == f"MAVEN_IV_{org.id}.mbi"


def test_format_iv_import_file_with_banking(enterprise_user):
    org = _add_org_settings(enterprise_user)
    banking_information = banking_info(org)
    filename, csv_contents = format_iv_import_file([org.id], banking_information)
    export_csv = list(csv.reader(csv_contents.split("\n"), delimiter=","))
    header = export_csv[0]
    export_row_data = export_csv[1]

    assert len(export_row_data) == 12
    assert header[1] == "2"  # rows sent
    assert export_row_data[5] == "123456789"
    assert filename == f"MAVEN_IV_{org.id}.mbi"


def test_format_ib_import_file(
    qualified_alegeus_wallet_hra,
    factories,
    eligibility_factories,
    faker,
    enterprise_user,
):
    address = factories.AddressFactory(
        user=qualified_alegeus_wallet_hra.member,
        state="PE",
        zip_code="C0A1N0",
        country="CA",
    )
    e9y_member = eligibility_factories.EligibilityMemberFactory.create(
        id=1,
        organization_id=qualified_alegeus_wallet_hra.reimbursement_organization_settings.organization_id,
        date_of_birth=faker.date_of_birth(),
    )
    with patch(
        "eligibility.e9y.grpc_service.member_id_search"
    ) as member_id_search_mock:
        member_id_search_mock.return_value = e9y_member
        _, csv_contents = format_ib_import_file(
            qualified_alegeus_wallet_hra, enterprise_user.id
        )
        export_csv = list(csv.reader(csv_contents.split("\n"), delimiter=","))
        header = export_csv[0]
        export_row_data = export_csv[1]

    assert header[1] == "2"  # rows sent
    assert export_row_data[-3] == address.state


def test_create_file_list_without_payroll(enterprise_user):
    org = _add_org_settings(enterprise_user)
    banking_information = banking_info(org)
    files = create_file_list([org.id], banking_information)
    assert len(files) == 4


def test_create_file_list_with_payroll(enterprise_user):
    org = _add_org_settings(enterprise_user)
    banking_information = banking_info(org, payroll_only=True)
    files = create_file_list([org.id], banking_information)
    assert len(files) == 3
