from __future__ import annotations

import datetime
from unittest import mock

import pytest
from sqlalchemy.exc import IntegrityError

from authn.pytests import factories as authn_factories
from eligibility.e9y import model
from eligibility.pytests import factories as eligibility_factories
from eligibility.repository import (
    EligibilityField,
    EligibilityMemberRepository,
    EmailDomain,
    EnterpriseEligibilitySettings,
    OrganizationAssociationSettings,
    OrganizationEligibilityType,
    OrgIdentity,
    UserOrganizationEmployeeRepository,
)
from models.enterprise import OrganizationType
from pytests import factories


class TestOrganizationEmployeeRepository:
    def test_get(self, organization_employee_repository):
        # Given
        given_oe = factories.OrganizationEmployeeFactory.create()
        # When
        fetched_oe = organization_employee_repository.get(id=given_oe.id)
        # Then
        assert fetched_oe == given_oe

    def test_create(self, organization_employee_repository):
        # Given
        org = factories.OrganizationFactory.create()
        built_oe = factories.OrganizationEmployeeFactory.build()
        given_kwargs = dict(
            first_name=built_oe.first_name,
            last_name=built_oe.last_name,
            email=built_oe.email,
            date_of_birth=built_oe.date_of_birth,
            organization_id=org.id,
            unique_corp_id=built_oe.unique_corp_id,
            dependent_id=built_oe.dependent_id,
        )
        given_json = dict(super="important")
        expected_fields = {**given_kwargs, "json": given_json.copy()}
        # When
        created_oe = organization_employee_repository.create(
            **given_kwargs, **given_json
        )
        created_fields = {
            f: v for f, v in vars(created_oe).items() if f in expected_fields
        }
        # Then
        assert created_fields == expected_fields

    def test_get_by_org_id_email_dob(self, organization_employee_repository):
        # Given
        given_oe = factories.OrganizationEmployeeFactory.create()
        # When
        fetched_oe = organization_employee_repository.get_by_org_id_email_dob(
            organization_id=given_oe.organization_id,
            email=given_oe.email,
            date_of_birth=given_oe.date_of_birth,
        )
        # Then
        assert fetched_oe == given_oe

    def test_get_by_e9y_member_id(self, organization_employee_repository):
        # Given
        e9y_member_id = 1
        given_oe = factories.OrganizationEmployeeFactory.create(
            eligibility_member_id=e9y_member_id,
        )
        # When
        fetched_oe = organization_employee_repository.get_by_e9y_member_id(
            member_id=e9y_member_id
        )
        # Then
        assert fetched_oe == given_oe

    def test_get_by_org_identity(self, organization_employee_repository, faker):
        # Given
        corp_id = faker.swift11()
        dep_id = faker.swift11()
        given_oe = factories.OrganizationEmployeeFactory.create(
            unique_corp_id=corp_id,
            dependent_id=dep_id,
        )
        org_id = given_oe.organization.id
        # When
        fetched_oe = organization_employee_repository.get_by_org_identity(
            unique_corp_id=corp_id,
            dependent_id=dep_id,
            organization_id=org_id,
        )
        # Then
        assert fetched_oe == given_oe

    def test_get_by_member_id_or_org_identity_using_member_id(
        self, organization_employee_repository, faker
    ):
        # Given
        e9y_member_id = 1
        corp_id = faker.swift11()
        dep_id = faker.swift11()
        given_oe = factories.OrganizationEmployeeFactory.create(
            eligibility_member_id=e9y_member_id,
        )
        org_id = given_oe.organization.id
        # When
        fetched_oe = (
            organization_employee_repository.get_by_e9y_member_id_or_org_identity(
                member_ids=[e9y_member_id],
                org_identities=[
                    OrgIdentity(
                        unique_corp_id=corp_id,
                        dependent_id=dep_id,
                        organization_id=org_id,
                    )
                ],
            )
        )
        # Then
        assert fetched_oe == [given_oe]

    def test_get_by_member_id_or_org_identity_using_org_identity(
        self, organization_employee_repository, faker
    ):
        # Given
        e9y_member_id = 1
        corp_id = faker.swift11()
        dep_id = faker.swift11()
        given_oe = factories.OrganizationEmployeeFactory.create(
            unique_corp_id=corp_id,
            dependent_id=dep_id,
        )
        org_id = given_oe.organization.id
        # When
        fetched_oe = (
            organization_employee_repository.get_by_e9y_member_id_or_org_identity(
                member_ids=[e9y_member_id],
                org_identities=[
                    OrgIdentity(
                        unique_corp_id=corp_id,
                        dependent_id=dep_id,
                        organization_id=org_id,
                    )
                ],
            )
        )
        # Then
        assert fetched_oe == [given_oe]

    def test_get_by_member_id_null_no_match(self, organization_employee_repository):
        # Given
        e9y_member_id = None
        given_oe = factories.OrganizationEmployeeFactory.create()
        org_id = given_oe.organization.id
        # When
        fetched_oe = (
            organization_employee_repository.get_by_e9y_member_id_or_org_identity(
                member_ids=[e9y_member_id],
                org_identities=[
                    OrgIdentity(
                        organization_id=org_id,
                        unique_corp_id=None,
                        dependent_id=None,
                    )
                ],
            )
        )
        # Then
        assert fetched_oe == []

    def test_get_by_member_id_or_org_identity_dependent_identity_match(
        self, organization_employee_repository
    ):
        # Given
        dependent_member = eligibility_factories.EligibilityMemberFactory.create()
        sponsor = factories.OrganizationEmployeeFactory.create(
            unique_corp_id=dependent_member.unique_corp_id, dependent_id=""
        )
        dependent = factories.OrganizationEmployeeFactory.create(
            organization=sponsor.organization,
            unique_corp_id=dependent_member.unique_corp_id,
            dependent_id=dependent_member.dependent_id,
        )
        # When
        fetched_oe = (
            organization_employee_repository.get_by_e9y_member_id_or_org_identity(
                member_ids=None,
                org_identities=[
                    OrgIdentity(
                        unique_corp_id=dependent_member.unique_corp_id,
                        dependent_id=dependent_member.dependent_id,
                        organization_id=sponsor.organization.id,
                    )
                ],
            )
        )
        # Then
        assert fetched_oe == [dependent]

    def test_get_by_member_id_or_org_identity_dependent_identity_match_multiple(
        self, organization_employee_repository
    ):
        # Given
        org_1 = factories.OrganizationFactory.create(id=1)

        # oe_1-1: no e9y_member_id
        # (e9y_memeber_id, org_id, uniq_corp_id, dependent_id) = (null, 1, 1234, null)
        oe_1 = factories.OrganizationEmployeeFactory.create(
            eligibility_member_id=None,
            organization=org_1,
            unique_corp_id="1234",
            dependent_id=None,
        )

        # oe_2: (e9y_memeber_id, org_id, uniq_corp_id, dependent_id) = (XXX, 1, a1234, null)
        oe_2 = factories.OrganizationEmployeeFactory.create(
            organization=org_1, unique_corp_id="a1234", dependent_id=None
        )

        # oe_3: create dependent & sponsor
        dependent_member = eligibility_factories.EligibilityMemberFactory.create()
        oe_3_sponsor = factories.OrganizationEmployeeFactory.create(
            unique_corp_id=dependent_member.unique_corp_id, dependent_id=""
        )
        oe_3_dependent = factories.OrganizationEmployeeFactory.create(
            organization=oe_3_sponsor.organization,
            unique_corp_id=dependent_member.unique_corp_id,
            dependent_id=dependent_member.dependent_id,
        )

        # When
        fetched_oe = (
            organization_employee_repository.get_by_e9y_member_id_or_org_identity(
                member_ids=[
                    oe_2.eligibility_member_id,
                    oe_3_dependent.eligibility_member_id,
                ],
                org_identities=[
                    OrgIdentity(
                        unique_corp_id=oe_1.unique_corp_id,
                        dependent_id=oe_1.dependent_id,
                        organization_id=oe_1.organization.id,
                    ),
                ],
            )
        )

        # Then
        assert fetched_oe == [oe_2, oe_3_dependent]

    def test_get_by_user_id(self, organization_employee_repository):
        # Given
        member = factories.EnterpriseUserFactory.create()
        given_oe = member.organization_employee
        # When
        fetched_oe = organization_employee_repository.get_by_user_id(
            user_id=member.id,
        )
        # Then
        assert fetched_oe == [given_oe]

    def test_get_by_user_id_when_not_found(self, organization_employee_repository):
        # Given
        # When
        fetched_oe = organization_employee_repository.get_by_user_id(
            user_id=1 << 32 + 1,  # A large user_id to simulate not existing user_id
        )
        # Then
        assert fetched_oe == []

    def test_associate_to_user_id(self, organization_employee_repository):
        # Given
        user = factories.DefaultUserFactory.create()
        employee = factories.OrganizationEmployeeFactory.create()
        # When
        organization_employee_repository.associate_to_user_id(
            user_id=user.id, employees=[employee]
        )
        all_associated = organization_employee_repository.get_by_user_id(
            user_id=user.id
        )
        associated = None if not all_associated else all_associated[0]
        # Then
        assert associated == employee

    def test_associate_to_user_id_multiple(self, organization_employee_repository):
        # Given
        user = factories.DefaultUserFactory.create()
        employee_1 = factories.OrganizationEmployeeFactory.create()
        employee_2 = factories.OrganizationEmployeeFactory.create()
        employee_3 = factories.OrganizationEmployeeFactory.create()

        # When
        organization_employee_repository.associate_to_user_id(
            user_id=user.id, employees=[employee_1, employee_2, employee_3]
        )
        all_associated = organization_employee_repository.get_by_user_id(
            user_id=user.id
        )
        # Then
        assert set(all_associated) == {employee_1, employee_2, employee_3}

    @pytest.mark.parametrize(
        argnames="ended_at",
        argvalues=[datetime.datetime.utcnow() - datetime.timedelta(days=7), None],
        ids=("ended association", "valid association"),
    )
    def test_associate_to_user_id_existing(
        self, ended_at, organization_employee_repository
    ):
        # Given
        user = factories.DefaultUserFactory.create()
        employee = factories.OrganizationEmployeeFactory.create()
        factories.UserOrganizationEmployeeFactory.create(
            user=user, organization_employee=employee, ended_at=ended_at
        )

        # When
        with pytest.raises(IntegrityError):
            organization_employee_repository.associate_to_user_id(
                user_id=user.id, employees=[employee]
            )

    def test_get_existing_claims(self, organization_employee_repository):
        # Given
        member = factories.EnterpriseUserFactory.create()
        oe = member.organization_employee
        expected_claims = {member.id}
        # When
        claims = organization_employee_repository.get_existing_claims(id=oe.id)
        # Then
        assert claims == expected_claims

    def test_get_existing_claims_excludes_ended_claims(
        self,
        organization_employee_repository,
        user_organization_employee_repository,
    ):
        # Given
        member = factories.EnterpriseUserFactory.create()
        oe = member.organization_employee
        uoes = user_organization_employee_repository.get_for_organization_employee_id(
            oe.id
        )
        for uoe in uoes:
            uoe.ended_at = datetime.datetime.now(
                tz=datetime.timezone.utc
            ) - datetime.timedelta(days=7)
        # When
        claims = organization_employee_repository.get_existing_claims(id=oe.id)
        # Then
        assert not claims

    def test_get_existing_claims_includes_future_ended_claims(
        self,
        organization_employee_repository,
        user_organization_employee_repository,
    ):
        # Given
        member = factories.EnterpriseUserFactory.create()
        oe = member.organization_employee
        uoes = user_organization_employee_repository.get_for_organization_employee_id(
            oe.id
        )
        for uoe in uoes:
            uoe.ended_at = datetime.datetime.now(
                tz=datetime.timezone.utc
            ) + datetime.timedelta(days=7)
        expected_claims = {member.id}
        # When
        claims = organization_employee_repository.get_existing_claims(id=oe.id)
        # Then
        assert claims == expected_claims

    def test_get_association_settings(self, organization_employee_repository):
        # Given
        beneficiaries_enabled = True
        oe = factories.OrganizationEmployeeFactory.create(
            json={"beneficiaries_enabled": beneficiaries_enabled},
            organization__employee_only=True,
            organization__medical_plan_only=False,
        )
        org = oe.organization
        expected_settings = OrganizationAssociationSettings(
            organization_id=org.id,
            employee_only=org.employee_only,
            medical_plan_only=org.medical_plan_only,
            beneficiaries_enabled=beneficiaries_enabled,
        )
        # When
        settings = organization_employee_repository.get_association_settings(
            id=oe.id,
        )
        # Then
        assert settings == expected_settings

    def test_get_association_settings_none(self, organization_employee_repository):
        # Given
        factories.OrganizationFactory.create()
        # When
        settings = organization_employee_repository.get_association_settings(id=1)
        # Then
        assert settings is None


