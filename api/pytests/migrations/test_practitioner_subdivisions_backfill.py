from storage.connection import db
from utils.migrations.backfill_practitioner_subdivisions import (
    backfill_certified_subdivision_codes,
)


def test_no_country_with_one_certified_state(factories, default_user):
    """
    When:
        - The PractitionerProfile has one certified state (comes from the fixture)
        - The PractitionerProfile does not have a country_code
    Then:
        - The backfill is run
    Test that:
        - The PractitionerProfile's certified_subdivision_codes is updated
    """
    pp = factories.PractitionerProfileFactory.create(
        user=default_user,
        country_code=None,
    )

    backfill_certified_subdivision_codes()
    db.session.expire_all()

    assert pp.certified_subdivision_codes == ["US-NY"]


def test_country_with_one_certified_state(factories, default_user):
    """
    When:
        - The PractitionerProfile has one certified state (comes from the fixture)
        - The PractitionerProfile has a country_code
    Then:
        - The backfill is run
    Test that:
        - The PractitionerProfile's certified_subdivision_codes is updated
    """
    pp = factories.PractitionerProfileFactory.create(
        user=default_user,
        country_code="US",
    )

    backfill_certified_subdivision_codes()
    db.session.expire_all()

    assert pp.certified_subdivision_codes == ["US-NY"]


def test_non_us_country_with_one_certified_state(factories, default_user):
    """
    When:
        - The PractitionerProfile has one certified state (comes from the fixture)
        - The PractitionerProfile has a country_code that is not "US"
    Then:
        - The backfill is run
    Test that:
        - The PractitionerProfile's certified_subdivision_codes is updated
    """
    pp = factories.PractitionerProfileFactory.create(
        user=default_user,
        country_code="CA",
    )

    backfill_certified_subdivision_codes()
    db.session.expire_all()

    assert pp.certified_subdivision_codes == ["US-NY"]
