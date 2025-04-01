import random
import string
from csv import DictReader
from io import StringIO

import pytest
from sqlalchemy import func

from models.enterprise import Organization, OrganizationEligibilityType
from storage.connection import db
from utils.migrations.organization_eligibility_types.backfill_organization_eligibility_types import (
    update_org_eligibility_type,
)


@pytest.fixture()
def random_prefix():
    return "".join(
        random.choice(string.ascii_uppercase + string.digits) for _ in range(5)
    )


def test_update_eligibility_type(factories):
    """
    When given a CSV with valid/matching Organization ID/name and a valid eligibility type,
    test that that organization's eligibility type is updated to the value in the CSV.
    """
    org_name = f"{random_prefix}FunCorp"
    org = factories.OrganizationFactory.create(
        name=org_name, eligibility_type=OrganizationEligibilityType.UNKNOWN
    )

    # create a fake CSV file
    data = [
        "id,name,eligibility_type",
        f"{org.id},{org_name},{OrganizationEligibilityType.ALTERNATE.value}",
    ]
    fake_csv = StringIO("\n".join(data))
    mapping = DictReader(fake_csv.readlines())
    update_org_eligibility_type(mapping)
    db.session.expire_all()

    assert org.eligibility_type == OrganizationEligibilityType.ALTERNATE


def test_update_eligibility_type__unknown_org_id(factories):
    """
    When given a CSV with a valid Organization name and a valid eligibility type,
    but the Organization ID does not exist in the DB,
    test that that organization's eligibility type is NOT updated to the value in the CSV.
    """
    org_name = f"{random_prefix}FunCorp"
    org = factories.OrganizationFactory.create(
        name=org_name, eligibility_type=OrganizationEligibilityType.UNKNOWN
    )

    max_org_id = db.session.query(func.max(Organization.id)).scalar()

    # create a fake CSV file
    data = [
        "id,name,eligibility_type",
        f"{max_org_id + 1},{org_name},{OrganizationEligibilityType.ALTERNATE.value}",
    ]
    fake_csv = StringIO("\n".join(data))
    mapping = DictReader(fake_csv.readlines())
    update_org_eligibility_type(mapping)
    db.session.expire_all()

    assert org.eligibility_type == OrganizationEligibilityType.UNKNOWN


def test_update_eligibility_type__missing_eligibility_type(factories):
    """
    When given a CSV with a valid Organization ID, Organization name, but no eligibility type,
    test that that organization's eligibility type is NOT updated to the value in the CSV.
    """
    org_name = f"{random_prefix}FunCorp"
    org = factories.OrganizationFactory.create(
        name=org_name, eligibility_type=OrganizationEligibilityType.UNKNOWN
    )

    # create a fake CSV file
    data = ["id,name,eligibility_type", f"{org.id},FunCorp,"]
    fake_csv = StringIO("\n".join(data))
    mapping = DictReader(fake_csv.readlines())
    update_org_eligibility_type(mapping)
    db.session.expire_all()

    assert org.eligibility_type == OrganizationEligibilityType.UNKNOWN


def test_update_eligibility_type__invalid_eligibility_type(factories):
    """
    When given a CSV with a valid Organization ID, Organization name, but an invalid eligibility type,
    test that that organization's eligibility type is NOT updated to the value in the CSV.
    """
    org_name = f"{random_prefix}FunCorp"
    org = factories.OrganizationFactory.create(
        name=org_name, eligibility_type=OrganizationEligibilityType.UNKNOWN
    )

    # create a fake CSV file
    data = ["id,name,eligibility_type", f"{org.id},{org_name},funky"]
    fake_csv = StringIO("\n".join(data))
    mapping = DictReader(fake_csv.readlines())
    update_org_eligibility_type(mapping)
    db.session.expire_all()

    assert org.eligibility_type == OrganizationEligibilityType.UNKNOWN