class TestUserOrganizationEmployeeRepository:
    def test_get(self, user_organization_employee_repository):
        # Given
        given_uoe = factories.UserOrganizationEmployeeFactory.create()
        # When
        fetched_uoe = user_organization_employee_repository.get(id=given_uoe.id)
        # Then
        assert fetched_uoe == given_uoe

    def test_get_user_for_organization_employee_id(
        self, user_organization_employee_repository
    ):
        # Given
        test_org_employee = factories.OrganizationEmployeeFactory.create(id=123)
        test_user_record = factories.DefaultUserFactory.create(id=234)
        factories.UserOrganizationEmployeeFactory.create(
            user=test_user_record, organization_employee=test_org_employee
        )

        # When
        fetched_users = (
            user_organization_employee_repository.get_for_organization_employee_id(
                test_org_employee.id
            )
        )

        # Then
        assert fetched_users[0].user_id == test_user_record.id

    @pytest.mark.parametrize(
        argnames="end_date_1,end_date_2",
        argvalues=[
            (
                datetime.datetime.utcnow() - datetime.timedelta(days=7),
                datetime.datetime.utcnow() - datetime.timedelta(days=7),
            ),
            (datetime.datetime.utcnow() - datetime.timedelta(days=7), None),
            (
                datetime.datetime.utcnow() - datetime.timedelta(days=7),
                datetime.datetime.utcnow() + datetime.timedelta(days=7),
            ),
            (
                datetime.datetime.utcnow() + datetime.timedelta(days=7),
                datetime.datetime.utcnow() - datetime.timedelta(days=7),
            ),
            (
                datetime.datetime.utcnow() + datetime.timedelta(days=7),
                datetime.datetime.utcnow() + datetime.timedelta(days=7),
            ),
            (datetime.datetime.utcnow() + datetime.timedelta(days=7), None),
            (None, None),
        ],
        ids=(
            "both_past_end_date",
            "past_end_date_and_none",
            "past_end_date_and_within_end_date",
            "within_end_date_and_past_end_date",
            "both_within_end_date",
            "within_end_date_and_no_end_date",
            "both_no_end_date",
        ),
    )
    def test_reset_user_associations(
        self,
        end_date_1: datetime.datetime | None,
        end_date_2: datetime.datetime | None,
        user_organization_employee_repository: UserOrganizationEmployeeRepository,
    ):
        # Given
        user = factories.EnterpriseUserFactory.create()
        uoe_1 = factories.UserOrganizationEmployeeFactory.create(
            user=user, ended_at=end_date_1
        )
        uoe_2 = factories.UserOrganizationEmployeeFactory.create(
            user=user, ended_at=end_date_2
        )

        # When
        user_organization_employee_repository.reset_user_associations(
            uoe_1.user_id,
            organization_employee_ids=[
                uoe_1.organization_employee_id,
                uoe_2.organization_employee_id,
            ],
        )

        # Then
        fetched_uoe_1 = user_organization_employee_repository.get(id=uoe_1.id)
        fetched_uoe_2 = user_organization_employee_repository.get(id=uoe_2.id)
        assert fetched_uoe_1.ended_at is None
        assert fetched_uoe_2.ended_at is None

    def test_reset_user_associations_none_uoe_logs_doesnt_raise_error(
        self,
        user_organization_employee_repository,
    ):
        # Given nothing - Non-existent UOE
        test_user_id = 333221
        test_oe_id = 122333
        fetched_uoe_list = (
            user_organization_employee_repository.get_for_organization_employee_id(
                organization_employee_id=test_oe_id
            )
        )
        assert len(fetched_uoe_list) == 0

        # When
        with mock.patch("eligibility.repository.logger") as logger_mock:
            user_organization_employee_repository.reset_user_associations(
                user_id=test_user_id,
                organization_employee_ids=[test_oe_id],
            )

            # Then nothing - Logged, but no errors are raised so process is not interrupted
            logger_mock.warning.assert_called_with(
                "not all user_organization_employees to reset found",
                user_id=test_user_id,
                organization_employee_ids=[test_oe_id],
            )


