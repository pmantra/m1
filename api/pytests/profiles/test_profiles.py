import json
from datetime import datetime, timedelta
from unittest import mock

import pytest

from authn.models.user import User
from authz.models.roles import ROLES
from models.profiles import (
    AgreementNames,
    CareTeamTypes,
    MemberPractitionerAssociation,
    PractitionerProfile,
)
from pytests import factories
from pytests.freezegun import freeze_time
from storage.connection import db


class TestUserProfiles:
    def test_last_care_advocate_appointment(self, factories):
        ca_vertical = factories.VerticalFactory.create_cx_vertical()
        ca = factories.PractitionerUserFactory(
            practitioner_profile__verticals=[ca_vertical]
        )
        appt = factories.AppointmentFactory.create_with_practitioner(
            ca, scheduled_start=datetime.now(), scheduled_end=datetime.now()
        )
        assert appt.member.last_care_advocate_appointment().id == appt.id

    def test_normalized_country_abbr(self, default_user, factories):
        mp = factories.MemberProfileFactory.create(user=default_user)
        assert default_user.country_code is None
        assert default_user.normalized_country_abbr == "US"

        mp.country_code = "UA"

        assert default_user.normalized_country_abbr == "UA"

    def test_pending_organization_agreements__no_pending_agreements(
        self, factories, enterprise_user
    ):
        """
        When there are no pending agreements,
        we should not return any agreements.
        """
        factories.LanguageFactory.create(name="English")
        agreement = factories.AgreementFactory.create()
        factories.AgreementAcceptanceFactory.create(
            agreement=agreement, user=enterprise_user
        )
        organization_ids = {enterprise_user.organization_v2.id}
        assert (
            enterprise_user.get_pending_organization_agreements(organization_ids) == []
        )

    def test_pending_organization_agreements__pending_agreements_org_match(
        self, factories, enterprise_user
    ):
        """
        When a pending agreement is associated with the user's organization,
        we should return that agreement.
        """
        factories.LanguageFactory.create(name="English")
        agreement = factories.AgreementFactory.create()
        factories.OrganizationAgreementFactory.create(
            organization=enterprise_user.organization, agreement=agreement
        )

        organization_ids = {enterprise_user.organization_v2.id}
        assert (
            len(enterprise_user.get_pending_organization_agreements(organization_ids))
            == 1
        )

    def test_pending_organization_agreements__pending_agreements_org_mismatch(
        self, factories, enterprise_user
    ):
        """
        When a pending agreement is associated with an organization,
        but it is not the user's organization,
        we should not return that agreement.
        """
        factories.LanguageFactory.create(name="English")
        agreement = factories.AgreementFactory.create()
        org = factories.OrganizationFactory.create()
        factories.OrganizationAgreementFactory.create(
            organization=org, agreement=agreement
        )
        organization_ids = {enterprise_user.organization_v2.id}
        assert (
            len(enterprise_user.get_pending_organization_agreements(organization_ids))
            == 0
        )

    def test_pending_organization_agreements__pending_agreements_no_org_agreements(
        self, factories, enterprise_user
    ):
        """
        When the pending agreement is not associated with an organization,
        we should not return that agreement.
        """
        factories.LanguageFactory.create(name="English")
        factories.AgreementFactory.create()

        organization_ids = {enterprise_user.organization_v2.id}
        assert (
            len(enterprise_user.get_pending_organization_agreements(organization_ids))
            == 0
        )

    def test_pending_user_agreements__no_pending_agreements(
        self, factories, enterprise_user
    ):
        """
        When there are no pending agreements,
        we should not return any agreements.
        """
        factories.LanguageFactory.create(name="English")
        agreement = factories.AgreementFactory.create()
        factories.AgreementAcceptanceFactory.create(
            agreement=agreement, user=enterprise_user
        )
        assert enterprise_user.pending_user_agreements == []

    def test_pending_user_agreements__multiple_agreements(
        self, factories, enterprise_user
    ):
        """
        When there are multiple agreements,
        and one is accepted,
        we should return the unaccepted agreement.
        """
        factories.LanguageFactory.create(name="English")
        accepted_agreement = factories.AgreementFactory.create(
            name=AgreementNames.PRIVACY_POLICY
        )
        factories.AgreementFactory.create(name=AgreementNames.TERMS_OF_USE)
        factories.AgreementAcceptanceFactory.create(
            agreement=accepted_agreement, user=enterprise_user
        )

        assert len(enterprise_user.pending_user_agreements) == 1
        assert (
            enterprise_user.pending_user_agreements[0].name.value
            == AgreementNames.TERMS_OF_USE.value
        )
        assert enterprise_user.pending_user_agreements[0].display_name == "Terms of Use"

    def test_pending_user_agreements__pending_agreements_org_match(
        self, factories, enterprise_user
    ):
        """
        When there is a pending agreement that is associated with the user's organization,
        we should not return that agreement.
        """
        factories.LanguageFactory.create(name="English")
        agreement = factories.AgreementFactory.create()
        factories.OrganizationAgreementFactory.create(
            organization=enterprise_user.organization, agreement=agreement
        )

        assert len(enterprise_user.pending_user_agreements) == 0

    def test_pending_user_agreements__pending_agreements_org_mismatch(
        self, factories, enterprise_user
    ):
        """
        When a pending agreement is associated with an organization,
        but it is not the user's organization,
        we should not return that agreement.
        """
        factories.LanguageFactory.create(name="English")
        agreement = factories.AgreementFactory.create()
        org = factories.OrganizationFactory.create()
        factories.OrganizationAgreementFactory.create(
            organization=org, agreement=agreement
        )

        assert len(enterprise_user.pending_user_agreements) == 0

    def test_pending_user_agreements__pending_agreements_no_org_agreements(
        self, factories, enterprise_user
    ):
        """
        When a pending agreement is not associated with an organization,
        we should return that agreement.
        """
        factories.LanguageFactory.create(name="English")
        factories.AgreementFactory.create()

        assert len(enterprise_user.pending_user_agreements) == 1

    def test_create_user_profiles(
        self, client, api_helpers, patch_user_id_encoded_token
    ):
        # Given
        factories.RoleFactory.create(name=ROLES.member)
        data = {
            "email": "foo@example.com",
            "first_name": "Foo",
            "last_name": "Bar",
            "password": "$ecretW0rd",
            "username": "foobar",
        }
        # When
        with mock.patch("authn.resources.user.create_idp_user") as create_idp_user_mock:
            client.post(
                "/api/v1/users",
                data=json.dumps(data),
                headers=api_helpers.json_headers(None),
            )
            assert create_idp_user_mock.called

        user = db.session.query(User).filter(User.email == data["email"]).one()
        # Then
        assert user.member_profile
        assert len(user.user_types) == 1


