from unittest.mock import mock_open, patch

import pytest
from marshmallow import ValidationError

from incentives.models.incentive import IncentiveOrganization
from incentives.utils.backfill.backfill_incentive_org import (
    IncentiveOrganizationBackfill,
    validate_incentivized_action,
)
from storage.connection import db


class TestBackfillIncentiveOrg:
    def test_backfill_incentive_org__success(self, factories):
        # Given 2 orgs, 2 incentives, and a fake CSV file
        org_1 = factories.OrganizationFactory.create()
        org_1.gift_card_allowed = True
        org_1.welcome_box_allowed = True
        org_2 = factories.OrganizationFactory.create()
        org_2.gift_card_allowed = True
        org_2.welcome_box_allowed = True
        incentive_1 = factories.IncentiveFactory.create()
        incentive_2 = factories.IncentiveFactory.create()

        data = [
            "organization_id,organization_name,action,incentive_name,track_name,countries",
            f'{org_1.id},"{org_1.name}",CA_INTRO,{incentive_1.name},pregnancy,"US,MX"',
            f'{org_1.id},"{org_1.name}",OFFBOARDING_ASSESSMENT,{incentive_1.name},fertility,US',
            f'{org_2.id},"{org_2.name}",CA_INTRO,{incentive_1.name},adoption,CA',
            f'{org_2.id},"{org_2.name}",OFFBOARDING_ASSESSMENT,{incentive_2.name},fertility,"US,CA"',
        ]
        fake_csv = "\n".join(data)

        # When
        with patch("builtins.open", mock_open(read_data=fake_csv)):
            errors = IncentiveOrganizationBackfill.backfill_incentive_organization(
                "fake_file_path.csv"
            )
        db.session.expire_all()

        # Then
        incentive_1_org_1 = (
            db.session.query(IncentiveOrganization)
            .filter_by(organization_id=org_1.id, incentive_id=incentive_1.id)
            .all()
        )
        incentive_1_org_2 = (
            db.session.query(IncentiveOrganization)
            .filter_by(organization_id=org_2.id, incentive_id=incentive_1.id)
            .all()
        )
        incentive_2_org_2 = (
            db.session.query(IncentiveOrganization)
            .filter_by(organization_id=org_2.id, incentive_id=incentive_2.id)
            .all()
        )

        assert not errors
        assert incentive_1_org_1
        assert incentive_1_org_2
        assert incentive_2_org_2

    def test_backfill_incentive_org__errors(self, factories):
        # Given 2 orgs, 2 incentives, and a fake CSV file
        org_1 = factories.OrganizationFactory.create()
        org_1.gift_card_allowed = True
        org_1.welcome_box_allowed = True
        org_2 = factories.OrganizationFactory.create()
        org_2.gift_card_allowed = True
        org_2.welcome_box_allowed = True
        incentive_1 = factories.IncentiveFactory.create()
        incentive_2 = factories.IncentiveFactory.create()

        data = [
            "organization_id,organization_name,action,incentive_name,track_name,countries",
            f'{org_1.id},"{org_1.name}",Fake action,{incentive_1.name},postpartum,"US,MX"',
            f'0,"{org_1.name}",OFFBOARDING_ASSESSMENT,{incentive_1.name},fertility,US',
            f'{org_2.id},"{org_2.name}",CA_INTRO,{incentive_1.name},not_a_track,CA',
            f'{org_2.id},"{org_2.name}",OFFBOARDING_ASSESSMENT,{incentive_2.name},pregnancy,"US,CA"',
        ]
        fake_csv = "\n".join(data)

        # When
        with patch("builtins.open", mock_open(read_data=fake_csv)):
            errors = IncentiveOrganizationBackfill.backfill_incentive_organization(
                "fake_file_path.csv"
            )
        db.session.expire_all()

        # Then assert errors are as expected (including in different orders)
        assert set(errors).issubset(
            [
                f"{{'action': ['Invalid incentivized_action']}} - Organization: {org_1.id}",
                "Organization 0 does not exist",
                f"Exception creating IncentiveOrg incentive_name: {incentive_1.name}, org_id: {org_2.id}. 'not_a_track' is not a valid track name",
            ]
        )


class TestValidateIncentivizedAction:
    def test_validate_incentivized_action__valid(self):
        assert validate_incentivized_action("CA_INTRO")

    def test_validate_incentivized_action__invalid(self):
        with pytest.raises(ValidationError):
            validate_incentivized_action("Invalid data")


class TestValidateTrackName:
    def test_validate_track_name__valid(self):
        assert IncentiveOrganizationBackfill._validate_track_name("pregnancy")

    def test_validate_track_name__invalid(self):
        with pytest.raises(ValueError):
            IncentiveOrganizationBackfill._validate_track_name("Invalid data")


class TestValidateCountryCode:
    def test_validate_country_code__valid(self):
        assert IncentiveOrganizationBackfill._validate_country_code("US")

    def test_validate_country_code__invalid(self):
        with pytest.raises(ValueError):
            IncentiveOrganizationBackfill._validate_country_code("Invalid data")
