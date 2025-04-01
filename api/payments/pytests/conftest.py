import io
from datetime import date, datetime, timedelta
from typing import List

import pytest
from sqlalchemy import func
from werkzeug.datastructures import FileStorage

from authn.models.user import User
from models.profiles import PractitionerProfile
from payments.pytests.factories import (
    ContractValidatorFactory,
    PractitionerContractFactory,
)
from pytests.factories import CreditFactory
from storage.connection import db


@pytest.fixture()
def today():
    today = date.today()
    return today


@pytest.fixture()
def yesterday(today):
    yesterday = today - timedelta(days=1)
    return yesterday


@pytest.fixture()
def tomorrow(today):
    tomorrow = today + timedelta(days=1)
    return tomorrow


@pytest.fixture()
def jan_1st_this_year(today):
    jan_1st_this_year = date(year=today.year, month=1, day=1)
    return jan_1st_this_year


@pytest.fixture()
def jan_2nd_this_year(today):
    jan_2nd_this_year = date(year=today.year, month=1, day=2)
    return jan_2nd_this_year


@pytest.fixture()
def jan_31st_this_year(today):
    jan_31st_this_year = date(year=today.year, month=1, day=31)
    return jan_31st_this_year


@pytest.fixture()
def feb_1st_this_year(today):
    feb_1st_this_year = date(year=today.year, month=2, day=1)
    return feb_1st_this_year


@pytest.fixture()
def march_1st_this_year(today):
    march_1st_this_year = date(year=today.year, month=3, day=1)
    return march_1st_this_year


@pytest.fixture()
def march_31st_this_year(today):
    march_31st_this_year = date(year=today.year, month=3, day=31)
    return march_31st_this_year


@pytest.fixture()
def apr_1st_this_year(today):
    apr_1st_this_year = date(year=today.year, month=4, day=1)
    return apr_1st_this_year


@pytest.fixture()
def apr_30th_this_year(today):
    apr_30th_this_year = date(year=today.year, month=4, day=30)
    return apr_30th_this_year


@pytest.fixture()
def practitioner_contract(factories, default_user):
    prac_profile = factories.PractitionerProfileFactory.create(user=default_user)
    practitioner_contract = PractitionerContractFactory.create(
        practitioner=prac_profile
    )
    return practitioner_contract


@pytest.fixture()
def practitioner_profile(factories):
    practitioner = factories.PractitionerUserFactory()
    return practitioner.practitioner_profile


@pytest.fixture()
def practitioner_id(practitioner_profile):
    return practitioner_profile.user_id


@pytest.fixture()
def practitioner_id_for_inactive_practitioner(practitioner_profile):
    practitioner_profile.active = False
    return practitioner_profile.user_id


@pytest.fixture()
def invalid_user_id(today):
    # TODO: get this max_id through UserService
    max_id = db.session.query(func.max(User.id)).first()[0]
    if max_id:
        return max_id + 1
    return 1


@pytest.fixture()
def invalid_prac_id(today):
    max_id = db.session.query(func.max(PractitionerProfile.user_id)).first()[0]
    if max_id:
        return max_id + 1
    return 1


@pytest.fixture()
def contract_validator():
    contract_validator = ContractValidatorFactory.create()
    return contract_validator


def create_csv_file_for_practitioner_contract(
    data_rows: List[str] = None,
    headers_row="created_by_id,practitioner_id,contract_type,contract_start_date,contract_end_date,hourly_rate,hours_per_week,rate_per_overnight_appt,hourly_appt_rate,message_rate",
) -> FileStorage:

    contract_csv_filename = "contracts_file.csv"

    csv_data = headers_row
    if data_rows is not None:
        for data_row in data_rows:
            csv_data = csv_data + "\n" + data_row
    csv_data_in_bytes = bytes(csv_data, "utf-8")

    stream = io.BytesIO(csv_data_in_bytes)

    csvfile_filestorage = FileStorage(
        content_type="text/csv",
        filename=contract_csv_filename,
        name=contract_csv_filename,
        content_length=0,
        stream=stream,
    )
    return csvfile_filestorage


