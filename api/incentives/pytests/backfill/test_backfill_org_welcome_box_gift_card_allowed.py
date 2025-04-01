import random
import string
from unittest.mock import mock_open, patch

import pytest

from incentives.utils.backfill.backfill_org_welcome_box_gift_card_allowed import (
    OrganizationIncentiveAllowedBackfill,
)
from storage.connection import db


@pytest.fixture()
def random_prefix():
    return "".join(
        random.choice(string.ascii_uppercase + string.digits) for _ in range(5)
    )


def test_backfill_organization_welcome_box_gift_card_allowed__success(factories):
    # Given 4 organizations
    org_1 = factories.OrganizationFactory.create()
    org_2 = factories.OrganizationFactory.create()
    org_3 = factories.OrganizationFactory.create()
    org_4 = factories.OrganizationFactory.create()

    # create a fake CSV file
    data = [
        "organization_id,gift_card_allowed,welcome_box_allowed",
        f"{org_1.id},Y,Y",
        f"{org_2.id},N,Y",
        f"{org_3.id},Y,N",
        f"{org_4.id},,Y",
    ]
    fake_csv = "\n".join(data)

    # When
    with patch("builtins.open", mock_open(read_data=fake_csv)):
        errors = OrganizationIncentiveAllowedBackfill.backfill_organization_welcome_box_gift_card_allowed(
            "fake_file_path.csv"
        )
    db.session.expire_all()

    # Then
    assert org_1.gift_card_allowed
    assert not org_2.gift_card_allowed
    assert org_3.gift_card_allowed
    assert not org_4.gift_card_allowed
    assert org_1.welcome_box_allowed
    assert org_2.welcome_box_allowed
    assert not org_3.welcome_box_allowed
    assert org_4.welcome_box_allowed
    assert not errors


def test_backfill_organization_welcome_box_gift_card_allowed__errors(factories):
    # Given
    factories.OrganizationFactory.create()
    org_2 = factories.OrganizationFactory.create()
    org_3 = factories.OrganizationFactory.create()
    org_4 = factories.OrganizationFactory.create()

    # create a fake CSV file
    data = [
        "organization_id,gift_card_allowed,welcome_box_allowed",
        "0,Y,Y",
        f"{org_2.id},8,invalid",
        f"{org_3.id},Y,N",
        f"{org_4.id},,Y",
    ]
    fake_csv = "\n".join(data)

    # When
    with patch("builtins.open", mock_open(read_data=fake_csv)):
        errors = OrganizationIncentiveAllowedBackfill.backfill_organization_welcome_box_gift_card_allowed(
            "fake_file_path.csv"
        )
    db.session.expire_all()

    # Then
    assert set(errors).issubset(
        [
            "No valid organization found for org_id 0",
            "{'welcome_box_allowed': ['Not a valid boolean.'], 'gift_card_allowed': ['Not a valid boolean.']} org_id "
            + f"{org_2.id}",
            "{'gift_card_allowed': ['Not a valid boolean.'], 'welcome_box_allowed': ['Not a valid boolean.']} org_id "
            + f"{org_2.id}",
        ]
    )