class TestOrganizationRepository:
    def test_get_orgs_by_external_ids(self, organization_repository):
        # Given
        idp_id = 1
        given_org = factories.OrganizationFactory.create()
        org_external = factories.OrganizationExternalIDFactory.create(
            organization=given_org, identity_provider_id=idp_id
        )
        expected_ids = [
            (
                given_org.id,
                given_org.name,
                org_external.external_id,
                org_external.identity_provider_id,
            )
        ]
        # When
        fetched_ids = organization_repository.get_orgs_by_external_ids(
            (idp_id, org_external.external_id)
        )
        # Then
        assert fetched_ids == expected_ids

    def test_get_organization_by_user_external_identities(
        self, organization_repository, mock_sso_service
    ):
        # Given
        idp_id = 1
        given_org = factories.OrganizationFactory.create()
        org_external = factories.OrganizationExternalIDFactory.create(
            organization=given_org, identity_provider_id=idp_id
        )
        given_identity = authn_factories.UserExternalIdentityFactory.create(
            identity_provider_id=idp_id,
            external_organization_id=org_external.external_id,
        )
        mock_sso_service.fetch_identities.return_value = [given_identity]
        expected_identity = given_identity
        expected_org_meta = eligibility_factories.OrganizationMetaFactory(
            organization_id=given_org.id,
            organization_name=given_org.name,
            external_id=org_external.external_id,
            identity_provider_id=org_external.identity_provider_id,
        )
        # When
        (
            identity,
            org_meta,
        ) = organization_repository.get_organization_by_user_external_identities(
            user_id=given_identity.user_id,
        )
        # Then
        assert (identity, org_meta) == (expected_identity, expected_org_meta)

    def test_get_organization_by_user_external_identities_no_organization(
        self, organization_repository, mock_sso_service
    ):
        # Given
        idp_id = 1
        given_identity = authn_factories.UserExternalIdentityFactory.create(
            identity_provider_id=idp_id,
        )
        mock_sso_service.fetch_identities.return_value = [given_identity]
        expected_identity = None
        expected_org_meta = None
        # When
        (
            identity,
            org_meta,
        ) = organization_repository.get_organization_by_user_external_identities(
            user_id=given_identity.user_id,
        )
        # Then
        assert (identity, org_meta) == (expected_identity, expected_org_meta)

    def test_get_organization_by_user_external_identities_no_identities(
        self, organization_repository, mock_sso_service
    ):
        # Given
        idp_id = 1
        given_org = factories.OrganizationFactory.create()
        factories.OrganizationExternalIDFactory.create(
            organization=given_org, identity_provider_id=idp_id
        )
        mock_sso_service.fetch_identities.return_value = []
        expected_identity = None
        expected_org_meta = None
        # When
        (
            identity,
            org_meta,
        ) = organization_repository.get_organization_by_user_external_identities(
            user_id=1,
        )
        # Then
        assert (identity, org_meta) == (expected_identity, expected_org_meta)

    def test_get_organization_by_user_external_identities_too_many_identities(
        self, organization_repository, mock_sso_service
    ):
        # Given
        idp_id = 1
        given_identities = authn_factories.UserExternalIdentityFactory.create_batch(
            2,
            identity_provider_id=idp_id,
        )
        mock_sso_service.fetch_identities.return_value = given_identities
        for identity in given_identities:
            org = factories.OrganizationFactory.create()
            factories.OrganizationExternalIDFactory.create(
                organization=org,
                identity_provider_id=idp_id,
                external_id=identity.external_organization_id,
            )
        expected_identity = None
        expected_org_meta = None
        # When
        (
            identity,
            org_meta,
        ) = organization_repository.get_organization_by_user_external_identities(
            user_id=1,
        )
        # Then
        assert (identity, org_meta) == (expected_identity, expected_org_meta)

    def test_get_active_enablements(self, organization_repository):
        # Given
        allowed_tracks = ["pregnancy"]
        org = factories.OrganizationFactory.create(allowed_tracks=allowed_tracks)
        expected_products = {*allowed_tracks}
        # When
        enablements = organization_repository.get_active_enablements(
            organization_id=org.id
        )
        products = {e.product for e in enablements}
        # Then
        assert products == expected_products

    def test_get_active_enablements_bms(self, organization_repository):
        # Given
        org = factories.OrganizationFactory.create(_bms_enabled=True)
        expected_products = {"breast-milk-shipping"}
        # When
        enablements = organization_repository.get_active_enablements(
            organization_id=org.id
        )
        products = {e.product for e in enablements}
        # Then
        assert products == expected_products

    def test_get_eligibility_settings(self, organization_repository):
        # Given
        org = factories.OrganizationFactory.create(
            eligibility_type=OrganizationEligibilityType.STANDARD,
            employee_only=True,
            medical_plan_only=False,
        )
        email_domain = factories.OrganizationEmailDomainFactory.create(organization=org)
        field = factories.OrganizationEligibilityFieldFactory.create(
            organization=org, name="name", label="label"
        )
        expected_settings = EnterpriseEligibilitySettings(
            organization_id=org.id,
            organization_name=org.marketing_name,
            organization_shortname=org.name,
            organization_logo=org.icon,
            eligibility_type=org.eligibility_type,
            employee_only=org.employee_only,
            medical_plan_only=org.medical_plan_only,
            fields=[EligibilityField(name=field.name, label=field.label)],
            email_domains=[
                EmailDomain(
                    domain=email_domain.domain,
                    eligibility_type=OrganizationEligibilityType.CLIENT_SPECIFIC,
                )
            ],
            activated_at=mock.ANY,
        )
        # When
        settings = organization_repository.get_eligibility_settings(
            organization_id=org.id
        )
        # Then
        assert settings == expected_settings

    def test_get_eligibility_settings_by_email(self, organization_repository, faker):
        # Given
        email = faker.email()
        org = factories.OrganizationFactory.create(
            eligibility_type=OrganizationEligibilityType.STANDARD,
            employee_only=True,
            medical_plan_only=False,
        )
        email_domain = factories.OrganizationEmailDomainFactory.create(
            organization=org, domain=email.rsplit("@")[-1]
        )
        field = factories.OrganizationEligibilityFieldFactory.create(
            organization=org, name="name", label="label"
        )
        expected_settings = EnterpriseEligibilitySettings(
            organization_id=org.id,
            organization_name=org.marketing_name,
            organization_shortname=org.name,
            organization_logo=org.icon,
            eligibility_type=org.eligibility_type,
            employee_only=org.employee_only,
            medical_plan_only=org.medical_plan_only,
            fields=[EligibilityField(name=field.name, label=field.label)],
            email_domains=[
                EmailDomain(
                    domain=email_domain.domain,
                    eligibility_type=OrganizationEligibilityType.CLIENT_SPECIFIC,
                )
            ],
            activated_at=mock.ANY,
        )
        # When
        settings = organization_repository.get_eligibility_settings_by_email(
            company_email=email
        )
        # Then
        assert settings == expected_settings

    def test_get_organization_by_name(self, organization_repository):
        # Given
        name = "Redbull Racing"
        expected_org = factories.OrganizationFactory.create(
            name="Redbull Racing",
            eligibility_type=OrganizationEligibilityType.STANDARD,
            employee_only=True,
            medical_plan_only=False,
        )

        # When
        fetched_org = organization_repository.get_organization_by_name(name=name)
        # Then
        assert fetched_org == expected_org

    def test_get_organization_by_display_name(self, organization_repository):
        # Given
        name = "Redbull Racing"
        expected_org = factories.OrganizationFactory.create(
            name="Blah",
            display_name="Redbull Racing",
            eligibility_type=OrganizationEligibilityType.STANDARD,
            employee_only=True,
            medical_plan_only=False,
        )

        # When
        fetched_org = organization_repository.get_organization_by_name(name=name)
        # Then
        assert fetched_org == expected_org

    def test_get_organization_by_name_no_results(self, organization_repository):
        # Given
        name = "Redbull Racing"

        # When
        fetched_org = organization_repository.get_organization_by_name(name=name)
        # Then
        assert fetched_org is None

    def test_get_organization_by_display_name_multi_results(
        self, organization_repository
    ):
        # Given
        name = "Redbull Racing"
        expected_org = factories.OrganizationFactory.create(
            name="Racing",
            display_name="Redbull Racing",
            eligibility_type=OrganizationEligibilityType.STANDARD,
            internal_type=OrganizationType.MAVEN_FOR_MAVEN,
            employee_only=True,
            medical_plan_only=False,
        )
        factories.OrganizationFactory.create(
            name="Test Racing",
            display_name="Redbull Racing",
            eligibility_type=OrganizationEligibilityType.STANDARD,
            internal_type=OrganizationType.TEST,
            employee_only=True,
            medical_plan_only=False,
        )

        # When
        fetched_org = organization_repository.get_organization_by_name(name=name)
        # Then
        assert fetched_org == expected_org

    def test_get_organization_by_display_name_multi_valid_results(
        self, organization_repository
    ):
        # Given
        name = "Redbull Racing"
        valid_org_1 = factories.OrganizationFactory.create(
            name="Racing",
            display_name="Redbull Racing",
            eligibility_type=OrganizationEligibilityType.STANDARD,
            internal_type=OrganizationType.REAL,
            employee_only=True,
            medical_plan_only=False,
        )
        valid_org_2 = factories.OrganizationFactory.create(
            name="Test Racing",
            display_name="Redbull Racing",
            eligibility_type=OrganizationEligibilityType.STANDARD,
            internal_type=OrganizationType.REAL,
            employee_only=True,
            medical_plan_only=False,
        )
        expected_org = valid_org_1 if valid_org_1.id < valid_org_2.id else valid_org_2

        # When
        fetched_org = organization_repository.get_organization_by_name(name=name)
        # Then
        assert fetched_org == expected_org