class TestMemberProfiles:
    def test_member_profile_no_inactive_tracks(
        self,
        default_user,
    ):
        profile = factories.MemberProfileFactory.create(user=default_user)
        assert profile.has_recently_ended_track is False

    def test_member_profile_outdated_inactive_track(
        self,
        default_user,
    ):
        profile = factories.MemberProfileFactory.create(user=default_user)
        factories.MemberTrackFactory.create(
            user=default_user,
            ended_at=datetime.today() - timedelta(days=60),
        )

        assert profile.has_recently_ended_track is False

    def test_member_profile_recently_inactive_track(
        self,
        default_user,
    ):
        profile = factories.MemberProfileFactory.create(user=default_user)
        factories.MemberTrackFactory.create(
            user=default_user,
            ended_at=datetime.today() - timedelta(days=7),
        )

        assert profile.has_recently_ended_track is True

    @freeze_time(datetime.utcnow())
    def test_member_profile_recently_inactive_track_exact(
        self,
        default_user,
    ):
        profile = factories.MemberProfileFactory.create(user=default_user)
        factories.MemberTrackFactory.create(
            user=default_user,
            ended_at=datetime.today() - timedelta(days=30),
        )

        assert profile.has_recently_ended_track is True

    def test_member_profile_sets_subdivision_code(self, default_user):
        profile = factories.MemberProfileFactory.create(user=default_user)
        state = factories.StateFactory.create(abbreviation="CA", name="California")

        profile.country_code = "US"
        profile.state = state

        assert profile.subdivision_code == "US-CA"

    @pytest.mark.parametrize("should_enable_update_zendesk_user_profile", [True, False])
    @pytest.mark.parametrize("phone_number_updated", [True, False])
    @mock.patch("messaging.services.zendesk.should_update_zendesk_user_profile")
    @mock.patch("messaging.services.zendesk.update_zendesk_user.delay")
    def test_update_zendesk_user_on_phone_number_update(
        self,
        mock_update_zendesk_user,
        mock_should_update_zendesk_user_profile,
        phone_number_updated,
        default_user,
        should_enable_update_zendesk_user_profile,
    ):
        # Given
        # configure the ff to update the zendesk profile based on the boolean value of `should_enable_update_zendesk_user_profile`
        mock_should_update_zendesk_user_profile.return_value = (
            should_enable_update_zendesk_user_profile
        )

        # create a Member Profile
        member_profile = factories.MemberProfileFactory.create(user=default_user)

        # When

        # update the Member Profile's phone number
        if phone_number_updated:
            member_profile.phone_number = "1-212-555-5555"
        # `after_update` only happens after a flush and commit so manually commit to the db to trigger it
        db.session.commit()

        # Then

        # assert the log that contains the nature of the update and the user id
        if not should_enable_update_zendesk_user_profile or not phone_number_updated:
            mock_update_zendesk_user.assert_not_called()
        else:
            mock_update_zendesk_user.assert_called_once_with(
                user_id=default_user.id,
                update_identity="phone_number",
                team_ns="virtual_care",
                caller="update_zendesk_user_on_phone_number_update",
            )