@pytest.fixture
def practitioner_contracts_csv__valid(factories, default_user):
    user_id = default_user.id
    prac_1 = factories.PractitionerUserFactory()
    prac_2 = factories.PractitionerUserFactory()
    prac_3 = factories.PractitionerUserFactory()
    profile_1 = factories.PractitionerProfileFactory.create(user=prac_1)
    profile_1.is_staff = True
    profile_2 = factories.PractitionerProfileFactory.create(user=prac_2)
    profile_2.is_staff = False
    profile_3 = factories.PractitionerProfileFactory.create(user=prac_3)
    profile_3.is_staff = True
    prac_1_id = prac_1.id
    prac_2_id = prac_2.id
    prac_3_id = prac_3.id
    valid_data_row_1 = (
        f"{user_id},{prac_1_id},Fixed hourly,2017-10-01,2022-01-31,45,10,,,"
    )
    valid_data_row_2 = f"{user_id},{prac_2_id},By appointment,2020-06-01,,,,,,"
    valid_data_row_3 = (
        f"{user_id},{prac_3_id},Fixed Hourly Overnight,2022-01-01,,30,145,300,,,"
    )
    csv_file = create_csv_file_for_practitioner_contract(
        [valid_data_row_1, valid_data_row_2, valid_data_row_3]
    )
    return {
        "csv_file": csv_file,
        "prac_id_1": prac_1_id,
        "prac_id_2": prac_2_id,
        "prac_id_3": prac_3_id,
    }


@pytest.fixture
def practitioner_contracts_csv__invalid_contracts(factories, default_user):
    user_id = default_user.id
    prac_1 = factories.PractitionerUserFactory()
    prac_2 = factories.PractitionerUserFactory()
    prac_1_id = prac_1.id
    prac_2_id = prac_2.id
    valid_data_row = (
        f"{user_id},{prac_1_id},Fixed hourly,2017-10-01,2022-01-31,45,10,,,"
    )
    invalid_data_row = (
        f"{user_id},{prac_2_id},Fixed hourly,2017-10-17,2022-01-31,45,10,,,"
    )
    csv_file = create_csv_file_for_practitioner_contract(
        data_rows=[invalid_data_row, valid_data_row]
    )
    return {"csv_file": csv_file, "prac_id_1": prac_1_id, "prac_id_2": prac_2_id}


@pytest.fixture
def practitioner_contracts_csv__no_contracts():
    return create_csv_file_for_practitioner_contract(data_rows=None)


@pytest.fixture
def practitioner_contracts_csv__empty_file():
    contract_csv_filename = "contracts_file.csv"
    return FileStorage(
        content_type="text/csv",
        filename=contract_csv_filename,
        name=contract_csv_filename,
        content_length=0,
        stream=None,
    )


@pytest.fixture
def practitioner_contracts_csv__invalid_data():
    data_row = "x,x,x,x,x,x,x,x,x,x"
    return create_csv_file_for_practitioner_contract(data_rows=data_row)


@pytest.fixture
def practitioner_contracts_csv__missing_headers():
    return create_csv_file_for_practitioner_contract(
        headers_row="created_by_id,practitioner_id,contract_type,contract_start_date,contract_end_date,hourly_rate,"
    )


@pytest.fixture
def new_credit():
    def make_new_credit(appointment_id, user, amount=0, used_at=None):
        return CreditFactory.create(
            amount=amount,
            used_at=used_at,
            appointment_id=appointment_id,
            user=user,
        )

    return make_new_credit


@pytest.fixture(scope="function")
def enterprise_user(factories):
    return factories.EnterpriseUserFactory.create()


@pytest.fixture
def datetime_now():
    return datetime.utcnow().replace(microsecond=0)


@pytest.fixture
def datetime_one_hour_earlier(datetime_now):
    return datetime_now - timedelta(hours=1)
