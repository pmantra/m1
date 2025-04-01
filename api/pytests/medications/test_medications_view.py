import factory
from factory.alchemy import SQLAlchemyModelFactory

from models.medications import Medication
from pytests.factories import BaseMeta


class MedicationFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = Medication

    product_id = factory.Sequence(lambda n: f"0000-{n}")
    proprietary_name = "Medicine (TM)"
    nonproprietary_name = "Medicine"


def test_no_query_string(client, api_helpers, default_user):
    res = client.get(
        "/api/v1/medications", headers=api_helpers.standard_headers(default_user)
    )
    assert res.status_code == 400


def test_no_results(client, api_helpers, default_user):
    res = client.get(
        "/api/v1/medications?query_string=abc",
        headers=api_helpers.standard_headers(default_user),
    )
    assert res.status_code == 200
    assert api_helpers.load_json(res) == {"data": []}


def test_results(client, api_helpers, default_user):
    MedicationFactory.create(proprietary_name="Advil")
    MedicationFactory.create(proprietary_name="Advate")
    MedicationFactory.create(proprietary_name="Sadvil")
    res = client.get(
        "/api/v1/medications?query_string=adv",
        headers=api_helpers.standard_headers(default_user),
    )
    assert api_helpers.load_json(res)["data"] == ["Advil", "Advate"]