class TestPractitionerProfiles:
    @pytest.mark.parametrize(
        argnames="first_name,last_name,search",
        argvalues=[
            ("Firstname", "Lastname", "Firstname"),
            ("Firstname", "Lastname", "Lastname"),
            ("Firstname", "Lastname", "Firstname Lastname"),
            ("Firstname", "Lastname", "irst"),
        ],
    )
    def test_full_name_property__full_name_hybrid_property_can_be_used_in_sql(
        self, first_name, last_name, search, factories
    ):
        practitioner_user = factories.PractitionerUserFactory()

        # Given - Set the first name and last name on the practitioner profile fixture
        practitioner_user.first_name = first_name
        practitioner_user.last_name = last_name

        # When we query the DB using the hybrid property for full name
        pp = (
            db.session.query(PractitionerProfile)
            .filter(PractitionerProfile.full_name.like(f"%{search}%"))
            .first()
        )
        # Then the practitioner result from the DB is the same as the practitioner from the fixture
        assert pp == practitioner_user.practitioner_profile

    @pytest.mark.parametrize(
        argnames="first_name,last_name,search",
        argvalues=[
            ("Firstname", "Lastname", "Badfirstname"),
            ("Firstname", "Lastname", "FirstnameLastname"),
        ],
    )
    def test_full_name_property__full_name_hybrid_property_bad_first_name(
        self, first_name, last_name, search, factories
    ):
        practitioner_user = factories.PractitionerUserFactory()

        # Given - Set the first name and last name on the practitioner profile fixture
        practitioner_user.first_name = first_name
        practitioner_user.last_name = last_name

        # When we query the DB using the hybrid property for full name
        pp = (
            db.session.query(PractitionerProfile)
            .filter(PractitionerProfile.full_name.like(f"%{search}%"))
            .first()
        )
        # Then the practitioner result from the DB is none (search result not found)
        assert pp is None

    def test_practitioner_profile_sets_subdivision_code(self, default_user):
        profile = factories.PractitionerProfileFactory.create(user=default_user)
        state = factories.StateFactory.create(abbreviation="CA", name="California")

        profile.country_code = "US"
        profile.state = state

        assert profile.subdivision_code == "US-CA"