class TestEligibilityMemberRepository:
    def test_create_and_get_verification_for_user(
        self, mock_e9y_service, mock_redis_ttl_cache
    ):
        # Given
        user = factories.DefaultUserFactory.create(id=123)
        repository = EligibilityMemberRepository()
        repository.grpc = mock_e9y_service
        repository.verification_cache = mock_redis_ttl_cache

        ev = model.EligibilityVerification(
            user_id=123,
            organization_id=123,
            unique_corp_id="test",
            dependent_id="test",
            first_name="test",
            last_name="test",
            date_of_birth=datetime.date(2023, 1, 1),
            email="test",
            work_state="test",
            record={},
            created_at=datetime.datetime(2023, 1, 1),
            verified_at=datetime.datetime(2023, 1, 1),
            verification_type="test",
            is_active=False,
            verification_id=12435,
            effective_range=model.DateRange(
                lower=datetime.date(2020, 1, 1),
                upper=datetime.date(2023, 1, 1),
                upper_inc=True,
                lower_inc=True,
            ),
        )

        # When
        # Create verification
        mock_e9y_service.create_verification.return_value = (ev, None)
        verification = repository.create_verification_for_user(
            user_id=user.id, verification_type="test"
        )

        # Then
        assert verification == ev
        repository.verification_cache.add.assert_called()

        # Given
        # Check caching and our return value conversion
        repository.verification_cache.get.return_value = ev

        # When
        repository.get_verification_for_user(user_id=user.id)

        # Then
        repository.verification_cache.get.assert_called()

    def test_create_and_get_multiple_verifications_for_user(
        self, mock_e9y_service, mock_redis_ttl_cache
    ):
        # Given
        user = factories.DefaultUserFactory.create(id=123)
        repository = EligibilityMemberRepository()
        repository.grpc = mock_e9y_service
        repository.verification_overeligibility_cache = mock_redis_ttl_cache

        member1 = model.EligibilityMember(
            id=101,
            organization_id=111,
            unique_corp_id="test1",
            first_name="test",
            last_name="test",
            date_of_birth=datetime.date(2023, 1, 1),
            email="test1",
            work_state="test",
            file_id=None,
            dependent_id="121",
            created_at=datetime.datetime(2023, 1, 1),
            updated_at=datetime.datetime(2023, 1, 1),
            record={},
            custom_attributes={},
        )

        member2 = model.EligibilityMember(
            id=202,
            organization_id=222,
            unique_corp_id="test2",
            first_name="test",
            last_name="test",
            date_of_birth=datetime.date(2023, 1, 1),
            email="test2",
            work_state="test",
            file_id=None,
            dependent_id="242",
            created_at=datetime.datetime(2023, 1, 1),
            updated_at=datetime.datetime(2023, 1, 1),
            record={},
            custom_attributes={},
        )

        ev1 = model.EligibilityVerification(
            user_id=101,
            organization_id=111,
            unique_corp_id="test1",
            dependent_id="test1",
            first_name="test",
            last_name="test",
            date_of_birth=datetime.date(2023, 1, 1),
            email="test",
            work_state="test",
            record={},
            created_at=datetime.datetime(2023, 1, 1),
            verified_at=datetime.datetime(2023, 1, 1),
            verification_type="test",
            is_active=True,
            verification_id=12435,
            effective_range=model.DateRange(
                lower=datetime.date(2020, 1, 1),
                upper=datetime.date(2023, 1, 1),
                upper_inc=True,
                lower_inc=True,
            ),
        )

        ev2 = model.EligibilityVerification(
            user_id=101,
            organization_id=222,
            unique_corp_id="test2",
            dependent_id="test2",
            first_name="test",
            last_name="test",
            date_of_birth=datetime.date(2023, 1, 1),
            email="test2",
            work_state="test",
            record={},
            created_at=datetime.datetime(2023, 1, 1),
            verified_at=datetime.datetime(2023, 1, 1),
            verification_type="test",
            is_active=False,
            verification_id=54321,
            effective_range=model.DateRange(
                lower=datetime.date(2020, 1, 1),
                upper=datetime.date(2023, 1, 1),
                upper_inc=True,
                lower_inc=True,
            ),
        )

        # When
        # Create verification
        mock_e9y_service.create_multiple_verifications_for_user.return_value = (
            [ev1, ev2],
            None,
        )
        verifications = repository.create_multiple_verifications_for_user(
            user_id=user.id, verification_type="test", members=[member1, member2]
        )

        # Then
        assert verifications == [ev1, ev2]
        repository.verification_overeligibility_cache.add.assert_called()

        # Given
        # Check caching and our return value conversion
        repository.verification_overeligibility_cache.get.return_value = [ev1, ev2]

        # When
        repository.get_all_verifications_for_user(user_id=user.id)

        # Then
        repository.verification_overeligibility_cache.get.assert_called()

    def test_get_all_verifications_for_user(
        self, mock_e9y_service, mock_redis_ttl_cache
    ):
        # Given
        user = factories.DefaultUserFactory.create(id=123)
        repository = EligibilityMemberRepository()
        repository.grpc = mock_e9y_service
        repository.verification_overeligibility_cache = mock_redis_ttl_cache

        ev_1 = model.EligibilityVerification(
            user_id=123,
            organization_id=123,
            unique_corp_id="test",
            dependent_id="test",
            first_name="test",
            last_name="test",
            date_of_birth=datetime.date(2023, 1, 1),
            email="test",
            work_state="test",
            record={},
            created_at=datetime.datetime(2023, 1, 1),
            verified_at=datetime.datetime(2023, 1, 1),
            verification_type="test",
            is_active=False,
            verification_id=12435,
            effective_range=model.DateRange(
                lower=datetime.date(2020, 1, 1),
                upper=datetime.date(2023, 1, 1),
                upper_inc=True,
                lower_inc=True,
            ),
        )
        ev_2 = model.EligibilityVerification(
            user_id=123,
            organization_id=223,
            unique_corp_id="test2",
            dependent_id="test2",
            first_name="test2",
            last_name="test2",
            date_of_birth=datetime.date(2023, 1, 1),
            email="test2",
            work_state="test2",
            record={},
            created_at=datetime.datetime(2023, 1, 1),
            verified_at=datetime.datetime(2023, 1, 1),
            verification_type="test2",
            is_active=False,
            verification_id=22435,
            effective_range=model.DateRange(
                lower=datetime.date(2020, 1, 1),
                upper=datetime.date(2023, 1, 1),
                upper_inc=True,
                lower_inc=True,
            ),
        )

        # Given
        # Check caching and our return value conversion
        mock_e9y_service.get_all_verifications.return_value = [ev_1, ev_2]

        # When
        res = repository.get_all_verifications_for_user(user_id=user.id)

        # then
        assert res == [ev_1, ev_2]
        assert repository.verification_overeligibility_cache.add.call_count == 2

        # test read from cache if cache exists
        # When
        repository.verification_overeligibility_cache.get.return_value = [ev_1, ev_2]
        mock_e9y_service.get_all_verifications.reset_mock()
        repository.get_all_verifications_for_user(user_id=user.id)

        # Then
        mock_e9y_service.get_all_verifications.assert_not_called()

    def test_get_all_verifications_for_user_with_org_id(
        self, mock_e9y_service, mock_redis_ttl_cache
    ):
        # Given
        user = factories.DefaultUserFactory.create(id=123)
        repository = EligibilityMemberRepository()
        repository.grpc = mock_e9y_service
        repository.verification_overeligibility_cache = mock_redis_ttl_cache

        ev_1 = model.EligibilityVerification(
            user_id=123,
            organization_id=123,
            unique_corp_id="test",
            dependent_id="test",
            first_name="test",
            last_name="test",
            date_of_birth=datetime.date(2023, 1, 1),
            email="test",
            work_state="test",
            record={},
            created_at=datetime.datetime(2023, 1, 1),
            verified_at=datetime.datetime(2023, 1, 1),
            verification_type="test",
            is_active=False,
            verification_id=12435,
            effective_range=model.DateRange(
                lower=datetime.date(2020, 1, 1),
                upper=datetime.date(2023, 1, 1),
                upper_inc=True,
                lower_inc=True,
            ),
        )

        # Given
        # only 1 verification exists
        mock_e9y_service.get_all_verifications.return_value = [ev_1]

        # When
        res = repository.get_all_verifications_for_user(user_id=user.id)

        # then
        assert res == [ev_1]
        assert repository.verification_overeligibility_cache.add.call_count == 2

        # test read from cache with org_id will fail
        # When
        repository.verification_overeligibility_cache.get.return_value = []
        mock_e9y_service.get_all_verifications.reset_mock()
        repository.get_all_verifications_for_user(
            user_id=user.id, organization_ids=[223]
        )

        # Then
        mock_e9y_service.get_all_verifications.assert_called()
        assert (
            repository.verification_overeligibility_cache.add.call_count == 4
        )  # 2 calls for first request + 2 calls for second request

    def test_create_and_get_verification_for_user_error(
        self, mock_e9y_service, mock_redis_ttl_cache
    ):
        # Given
        user = factories.DefaultUserFactory.create(id=123)
        repository = EligibilityMemberRepository()
        repository.grpc = mock_e9y_service
        repository.verification_cache = mock_redis_ttl_cache

        # When
        # Ensure we raise an error if there's a verification creation error
        mock_e9y_service.create_verification.return_value = (None, "Error")
        with pytest.raises(Exception):  # noqa B017
            repository.create_verification_for_user(
                user_id=user.id, verification_type="test"
            )

    def test_create_and_get_multiple_verifications_for_user_error(
        self,
        mock_e9y_service,
        mock_redis_ttl_cache,
    ):
        # Given
        user = factories.DefaultUserFactory.create(id=123)

        member1 = model.EligibilityMember(
            id=101,
            organization_id=111,
            unique_corp_id="test1",
            first_name="test",
            last_name="test",
            date_of_birth=datetime.date(2023, 1, 1),
            email="test1",
            work_state="test",
            file_id=None,
            dependent_id="121",
            created_at=datetime.datetime(2023, 1, 1),
            updated_at=datetime.datetime(2023, 1, 1),
            record={},
            custom_attributes={},
        )

        member2 = model.EligibilityMember(
            id=202,
            organization_id=222,
            unique_corp_id="test2",
            first_name="test",
            last_name="test",
            date_of_birth=datetime.date(2023, 1, 1),
            email="test2",
            work_state="test",
            file_id=None,
            dependent_id="242",
            created_at=datetime.datetime(2023, 1, 1),
            updated_at=datetime.datetime(2023, 1, 1),
            record={},
            custom_attributes={},
        )
        repository = EligibilityMemberRepository()
        repository.grpc = mock_e9y_service
        repository.verification_overeligibility_cache = mock_redis_ttl_cache

        # When
        # Ensure we raise an error if there's a verification creation error
        mock_e9y_service.create_multiple_verifications_for_user.return_value = (
            None,
            "Error",
        )
        with pytest.raises(Exception):  # noqa B017
            repository.create_multiple_verifications_for_user(
                user_id=user.id, verification_type="test", members=[member1, member2]
            )

    def test_get_other_user_ids_in_family(self, mock_e9y_service):
        # Given
        user = factories.DefaultUserFactory.create(id=123)
        repository = EligibilityMemberRepository()
        repository.grpc = mock_e9y_service
        mock_e9y_service.get_other_user_ids_in_family.return_value = [1]

        # When
        user_ids = repository.get_other_user_ids_in_family(user_id=user.id)

        # Then
        assert user_ids

    def test_deactivate_verification_for_user_success(self, mock_e9y_service):
        # Given
        user = factories.DefaultUserFactory.create(id=123)
        repository = EligibilityMemberRepository()
        repository.grpc = mock_e9y_service

        # Create a mock verification with required attributes
        mock_verification = model.EligibilityVerification(
            user_id=123,
            organization_id=123,
            unique_corp_id="test",
            dependent_id="test",
            first_name="test",
            last_name="test",
            date_of_birth=datetime.date(2023, 1, 1),
            email="test",
            work_state="test",
            record={},
            created_at=datetime.datetime(2023, 1, 1),
            verified_at=datetime.datetime(2023, 1, 1),
            verification_type="test",
            is_active=False,
            verification_id=1,
            effective_range=model.DateRange(
                lower=datetime.date(2020, 1, 1),
                upper=datetime.date(2023, 1, 1),
                upper_inc=True,
                lower_inc=True,
            ),
        )

        # When
        mock_e9y_service.deactivate_verification.return_value = mock_verification
        result = repository.deactivate_verification_for_user(
            user_id=user.id, verification_id=1
        )

        # Then
        assert result == 1
        mock_e9y_service.deactivate_verification.assert_called_once()

    def test_deactivate_verification_for_user_failure(self, mock_e9y_service):
        # Given
        user = factories.DefaultUserFactory.create(id=123)
        repository = EligibilityMemberRepository()
        repository.grpc = mock_e9y_service

        # When
        mock_e9y_service.deactivate_verification.return_value = None
        result = repository.deactivate_verification_for_user(
            user_id=user.id, verification_id=1
        )
        # Then
        assert result == -1

    def test_create_member_records_for_org_failure(self, mock_e9y_service):
        # Given
        organization_id = 1
        repository = EligibilityMemberRepository()
        repository.grpc = mock_e9y_service

        # When
        mock_e9y_service.create_test_members_records_for_org.return_value = []
        result = repository.create_test_member_records_for_organization(
            organization_id=organization_id, test_member_records=[]
        )
        # Then
        assert result == []

    def test_create_member_records_for_org_success(self, mock_e9y_service):
        # Given
        organization_id = 1
        repository = EligibilityMemberRepository()
        repository.grpc = mock_e9y_service
        member = factories.MemberFactory.create(id=123)

        # When
        mock_e9y_service.create_test_members_records_for_org.return_value = [member]
        result = repository.create_test_member_records_for_organization(
            organization_id=organization_id, test_member_records=[]
        )
        # Then
        assert len(result) == 1

    def test_get_by_no_dob_verification_success(self, mock_e9y_service):
        # Given
        repository = EligibilityMemberRepository()
        repository.grpc = mock_e9y_service
        member = factories.MemberFactory.create(id=123)

        # When
        mock_e9y_service.no_dob_verification.return_value = [member]
        result = repository.get_by_no_dob_verification(
            email="foo@bar.net",
            first_name="John",
            last_name="Doe",
        )
        # Then
        assert result == [member]

    def test_get_by_no_dob_verification_failure(self, mock_e9y_service):
        # Given
        repository = EligibilityMemberRepository()
        repository.grpc = mock_e9y_service

        # When
        mock_e9y_service.no_dob_verification.return_value = None
        result = repository.get_by_no_dob_verification(
            email="foo@bar.net",
            first_name="John",
            last_name="Doe",
        )
        # Then
        assert result is None

    def test_get_by_no_dob_verification_error(self, mock_e9y_service):
        # Given
        repository = EligibilityMemberRepository()
        repository.grpc = mock_e9y_service

        # When
        # TODO raise error when calling no_dob_verification
        mock_e9y_service.no_dob_verification.side_effect = Exception("Error occurred")

        with pytest.raises(Exception):  # noqa B017
            repository.get_by_no_dob_verification(
                organization_id=1,
                email="foo@bar.net",
                first_name="John",
                last_name="Doe",
                unique_corp_id="corpid",
            )

    def test_get_by_basic_verification_success(self, mock_e9y_service):
        # Given
        repository = EligibilityMemberRepository()
        repository.grpc = mock_e9y_service
        member = factories.MemberFactory.create(
            first_name="Princess",
            last_name="Zelda",
            date_of_birth=datetime.date(1990, 1, 1),
        )

        # When
        mock_e9y_service.basic.return_value = [member]
        result = repository.get_by_basic_verification(
            first_name="Princess",
            last_name="Zelda",
            date_of_birth=datetime.date(1990, 1, 1),
        )
        # Then
        assert result == [member]

    def test_get_by_basic_verification_failure(self, mock_e9y_service):
        # Given
        repository = EligibilityMemberRepository()
        repository.grpc = mock_e9y_service

        # When
        mock_e9y_service.basic.return_value = None
        result = repository.get_by_basic_verification(
            date_of_birth=datetime.date(1990, 1, 1),
            first_name="John",
            last_name="Doe",
        )
        # Then
        assert result is None

    def test_get_by_healthplan_verification_success(self, mock_e9y_service):
        # Given
        repository = EligibilityMemberRepository()
        repository.grpc = mock_e9y_service
        member = factories.MemberFactory.create(
            first_name="Princess",
            last_name="Zelda",
            date_of_birth=datetime.date(1990, 1, 1),
        )

        # When
        mock_e9y_service.healthplan.return_value = member
        result = repository.get_by_healthplan_verification(
            first_name="Princess",
            last_name="Zelda",
            date_of_birth=datetime.date(1990, 1, 1),
            subscriber_id="test-id",
        )
        # Then
        assert result == member

    def test_get_by_healthplan_verification_failure(self, mock_e9y_service):
        # Given
        repository = EligibilityMemberRepository()
        repository.grpc = mock_e9y_service

        # When
        mock_e9y_service.healthplan.return_value = None
        result = repository.get_by_healthplan_verification(
            date_of_birth=datetime.date(1990, 1, 1),
            first_name="John",
            last_name="Doe",
            subscriber_id="test-id",
        )
        # Then
        assert result is None

    def test_get_by_employer_verification_success(self, mock_e9y_service):
        # Given
        repository = EligibilityMemberRepository()
        repository.grpc = mock_e9y_service
        member = factories.MemberFactory.create(
            first_name="mock_first",
            last_name="mock_last",
            date_of_birth=datetime.date(1990, 1, 1),
        )

        # When
        mock_e9y_service.employer.return_value = member
        result = repository.get_by_employer_verification(
            company_email="foo@bar.net",
            date_of_birth=datetime.date(1990, 1, 1),
            dependent_date_of_birth=datetime.date(1990, 1, 1),
            employee_first_name="employee_first_name",
            employee_last_name="employee_last_name",
            first_name="first_name",
            last_name="last_name",
            work_state="CA",
        )
        # Then
        assert result == member

    def test_get_by_employer_verification_failure(self, mock_e9y_service):
        # Given
        repository = EligibilityMemberRepository()
        repository.grpc = mock_e9y_service

        # When
        mock_e9y_service.employer.return_value = None
        result = repository.get_by_employer_verification(
            company_email="foo@bar.net",
            date_of_birth=datetime.date(1990, 1, 1),
            dependent_date_of_birth=datetime.date(1990, 1, 1),
            employee_first_name="employee_first_name",
            employee_last_name="employee_last_name",
            first_name="first_name",
            last_name="last_name",
            work_state="CA",
        )
        # Then
        assert result is None

    def test_is_verification_live(self, mock_e9y_service):
        # Given
        repository = EligibilityMemberRepository()
        today = datetime.date.today()

        # Test with no effective range
        verification_no_range = model.EligibilityVerification(
            user_id=123,
            organization_id=123,
            unique_corp_id="test",
            dependent_id="test",
            first_name="test",
            last_name="test",
            date_of_birth=datetime.date(2023, 1, 1),
            email="test",
            work_state="test",
            record={},
            created_at=datetime.datetime(2023, 1, 1),
            verified_at=datetime.datetime(2023, 1, 1),
            verification_type="test",
            is_active=True,
            verification_id=12435,
        )
        assert not repository._is_verification_live(verification_no_range)

        # Test with effective range that includes today (lower inclusive, upper exclusive)
        verification_live = model.EligibilityVerification(
            user_id=123,
            organization_id=123,
            unique_corp_id="test",
            dependent_id="test",
            first_name="test",
            last_name="test",
            date_of_birth=datetime.date(2023, 1, 1),
            email="test",
            work_state="test",
            record={},
            created_at=datetime.datetime(2023, 1, 1),
            verified_at=datetime.datetime(2023, 1, 1),
            verification_type="test",
            is_active=True,
            verification_id=12435,
            effective_range=model.DateRange(
                lower=today - datetime.timedelta(days=30),
                upper=today + datetime.timedelta(days=30),
                lower_inc=True,
                upper_inc=False,
            ),
        )
        assert repository._is_verification_live(verification_live)

        # Test with effective range that excludes today (lower inclusive, upper exclusive)
        verification_expired = model.EligibilityVerification(
            user_id=123,
            organization_id=123,
            unique_corp_id="test",
            dependent_id="test",
            first_name="test",
            last_name="test",
            date_of_birth=datetime.date(2023, 1, 1),
            email="test",
            work_state="test",
            record={},
            created_at=datetime.datetime(2023, 1, 1),
            verified_at=datetime.datetime(2023, 1, 1),
            verification_type="test",
            is_active=True,
            verification_id=12435,
            effective_range=model.DateRange(
                lower=today - datetime.timedelta(days=60),
                upper=today,
                lower_inc=True,
                upper_inc=False,
            ),
        )
        assert not repository._is_verification_live(verification_expired)

        # Test with infinite effective range
        verification_infinite = model.EligibilityVerification(
            user_id=123,
            organization_id=123,
            unique_corp_id="test",
            dependent_id="test",
            first_name="test",
            last_name="test",
            date_of_birth=datetime.date(2023, 1, 1),
            email="test",
            work_state="test",
            record={},
            created_at=datetime.datetime(2023, 1, 1),
            verified_at=datetime.datetime(2023, 1, 1),
            verification_type="test",
            is_active=True,
            verification_id=12435,
            effective_range=model.DateRange(
                lower=None,
                upper=None,
                lower_inc=None,
                upper_inc=None,
            ),
        )
        assert repository._is_verification_live(verification_infinite)

        # Test with only lower bound (inclusive)
        verification_only_lower = model.EligibilityVerification(
            user_id=123,
            organization_id=123,
            unique_corp_id="test",
            dependent_id="test",
            first_name="test",
            last_name="test",
            date_of_birth=datetime.date(2023, 1, 1),
            email="test",
            work_state="test",
            record={},
            created_at=datetime.datetime(2023, 1, 1),
            verified_at=datetime.datetime(2023, 1, 1),
            verification_type="test",
            is_active=True,
            verification_id=12435,
            effective_range=model.DateRange(
                lower=today - datetime.timedelta(days=30),
                upper=None,
                lower_inc=True,
                upper_inc=None,
            ),
        )
        assert repository._is_verification_live(verification_only_lower)

        # Test with only upper bound (exclusive)
        verification_only_upper = model.EligibilityVerification(
            user_id=123,
            organization_id=123,
            unique_corp_id="test",
            dependent_id="test",
            first_name="test",
            last_name="test",
            date_of_birth=datetime.date(2023, 1, 1),
            email="test",
            work_state="test",
            record={},
            created_at=datetime.datetime(2023, 1, 1),
            verified_at=datetime.datetime(2023, 1, 1),
            verification_type="test",
            is_active=True,
            verification_id=12435,
            effective_range=model.DateRange(
                lower=None,
                upper=today + datetime.timedelta(days=30),
                lower_inc=None,
                upper_inc=False,
            ),
        )
        assert repository._is_verification_live(verification_only_upper)

        # Test with today exactly on lower bound (inclusive)
        verification_exact_lower = model.EligibilityVerification(
            user_id=123,
            organization_id=123,
            unique_corp_id="test",
            dependent_id="test",
            first_name="test",
            last_name="test",
            date_of_birth=datetime.date(2023, 1, 1),
            email="test",
            work_state="test",
            record={},
            created_at=datetime.datetime(2023, 1, 1),
            verified_at=datetime.datetime(2023, 1, 1),
            verification_type="test",
            is_active=True,
            verification_id=12435,
            effective_range=model.DateRange(
                lower=today,
                upper=today + datetime.timedelta(days=30),
                lower_inc=True,
                upper_inc=False,
            ),
        )
        assert repository._is_verification_live(verification_exact_lower)

        # Test with today exactly on upper bound (exclusive)
        verification_exact_upper = model.EligibilityVerification(
            user_id=123,
            organization_id=123,
            unique_corp_id="test",
            dependent_id="test",
            first_name="test",
            last_name="test",
            date_of_birth=datetime.date(2023, 1, 1),
            email="test",
            work_state="test",
            record={},
            created_at=datetime.datetime(2023, 1, 1),
            verified_at=datetime.datetime(2023, 1, 1),
            verification_type="test",
            is_active=True,
            verification_id=12435,
            effective_range=model.DateRange(
                lower=today - datetime.timedelta(days=30),
                upper=today,
                lower_inc=True,
                upper_inc=False,
            ),
        )
        assert not repository._is_verification_live(verification_exact_upper)

        # Test with today between bounds
        verification_between = model.EligibilityVerification(
            user_id=123,
            organization_id=123,
            unique_corp_id="test",
            dependent_id="test",
            first_name="test",
            last_name="test",
            date_of_birth=datetime.date(2023, 1, 1),
            email="test",
            work_state="test",
            record={},
            created_at=datetime.datetime(2023, 1, 1),
            verified_at=datetime.datetime(2023, 1, 1),
            verification_type="test",
            is_active=True,
            verification_id=12435,
            effective_range=model.DateRange(
                lower=today - datetime.timedelta(days=15),
                upper=today + datetime.timedelta(days=15),
                lower_inc=True,
                upper_inc=False,
            ),
        )
        assert repository._is_verification_live(verification_between)

    def test_build_single_verification_cache_key(self, mock_e9y_service):
        # Given
        repository = EligibilityMemberRepository()

        # Test with different user IDs
        key1 = repository._build_single_verification_cache_key(
            user_id=123,
            active_eligibility_only=False,
        )
        key2 = repository._build_single_verification_cache_key(
            user_id=456,
            active_eligibility_only=False,
        )
        assert key1 != key2

        # Test with different active_eligibility_only values
        key3 = repository._build_single_verification_cache_key(
            user_id=123,
            active_eligibility_only=True,
        )
        assert key1 != key3

        # Test with same parameters
        key4 = repository._build_single_verification_cache_key(
            user_id=123,
            active_eligibility_only=False,
        )
        assert key1 == key4

    def test_build_multiple_verifications_cache_key(self, mock_e9y_service):
        # Given
        repository = EligibilityMemberRepository()

        # Test with different user IDs
        key1 = repository._build_multiple_verifications_cache_key(
            user_id=123,
            organization_ids=[1, 2, 3],
            active_verifications_only=False,
        )
        key2 = repository._build_multiple_verifications_cache_key(
            user_id=456,
            organization_ids=[1, 2, 3],
            active_verifications_only=False,
        )
        assert key1 != key2

        # Test with different organization IDs
        key3 = repository._build_multiple_verifications_cache_key(
            user_id=123,
            organization_ids=[4, 5, 6],
            active_verifications_only=False,
        )
        assert key1 != key3

        # Test with different active_verifications_only values
        key4 = repository._build_multiple_verifications_cache_key(
            user_id=123,
            organization_ids=[1, 2, 3],
            active_verifications_only=True,
        )
        assert key1 != key4

        # Test with same parameters
        key5 = repository._build_multiple_verifications_cache_key(
            user_id=123,
            organization_ids=[1, 2, 3],
            active_verifications_only=False,
        )
        assert key1 == key5

        # Test with different order of organization IDs
        key6 = repository._build_multiple_verifications_cache_key(
            user_id=123,
            organization_ids=[3, 2, 1],
            active_verifications_only=False,
        )
        assert key1 == key6

        # Test with duplicate organization IDs
        key7 = repository._build_multiple_verifications_cache_key(
            user_id=123,
            organization_ids=[1, 2, 3, 3, 2, 1],
            active_verifications_only=False,
        )
        assert key1 == key7

        # Test with None organization IDs
        key8 = repository._build_multiple_verifications_cache_key(
            user_id=123,
            organization_ids=None,
            active_verifications_only=False,
        )
        assert key8 != key1
