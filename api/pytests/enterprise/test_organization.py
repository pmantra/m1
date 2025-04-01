from unittest import mock

import pytest
from sqlalchemy.exc import StatementError

from admin.views.models.enterprise import coerce_bool
from models.enterprise import (
    Organization,
    OrganizationEligibilityType,
    OrganizationType,
)
from models.tracks import TrackName
from storage.connection import db


def test_education_only_validation(factories):
    with pytest.raises(ValueError) as e:
        org = factories.OrganizationFactory.create()
        org.rx_enabled = True
        org.education_only = True

    assert "cannot set education only to true" in repr(e.value)


def test_real_organization_alegeus_employer_id(factories):
    real_organization = factories.OrganizationFactory.create(
        internal_type=OrganizationType.REAL
    )
    # create_alegeus_employer_id is called by admin on creation of organization
    real_organization.create_alegeus_employer_id()
    assert len(real_organization.alegeus_employer_id) == 11

    maven_organization = factories.OrganizationFactory.create(
        internal_type=OrganizationType.MAVEN_FOR_MAVEN
    )
    maven_organization.create_alegeus_employer_id()
    assert len(maven_organization.alegeus_employer_id) == 11


def test_fake_organization_no_alegeus_employer_id(factories):
    test_organization = factories.OrganizationFactory.create(
        internal_type=OrganizationType.TEST
    )
    # create_alegeus_employer_id is called by admin on creation of organization
    test_organization.create_alegeus_employer_id()
    assert test_organization.alegeus_employer_id is None

    vip_organization = factories.OrganizationFactory.create(
        internal_type=OrganizationType.DEMO_OR_VIP
    )
    vip_organization.create_alegeus_employer_id()
    assert vip_organization.alegeus_employer_id is None


def test_set_eligibility_type_from_enum(factories):
    org = factories.OrganizationFactory.create()
    org.eligibility_type = OrganizationEligibilityType.FILELESS
    db.session.add(org)
    db.session.commit()

    db_org = Organization.query.get(org.id)
    assert db_org.eligibility_type is OrganizationEligibilityType.FILELESS


def test_set_us_restricted(factories):
    org = factories.OrganizationFactory.create()
    org.US_restricted = True
    db.session.add(org)
    db.session.commit()

    db_org = Organization.query.get(org.id)
    assert db_org.US_restricted is True


def test_set_us_restricted_false(factories):
    org = factories.OrganizationFactory.create()
    org.US_restricted = False
    db.session.add(org)
    db.session.commit()

    db_org = Organization.query.get(org.id)
    assert db_org.US_restricted is False


def test_set_eligibility_type_from_enum_failure(factories):
    org = factories.OrganizationFactory.create()
    org.eligibility_type = "invalid value"
    db.session.add(org)
    with pytest.raises(StatementError) as e:
        db.session.commit()
        assert "invalid value is not among the defined enum values" in repr(e.value)


@pytest.mark.parametrize("data_provider_enabled", [(True), (False)])
def test_set_data_provider(factories, data_provider_enabled):
    org = factories.OrganizationFactory.create()
    org.data_provider = data_provider_enabled
    db.session.add(org)
    db.session.commit()

    db_org = Organization.query.get(org.id)

    assert db_org.data_provider == data_provider_enabled


@mock.patch("messaging.services.zendesk.update_zendesk_org.delay")
def test_create_organization_zendesk_listener(
    mock_update_zd_org,
    factories,
):
    # Given
    # When - new org
    org = factories.OrganizationFactory.create()
    db.session.commit()

    mock_update_zd_org.assert_called_once_with(org.id, org.name, [], org.US_restricted)


@mock.patch("messaging.services.zendesk.update_zendesk_org.delay")
def test_update_organization_zendesk_listener(
    mock_update_zd_org,
    factories,
):
    # Given
    org = factories.OrganizationFactory.create()
    track_1 = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.ADOPTION
    )
    track_2 = factories.ClientTrackFactory.create(
        organization=org, track=TrackName.PREGNANCY
    )
    db.session.commit()

    # When - clear mocks + change name
    mock_update_zd_org.reset_mock()
    org.name = "LEAH TEST ORG"
    db.session.commit()

    # then
    call_args = mock_update_zd_org.call_args[0]
    assert call_args[0] == org.id
    assert call_args[1] == org.name
    assert call_args[2][0].active == track_1.active
    assert call_args[2][0].name == track_1.name
    assert call_args[2][0].display_name == track_1.display_name
    assert call_args[2][1].active == track_2.active
    assert call_args[2][1].name == track_2.name
    assert call_args[2][1].display_name == track_2.display_name


@mock.patch("messaging.services.zendesk.update_zendesk_org.delay")
def test_update_organization_zendesk_listener__offshore_restriction(
    mock_update_zd_org,
    factories,
):
    # Given org
    org = factories.OrganizationFactory.create()
    mock_update_zd_org.reset_mock()
    # When - offshore changed
    org.US_restricted = not org.US_restricted
    db.session.commit()

    mock_update_zd_org.assert_called_once_with(org.id, org.name, [], org.US_restricted)


class TestCoerceBool:
    def test_coerce_bool__string_true(self):
        assert coerce_bool("True") is True

    def test_coerce_bool__string_false(self):
        assert coerce_bool("False") is False

    def test_coerce_bool__string_none(self):
        assert coerce_bool("None") is None

    def test_coerce_bool__int_true(self):
        assert coerce_bool(1) is True

    def test_coerce_bool__int_false(self):
        assert coerce_bool(0) is False

    def test_coerce_bool__bool_true(self):
        assert coerce_bool(True) is True

    def test_coerce_bool__bool_false(self):
        assert coerce_bool(False) is False

    def test_coerce_bool__none(self):
        assert coerce_bool(None) is None