class TestMemberPractitionerAssociation:
    @pytest.mark.parametrize("should_enable_update_zendesk_user_profile", [True, False])
    @mock.patch("messaging.services.zendesk.should_update_zendesk_user_profile")
    @mock.patch("messaging.services.zendesk.update_zendesk_user.delay")
    @mock.patch("models.profiles.log.info")
    def test_mpa__update_zendesk_user_on_ca_update(
        self,
        mock_log_info,
        mock_update_zendesk_user,
        mock_should_update_zendesk_user_profile,
        should_enable_update_zendesk_user_profile,
    ):
        # Given
        # configure the ff to update the zendesk profile based on the boolean value of `should_enable_update_zendesk_user_profile`
        mock_should_update_zendesk_user_profile.return_value = (
            should_enable_update_zendesk_user_profile
        )
        # we have an existing user and CA relationship
        user = factories.EnterpriseUserFactory.create()
        old_cx = user.care_coordinators[0]
        factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=old_cx
        )
        mock_log_info.reset_mock()
        mock_update_zendesk_user.reset_mock()
        # When
        # update the Member's CA
        new_cx = factories.PractitionerUserFactory()
        association = MemberPractitionerAssociation.query.filter_by(
            user_id=user.id,
            practitioner_id=old_cx.id,
            type=CareTeamTypes.CARE_COORDINATOR,
        ).first()
        association.practitioner_profile = new_cx.practitioner_profile
        db.session.commit()

        # Then
        # assert the log that contains the nature of the update and the user id
        if not should_enable_update_zendesk_user_profile:
            mock_update_zendesk_user.assert_not_called()
            mock_log_info.assert_not_called()
        else:
            mock_log_info.assert_called_once_with(
                "Updating Zendesk Profile for user due to CA change",
                user_id=user.id,
                mpa_id=association.id,
            )
            mock_update_zendesk_user.assert_called_once_with(
                user_id=user.id,
                update_identity="care_advocate",
                team_ns="virtual_care",
                caller="update_zendesk_user_on_ca_update",
            )

    @pytest.mark.parametrize("should_enable_update_zendesk_user_profile", [True, False])
    @mock.patch("messaging.services.zendesk.should_update_zendesk_user_profile")
    @mock.patch("messaging.services.zendesk.update_zendesk_user.delay")
    @mock.patch("models.profiles.log.info")
    def test_mpa__update_zendesk_user_on_ca_assignment(
        self,
        mock_log_info,
        mock_update_zendesk_user,
        mock_should_update_zendesk_user_profile,
        should_enable_update_zendesk_user_profile,
    ):
        # Given
        # configure the ff to update the zendesk profile based on the boolean value of `should_enable_update_zendesk_user_profile`
        mock_should_update_zendesk_user_profile.return_value = (
            should_enable_update_zendesk_user_profile
        )
        # we have an existing user that comes with a CA relationship
        user = factories.EnterpriseUserFactory.create()
        mock_update_zendesk_user.reset_mock()
        mock_log_info.reset_mock()
        cx = user.care_coordinators[0]
        factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=cx)
        # then
        # assert the log that contains the nature of the update and the user id
        if not should_enable_update_zendesk_user_profile:
            mock_update_zendesk_user.assert_not_called()
            mock_log_info.assert_not_called()
        else:
            association = MemberPractitionerAssociation.query.filter_by(
                user_id=user.id,
                practitioner_id=cx.id,
                type=CareTeamTypes.CARE_COORDINATOR,
            ).first()
            mock_log_info.assert_called_once_with(
                "Updating Zendesk Profile for user due to CA assignment",
                user_id=user.id,
                mpa_id=association.id,
            )
            mock_update_zendesk_user.assert_called_once_with(
                user_id=user.id,
                update_identity="care_advocate",
                team_ns="virtual_care",
                caller="update_zendesk_user_on_ca_assignment",
            )

    @pytest.mark.parametrize("should_enable_update_zendesk_user_profile", [True, False])
    @mock.patch("messaging.services.zendesk.should_update_zendesk_user_profile")
    @mock.patch("messaging.services.zendesk.update_zendesk_user.delay")
    @mock.patch("models.profiles.log.info")
    def test_mpa__update_zendesk_user_skipped_non_ca_update(
        self,
        mock_log_info,
        mock_update_zendesk_user,
        mock_should_update_zendesk_user_profile,
        should_enable_update_zendesk_user_profile,
    ):
        # Given
        # configure the ff to update the zendesk profile based on the boolean value of `should_enable_update_zendesk_user_profile`
        mock_should_update_zendesk_user_profile.return_value = (
            should_enable_update_zendesk_user_profile
        )
        # user with prac association
        user = factories.EnterpriseUserFactory.create()
        practitioner = factories.PractitionerUserFactory()
        new_prac = factories.PractitionerUserFactory()

        mock_log_info.reset_mock()
        mock_update_zendesk_user.reset_mock()

        user.practitioner_associations.append(
            MemberPractitionerAssociation(
                user_id=user.id,
                practitioner_id=practitioner.id,
                type=CareTeamTypes.APPOINTMENT,
                json={"migrated_at": datetime.utcnow().isoformat()},
            )
        )

        # When
        # update the MPA ID
        association = MemberPractitionerAssociation.query.filter_by(
            user_id=user.id,
            practitioner_id=practitioner.id,
            type=CareTeamTypes.APPOINTMENT,
        ).first()
        association.practitioner_id = new_prac.id
        db.session.commit()
        # Then
        # assert that we don't update zendesk bc it's not a CA change
        mock_log_info.assert_not_called()
        mock_update_zendesk_user.assert_not_called()
