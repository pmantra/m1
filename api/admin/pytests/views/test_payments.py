import csv
import datetime
from io import BytesIO, StringIO

import pytest
from dateutil.relativedelta import relativedelta


@pytest.fixture
def csv_fixture():
    def make_csv_data(data):
        csv_stream = StringIO()
        csv.writer(csv_stream).writerows(data)
        csv_encoded = csv_stream.getvalue().encode("utf-8")
        return (BytesIO(csv_encoded), "generate_fees_test-valid.csv")

    return make_csv_data


class TestMonthlyPaymentsGenerateFees:
    def test_monthly_payments_generate_fees__invalid_date(
        self, admin_client, csv_fixture
    ):
        csv_data = [
            ["ID", "Final Payment Amount"],
            ["1", "50.00"],
            ["2", "100.00"],
        ]
        csv_file = csv_fixture(csv_data)
        invalid_payment_date = (
            datetime.datetime.utcnow().replace(day=1)
            - datetime.timedelta(days=1)
            - relativedelta(months=1)
        )

        res = admin_client.post(
            "/admin/monthly_payments/generate_fees",
            data={
                "payment_date": invalid_payment_date.strftime("%m/%d/%Y"),
                "providers_validated_payments_csv": csv_file,
            },
            headers={"Content-Type": "multipart/form-data"},
            follow_redirects=True,
        )

        html = res.data.decode("utf-8")
        assert res.status_code == 400
        assert (
            "Please provide a date no more than one month prior to today for this payment."
            in html
        )

    def test_monthly_payments_generate_fees__invalid_csv_header(
        self, admin_client, csv_fixture
    ):
        csv_data = [
            ["prac_id", "amount"],
            [str(1), str(50.00)],
            [str(2), str(100.00)],
        ]
        csv_file = csv_fixture(csv_data)
        payment_date = datetime.datetime.utcnow().replace(day=1) - datetime.timedelta(
            days=1
        )

        res = admin_client.post(
            "/admin/monthly_payments/generate_fees",
            data={
                "payment_date": payment_date.strftime("%m/%d/%Y"),
                "providers_validated_payments_csv": csv_file,
            },
            headers={"Content-Type": "multipart/form-data"},
            follow_redirects=True,
        )

        html = res.data.decode("utf-8")
        assert res.status_code == 400
        assert "Invalid csv file, file headers" in html

    def test_monthly_payments_generate_fees__invalid_csv_data(
        self, admin_client, factories, csv_fixture
    ):
        prac_1 = factories.PractitionerUserFactory.create()
        csv_data = [
            ["ID", "Final Payment Amount"],
            [str(prac_1.id), "50,00"],
            ["", str(100.00)],
            [str(-1), "200.00"],
        ]
        csv_file = csv_fixture(csv_data)
        payment_date = datetime.datetime.utcnow().replace(day=1) - datetime.timedelta(
            days=1
        )

        res = admin_client.post(
            "/admin/monthly_payments/generate_fees",
            data={
                "payment_date": payment_date.strftime("%m/%d/%Y"),
                "providers_validated_payments_csv": csv_file,
            },
            headers={"Content-Type": "multipart/form-data"},
            follow_redirects=True,
        )

        html = res.data.decode("utf-8")
        assert res.status_code == 400
        assert "Missing practitioner" in html
        assert "Invalid amount" in html
        assert "Invalid practitioners" in html

    def test_monthly_payments_generate_fees__valid(
        self, admin_client, factories, csv_fixture
    ):
        prac_1 = factories.PractitionerUserFactory.create()
        prac_2 = factories.PractitionerUserFactory.create()
        csv_data = [
            ["ID", "Final Payment Amount"],
            [str(prac_1.id), str(50.00)],
            [str(prac_2.id), str(100.00)],
        ]
        csv_file = csv_fixture(csv_data)
        payment_date = datetime.datetime.utcnow().replace(day=1) - datetime.timedelta(
            days=1
        )

        res = admin_client.post(
            "/admin/monthly_payments/generate_fees",
            data={
                "payment_date": payment_date.strftime("%m/%d/%Y"),
                "providers_validated_payments_csv": csv_file,
            },
            headers={"Content-Type": "multipart/form-data"},
        )

        assert res.status_code == 200
