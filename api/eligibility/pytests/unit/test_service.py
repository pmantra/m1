from __future__ import annotations

import contextlib
import copy
import datetime
import json
import os
from typing import Dict, List
from unittest import mock
from unittest.mock import patch

import pytest
import sqlalchemy.exc

from eligibility import EnterpriseVerificationService, _empty_or_equal, service
from eligibility.e9y import (
    DateRange,
    EligibilityMember,
    EligibilityVerification,
    PreEligibilityResponse,
)
from eligibility.e9y import model as e9y_model
from eligibility.pytests import factories
from eligibility.pytests import factories as e9y_factories
from eligibility.pytests.factories import EligibilityMemberFactory, VerificationFactory
from eligibility.repository import (
    EmployeeInfo,
    EnterpriseEligibilitySettings,
    OrganizationAssociationSettings,
    OrganizationEligibilityType,
)
from eligibility.service import (
    EnterpriseVerificationFilelessError,
    EnterpriseVerificationOverEligibilityError,
    EnterpriseVerificationQueryError,
    compare_verifications,
)
from eligibility.utils import verification_utils
from eligibility.utils.verification_utils import VerificationParams
from models.enterprise import MatchType, Organization, OrganizationEmployee
from pytests.factories import OrganizationEmployeeFactory, OrganizationFactory


@pytest.fixture
def patch_report_last_eligible_through_organization():
    with mock.patch(
        "tasks.braze.report_last_eligible_through_organization"
    ) as report_last_eligible_through_organization:
        yield report_last_eligible_through_organization


@pytest.fixture()
def mock_get_multiple_orgs_for_user(request):
    num_orgs = request.param
    orgs = []
    for index in range(num_orgs):
        org = OrganizationFactory.create(
            name=f"org{index}",
        )
        orgs.append(org)
    return orgs


class TestVerifyMemberSSO:
    def test_verification_succeeds(self, eligibility_service):
        # Given
        org_id = 1
        identity = factories.DummyIdentityFactory.create()
        org_meta = factories.OrganizationMetaFactory.create(organization_id=org_id)
        eligibility_service.sso.fetch_identities.return_value = [identity]
        eligibility_service.orgs.get_organization_by_user_external_identities.return_value = (
            identity,
            org_meta,
        )
        expected_call = mock.call(
            unique_corp_id=identity.unique_corp_id,
            dependent_id=mock.ANY,
            organization_id=org_id,
            metadata=mock.ANY,
        )
        # When
        eligibility_service.verify_member_sso(user_id=1)
        # Then
        assert eligibility_service.e9y.get_by_org_identity.call_args == expected_call

    def test_no_identities(self, eligibility_service):
        # Given
        eligibility_service.orgs.get_organization_by_user_external_identities.return_value = (
            None,
            None,
        )
        # When
        located = eligibility_service.verify_member_sso(user_id=1)
        # Then
        assert located is None


class TestVerifyMemberClientSpecific:
    def test_verification(self, eligibility_service):
        # Given
        kwargs = factories.ClientSpecificParams.create()
        expected_call = mock.call(**kwargs, metadata=mock.ANY)
        # When
        eligibility_service.verify_member_client_specific(**kwargs)
        # Then
        assert eligibility_service.e9y.get_by_client_specific.call_args == expected_call


class TestVerifyMemberStandard:
    @pytest.fixture(params=["no-dependent-dob", "dependent-dob"])
    def success_case(self, request, faker):
        params = factories.StandardVerificationParams.create()
        expected_call = mock.call(**params, metadata=mock.ANY)
        if request.param == "no-dependent-dob":
            return expected_call, params

        params["dependent_date_of_birth"] = params.pop("date_of_birth")
        params["date_of_birth"] = faker.date_of_birth()
        return expected_call, params

    def test_verification_succeeds(self, eligibility_service, success_case):
        # Given
        expected_call, params = success_case
        # When
        eligibility_service.verify_member_standard(**params)
        # Then
        assert (
            eligibility_service.e9y.get_by_standard_verification.call_args
            == expected_call
        )

    def test_verification_succeeds_dep_dob_fallthrough(
        self, eligibility_service, faker
    ):
        # Given
        params = factories.StandardVerificationParams.create()
        date_of_birth = params.pop("date_of_birth")
        dependent_date_of_birth = faker.date_of_birth()
        expected_calls = [
            mock.call(
                date_of_birth=dependent_date_of_birth,
                **params,
                metadata=mock.ANY,
            ),
            mock.call(
                date_of_birth=date_of_birth,
                **params,
                metadata=mock.ANY,
            ),
        ]
        eligibility_service.e9y.get_by_standard_verification.side_effect = iter(
            [None, mock.MagicMock()]
        )
        # When
        eligibility_service.verify_member_standard(
            date_of_birth=date_of_birth,
            dependent_date_of_birth=dependent_date_of_birth,
            **params,
        )
        # Then
        eligibility_service.e9y.get_by_standard_verification.assert_has_calls(
            expected_calls
        )


class TestVerifyMemberAlternate:
    @pytest.fixture(params=["no-dependent-dob", "dependent-dob"])
    def success_case(self, request, faker):
        params = factories.AlternateVerificationParams.create()
        expected_call = mock.call(**params, metadata=mock.ANY)
        if request.param == "no-dependent-dob":
            return expected_call, params

        params["dependent_date_of_birth"] = params.pop("date_of_birth")
        params["date_of_birth"] = faker.date_of_birth()
        return expected_call, params

    def test_verification_succeeds(self, eligibility_service, success_case):
        # Given
        expected_call, params = success_case
        # When
        eligibility_service.verify_member_alternate(**params)
        # Then
        assert (
            eligibility_service.e9y.get_by_alternate_verification.call_args
            == expected_call
        )

    def test_verification_succeeds_dep_dob_fallthrough(
        self, eligibility_service, faker
    ):
        # Given
        params = factories.AlternateVerificationParams.create()
        date_of_birth = params.pop("date_of_birth")
        dependent_date_of_birth = faker.date_of_birth()
        expected_calls = [
            mock.call(
                date_of_birth=dependent_date_of_birth,
                **params,
                metadata=mock.ANY,
            ),
            mock.call(
                date_of_birth=date_of_birth,
                **params,
                metadata=mock.ANY,
            ),
        ]
        eligibility_service.e9y.get_by_alternate_verification.side_effect = iter(
            [None, mock.MagicMock()]
        )
        # When
        eligibility_service.verify_member_alternate(
            date_of_birth=date_of_birth,
            dependent_date_of_birth=dependent_date_of_birth,
            **params,
        )
        # Then
        assert (
            eligibility_service.e9y.get_by_alternate_verification.call_args_list
            == expected_calls
        )


class TestVerifyMemberMultistep:
    def test_verify_alternate_succeeds(
        self,
        eligibility_service,
    ):
        # Given
        params = factories.AlternateVerificationParams.create()
        eligibility_service.e9y.get_by_alternate_verification.side_effect = iter(
            [mock.MagicMock()]
        )
        expected_num_alternate_calls = 1
        expected_num_standard_calls = 0
        # When
        eligibility_service.verify_member_multistep(user_id=1, **params)
        # Then
        assert (
            len(eligibility_service.e9y.get_by_alternate_verification.call_args_list)
            == expected_num_alternate_calls
        )
        assert (
            len(eligibility_service.e9y.get_by_standard_verification.call_args_list)
            == expected_num_standard_calls
        )

    def test_verify_alternate_work_state_fallthrough_succeeds(
        self,
        eligibility_service,
    ):
        # Given
        params = factories.AlternateVerificationParams.create()
        eligibility_service.e9y.get_by_alternate_verification.side_effect = iter(
            [None, mock.MagicMock()]
        )
        expected_num_alternate_calls = 2
        expected_num_standard_calls = 0
        # When
        eligibility_service.verify_member_multistep(user_id=1, **params)
        # Then
        assert (
            len(eligibility_service.e9y.get_by_alternate_verification.call_args_list)
            == expected_num_alternate_calls
        )
        assert (
            len(eligibility_service.e9y.get_by_standard_verification.call_args_list)
            == expected_num_standard_calls
        )

    def test_verify_standard_fallthrough_succeeds(
        self,
        eligibility_service,
    ):
        # Given
        params = factories.AlternateVerificationParams.create()
        params.update(factories.StandardVerificationParams.create())
        eligibility_service.e9y.get_by_alternate_verification.side_effect = iter(
            [None, None]
        )
        eligibility_service.e9y.get_by_standard_verification.side_effect = iter(
            [mock.MagicMock()]
        )
        expected_num_alternate_calls = 2
        expected_num_standard_calls = 1
        # When
        eligibility_service.verify_member_multistep(user_id=1, **params)
        # Then
        assert (
            len(eligibility_service.e9y.get_by_alternate_verification.call_args_list)
            == expected_num_alternate_calls
        )
        assert (
            len(eligibility_service.e9y.get_by_standard_verification.call_args_list)
            == expected_num_standard_calls
        )

    def test_verify_standard_only_succeeds(
        self,
        eligibility_service,
    ):
        # Given
        params = factories.StandardVerificationParams.create()
        eligibility_service.e9y.get_by_standard_verification.side_effect = iter(
            [mock.MagicMock()]
        )
        expected_num_alternate_calls = 0
        expected_num_standard_calls = 1
        # When
        eligibility_service.verify_member_multistep(user_id=1, **params)
        # Then
        assert (
            len(eligibility_service.e9y.get_by_alternate_verification.call_args_list)
            == expected_num_alternate_calls
        )
        assert (
            len(eligibility_service.e9y.get_by_standard_verification.call_args_list)
            == expected_num_standard_calls
        )

    def test_verify_missing_necessary_params(
        self,
        eligibility_service,
        faker,
    ):
        # Given
        date_of_birth = faker.date_of_birth()
        eligibility_service.e9y.get_by_standard_verification.side_effect = iter(
            [mock.MagicMock()]
        )
        expected_num_alternate_calls = 0
        expected_num_standard_calls = 0
        # When
        eligibility_service.verify_member_multistep(
            user_id=1,
            date_of_birth=date_of_birth,
        )
        # Then
        assert (
            len(eligibility_service.e9y.get_by_alternate_verification.call_args_list)
            == expected_num_alternate_calls
        )
        assert (
            len(eligibility_service.e9y.get_by_standard_verification.call_args_list)
            == expected_num_standard_calls
        )

    @pytest.mark.parametrize(
        argnames=("param", "value"),
        argvalues=[("first_name", None), ("last_name", None), ("date_of_birth", None)],
        ids=("missing_first_name", "missing_last_name", "missing_date_of_birth"),
    )
    def test_verify_overeligibility_missing_necessary_params(
        self,
        eligibility_service,
        mock_overeligibility_enabled,
        param,
        value,
    ):
        mock_overeligibility_enabled(True)
        params = factories.OvereligibilityVerificationParams.create()
        updated_params = {**params, param: value}
        eligibility_service.e9y.get_by_alternate_verification.side_effect = iter(
            [None, None]
        )
        eligibility_service.e9y.get_by_standard_verification.side_effect = iter([None])
        expected_number_overeligibility_calls = 0
        # When
        eligibility_service.verify_member_multistep(**updated_params)
        # Then
        assert (
            len(
                eligibility_service.e9y.get_by_overeligibility_verification.call_args_list
            )
            == expected_number_overeligibility_calls
        )

    def test_verify_overeligibility_missing_both_optional_params(
        self,
        eligibility_service,
        mock_overeligibility_enabled,
    ):
        mock_overeligibility_enabled(True)
        params = factories.OvereligibilityVerificationParams.create()
        updated_params = {**params, "unique_corp_id": None, "company_email": None}
        eligibility_service.e9y.get_by_alternate_verification.side_effect = iter(
            [None, None]
        )
        eligibility_service.e9y.get_by_standard_verification.side_effect = iter([None])
        expected_number_overeligibility_calls = 0
        # When
        eligibility_service.verify_member_multistep(**updated_params)
        # Then
        assert (
            len(
                eligibility_service.e9y.get_by_overeligibility_verification.call_args_list
            )
            == expected_number_overeligibility_calls
        )

    @pytest.mark.parametrize(
        argnames=("param", "value"),
        argvalues=[("company_email", None), ("first_name", None), ("last_name", None)],
        ids=("missing_company_email", "missing_first_name", "missing_last_name"),
    )
    def test_verify_no_dob_missing_necessary_params(
        self,
        eligibility_service,
        mock_no_dob_verification_enabled,
        param,
        value,
    ):
        mock_no_dob_verification_enabled(True)
        params = factories.NoDOBVerificationParams.create()
        updated_params = {**params, param: value}
        eligibility_service.e9y.get_by_alternate_verification.side_effect = iter(
            [None, None]
        )
        eligibility_service.e9y.get_by_standard_verification.side_effect = iter([None])
        expected_num_no_dob_calls = 0
        # When
        eligibility_service.verify_member_multistep(user_id=1, **updated_params)
        # Then
        assert (
            len(eligibility_service.e9y.get_by_no_dob_verification.call_args_list)
            == expected_num_no_dob_calls
        )


class TestVerifyMemberBasic:
    user_id = 1
    first_name = "mock_first"
    last_name = "mock_last"
    date_of_birth = datetime.date(1990, 1, 1)
    member1 = EligibilityMemberFactory.create()
    member2 = EligibilityMemberFactory.create()
    params = verification_utils.VerificationParams(
        user_id=user_id,
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date_of_birth,
    )

    def test_basic_success(self, eligibility_service):

        eligibility_service.e9y.get_by_basic_verification.side_effect = [
            [TestVerifyMemberBasic.member1]
        ]

        # When
        res = eligibility_service.verify_member_basic(
            params=TestVerifyMemberBasic.params
        )
        eligibility_service.e9y.get_by_basic_verification.assert_called_with(
            first_name=TestVerifyMemberBasic.first_name,
            last_name=TestVerifyMemberBasic.last_name,
            date_of_birth=TestVerifyMemberBasic.date_of_birth,
            user_id=TestVerifyMemberBasic.user_id,
            metadata=mock.ANY,
        )
        assert res == [TestVerifyMemberBasic.member1]

    def test_basic_return_empty_list_if_multiple_found(self, eligibility_service):

        eligibility_service.e9y.get_by_basic_verification.side_effect = [
            [TestVerifyMemberBasic.member1, TestVerifyMemberBasic.member2]
        ]

        # When
        res = eligibility_service.verify_member_basic(
            params=TestVerifyMemberBasic.params
        )
        eligibility_service.e9y.get_by_basic_verification.assert_called_with(
            first_name=TestVerifyMemberBasic.first_name,
            last_name=TestVerifyMemberBasic.last_name,
            date_of_birth=TestVerifyMemberBasic.date_of_birth,
            user_id=TestVerifyMemberBasic.user_id,
            metadata=mock.ANY,
        )
        assert res == []

    def test_basic_no_grpc_call_missing_params(self, eligibility_service):
        params = verification_utils.VerificationParams(
            user_id=TestVerifyMemberBasic.user_id,
        )
        # When
        with pytest.raises(service.EnterpriseVerificationQueryError):
            eligibility_service.verify_member_basic(params=params)
        eligibility_service.e9y.get_by_basic_verification.assert_not_called


class TestVerifyMemberEmployer:
    user_id = 1
    company_email = "mock_company_email"
    date_of_birth = datetime.date(1990, 1, 1)
    first_name = "mock_first_name"
    last_name = "mock_last_name"
    employee_first_name = "mock_employee_first_name"
    employee_last_name = "mock_employee_last_name"
    work_state = "mock_work_state"
    dependent_date_of_birth = datetime.date(1990, 1, 2)
    params = verification_utils.VerificationParams(
        user_id=user_id,
        company_email=company_email,
        date_of_birth=date_of_birth,
        first_name=first_name,
        last_name=last_name,
        employee_first_name=employee_first_name,
        employee_last_name=employee_last_name,
        work_state=work_state,
        dependent_date_of_birth=dependent_date_of_birth,
    )

    def test_employer_success(self, eligibility_service):

        member_found = EligibilityMemberFactory.create()
        eligibility_service.e9y.get_by_employer_verification.side_effect = [
            member_found
        ]

        # When
        res = eligibility_service.verify_member_employer(
            params=TestVerifyMemberEmployer.params
        )
        eligibility_service.e9y.get_by_employer_verification.assert_called_with(
            company_email=TestVerifyMemberEmployer.company_email,
            date_of_birth=TestVerifyMemberEmployer.date_of_birth,
            first_name=TestVerifyMemberEmployer.first_name,
            last_name=TestVerifyMemberEmployer.last_name,
            employee_first_name=TestVerifyMemberEmployer.employee_first_name,
            employee_last_name=TestVerifyMemberEmployer.employee_last_name,
            work_state=TestVerifyMemberEmployer.work_state,
            dependent_date_of_birth=TestVerifyMemberEmployer.dependent_date_of_birth,
            user_id=TestVerifyMemberEmployer.user_id,
            metadata=mock.ANY,
        )
        assert res == [member_found]

    def test_employer_member_not_found(self, eligibility_service):

        eligibility_service.e9y.get_by_employer_verification.side_effect = [None]

        # When
        res = eligibility_service.verify_member_employer(
            params=TestVerifyMemberEmployer.params
        )
        eligibility_service.e9y.get_by_employer_verification.assert_called_with(
            company_email=TestVerifyMemberEmployer.company_email,
            date_of_birth=TestVerifyMemberEmployer.date_of_birth,
            first_name=TestVerifyMemberEmployer.first_name,
            last_name=TestVerifyMemberEmployer.last_name,
            employee_first_name=TestVerifyMemberEmployer.employee_first_name,
            employee_last_name=TestVerifyMemberEmployer.employee_last_name,
            work_state=TestVerifyMemberEmployer.work_state,
            dependent_date_of_birth=TestVerifyMemberEmployer.dependent_date_of_birth,
            user_id=TestVerifyMemberEmployer.user_id,
            metadata=mock.ANY,
        )
        assert res == []

    def test_employer_no_grpc_call_when_param_missing(self, eligibility_service):
        params = verification_utils.VerificationParams(
            user_id=1,
        )
        # When
        with pytest.raises(service.EnterpriseVerificationQueryError):
            eligibility_service.verify_member_employer(params=params)
        eligibility_service.e9y.get_by_employer_verification.assert_not_called


class TestVerifyMemberHealthplan:
    user_id = 1
    unique_corp_id = "mock_unique_corp_id"
    first_name = "mock_first_name"
    last_name = "mock_last_name"
    date_of_birth = datetime.date(1999, 1, 2)
    dependent_date_of_birth = "mock_dependent_date_of_birth"
    employee_first_name = "mock_employee_first_name"
    employee_last_name = "mock_employee_last_name"
    params = verification_utils.VerificationParams(
        user_id=user_id,
        unique_corp_id=unique_corp_id,
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date_of_birth,
        dependent_date_of_birth=dependent_date_of_birth,
        employee_first_name=employee_first_name,
        employee_last_name=employee_last_name,
    )

    def test_healthplan_success(self, eligibility_service):

        member_found = EligibilityMemberFactory.create()
        eligibility_service.e9y.get_by_healthplan_verification.side_effect = [
            member_found
        ]

        # When
        res = eligibility_service.verify_member_healthplan(
            params=TestVerifyMemberHealthplan.params
        )
        eligibility_service.e9y.get_by_healthplan_verification.assert_called_with(
            subscriber_id=TestVerifyMemberHealthplan.unique_corp_id,
            first_name=TestVerifyMemberHealthplan.first_name,
            last_name=TestVerifyMemberHealthplan.last_name,
            date_of_birth=TestVerifyMemberHealthplan.date_of_birth,
            dependent_date_of_birth=TestVerifyMemberHealthplan.dependent_date_of_birth,
            employee_first_name=TestVerifyMemberHealthplan.employee_first_name,
            employee_last_name=TestVerifyMemberHealthplan.employee_last_name,
            user_id=TestVerifyMemberHealthplan.user_id,
            metadata=mock.ANY,
        )
        assert res == [member_found]

    def test_healthplan_member_not_found(self, eligibility_service):

        eligibility_service.e9y.get_by_healthplan_verification.side_effect = [None]

        # When
        res = eligibility_service.verify_member_healthplan(
            params=TestVerifyMemberHealthplan.params
        )
        eligibility_service.e9y.get_by_healthplan_verification.assert_called_with(
            subscriber_id=TestVerifyMemberHealthplan.unique_corp_id,
            first_name=TestVerifyMemberHealthplan.first_name,
            last_name=TestVerifyMemberHealthplan.last_name,
            date_of_birth=TestVerifyMemberHealthplan.date_of_birth,
            dependent_date_of_birth=TestVerifyMemberHealthplan.dependent_date_of_birth,
            employee_first_name=TestVerifyMemberHealthplan.employee_first_name,
            employee_last_name=TestVerifyMemberHealthplan.employee_last_name,
            user_id=TestVerifyMemberHealthplan.user_id,
            metadata=mock.ANY,
        )
        assert res == []

    def test_healthplan_no_grpc_call_when_param_missing(self, eligibility_service):
        params = verification_utils.VerificationParams(
            user_id=TestVerifyMemberBasic.user_id,
        )
        # When
        with pytest.raises(service.EnterpriseVerificationQueryError):
            eligibility_service.verify_member_healthplan(params=params)
        eligibility_service.e9y.get_by_healthplan_verification.assert_not_called


class TestVerifyMemberOvereligibility:
    @pytest.fixture(params=["no-dependent-dob", "dependent-dob"])
    def success_case(self, request, faker):
        params = factories.OvereligibilityVerificationParams.create()
        expected_call = mock.call(**params, metadata=mock.ANY)
        if request.param == "no-dependent-dob":
            return expected_call, params
        params["dependent_date_of_birth"] = params.pop("date_of_birth")
        params["date_of_birth"] = faker.date_of_birth()
        return expected_call, params

    def test_verification_succeeds(self, eligibility_service, success_case):
        # Given
        expected_call, params = success_case
        # When
        eligibility_service.verify_member_overeligibility(**params)
        # Then
        assert (
            eligibility_service.e9y.get_by_overeligibility_verification.call_args
            == expected_call
        )

    def test_verification_succeeds_dep_dob_fallthrough(
        self, eligibility_service, faker
    ):
        # Given
        params = factories.OvereligibilityVerificationParams.create()
        date_of_birth = params.pop("date_of_birth")
        dependent_date_of_birth = faker.date_of_birth()
        expected_calls = [
            mock.call(
                date_of_birth=dependent_date_of_birth,
                **params,
                metadata=mock.ANY,
            ),
            mock.call(
                date_of_birth=date_of_birth,
                **params,
                metadata=mock.ANY,
            ),
        ]
        eligibility_service.e9y.get_by_overeligibility_verification.side_effect = iter(
            [None, mock.MagicMock()]
        )
        # When
        eligibility_service.verify_member_overeligibility(
            date_of_birth=date_of_birth,
            dependent_date_of_birth=dependent_date_of_birth,
            **params,
        )
        # Then
        assert (
            eligibility_service.e9y.get_by_overeligibility_verification.call_args_list
            == expected_calls
        )


class TestGetEnterpriseAssociation:
    def test_member_id_override(self, eligibility_service):
        """Test the manual enrollment flow via admin, where an eligibility_member_id is provided"""
        # Given
        verification_type = "lookup"
        user_id = 1
        eligibility_member_id = 1
        # member_versioned record is returned
        eligibility_service.e9y.get_by_member_id.return_value = mock.MagicMock()
        # existing verification doesn't exist
        eligibility_service.e9y.get_verification_for_user.return_value = None
        # verification returned upon create
        eligibility_service.e9y.create_verification_for_user.return_value = (
            mock.MagicMock()
        )

        # When
        eligibility_service.get_enterprise_association(
            user_id=user_id,
            verification_type=verification_type,
            eligibility_member_id=eligibility_member_id,
        )

        # Then
        assert eligibility_service.e9y.create_verification_for_user.called

    def test_identities_override(self, eligibility_service):
        # Given
        verification_type = "lookup"
        user_id = 1
        expected_call = mock.call(user_id=user_id)
        eligibility_service.sso.fetch_identities.return_value = [mock.MagicMock()]
        # When
        eligibility_service.get_enterprise_association(
            user_id=user_id, verification_type=verification_type
        )
        # Then
        assert eligibility_service.employees.get_by_user_id.call_args == expected_call

    def test_lookup_succeeds(self, eligibility_service):
        # Given
        verification_type = "lookup"
        user_id = 1
        expected_call = mock.call(user_id=user_id)
        eligibility_service.employees.get_by_user_id.return_value = mock.MagicMock()
        # The found organization has a restricted eligibility-type,
        #   which we should ignore.
        settings = (
            eligibility_service.orgs.get_eligibility_settings_by_email.return_value
        )
        settings.eligibility_type = "FILELESS"
        # When
        eligibility_service.get_enterprise_association(
            user_id=user_id, verification_type=verification_type
        )
        # Then
        assert eligibility_service.employees.get_by_user_id.call_args == expected_call

    def test_lookup_fails(self, eligibility_service):
        # Given
        verification_type = "lookup"
        user_id = 1
        eligibility_service.e9y.get_verification_for_user.return_value = None
        # When/Then
        with pytest.raises(service.EnterpriseVerificationFailedError):
            eligibility_service.get_enterprise_association(
                user_id=user_id, verification_type=verification_type
            )

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_standard_succeeds(self, eligibility_service):
        # Given
        verification_type = "standard"
        user_id = 1
        params = factories.StandardVerificationParams.create()
        eligibility_service.e9y.get_by_standard_verification.return_value = (
            mock.MagicMock()
        )
        # When
        eligibility_service.get_enterprise_association(
            user_id=user_id,
            verification_type=verification_type,
            **params,
        )
        # Then
        assert eligibility_service.e9y.create_verification_for_user.called

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_standard_fallthrough_succeeds(self, eligibility_service):
        # Given
        verification_type = "standard"
        user_id = 1
        params = factories.StandardVerificationParams.create()
        params.update(factories.AlternateVerificationParams.create())
        eligibility_service.e9y.get_by_standard_verification.return_value = None
        eligibility_service.e9y.get_by_alternate_verification.return_value = (
            mock.MagicMock()
        )
        # When
        eligibility_service.get_enterprise_association(
            user_id=user_id, verification_type=verification_type, **params
        )
        # Then
        assert eligibility_service.e9y.create_verification_for_user.called

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_standard_missing_params(self, eligibility_service):
        # Given
        verification_type = "standard"
        user_id = 1
        params = factories.StandardVerificationParams.create(date_of_birth=None)
        eligibility_service.e9y.get_by_standard_verification.return_value = (
            mock.MagicMock()
        )
        # When/Then
        with pytest.raises(service.EnterpriseVerificationQueryError):
            eligibility_service.get_enterprise_association(
                user_id=user_id, verification_type=verification_type, **params
            )

    def test_standard_fails(self, eligibility_service):
        # Given
        verification_type = "standard"
        user_id = 1
        params = factories.StandardVerificationParams.create()
        params.update(factories.AlternateVerificationParams.create())
        eligibility_service.e9y.get_by_standard_verification.return_value = None
        eligibility_service.e9y.get_by_alternate_verification.return_value = None
        # When/Then
        with pytest.raises(service.EnterpriseVerificationFailedError):
            eligibility_service.get_enterprise_association(
                user_id=user_id, verification_type=verification_type, **params
            )

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_alternate_succeeds(self, eligibility_service):
        # Given
        verification_type = "alternate"
        user_id = 1
        params = factories.AlternateVerificationParams.create()
        eligibility_service.e9y.get_by_alternate_verification.return_value = (
            mock.MagicMock()
        )
        # When
        eligibility_service.get_enterprise_association(
            user_id=user_id, verification_type=verification_type, **params
        )
        # Then
        assert eligibility_service.e9y.create_verification_for_user.called

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_alternate_fallthrough_succeeds(self, eligibility_service):
        # Given
        verification_type = "alternate"
        user_id = 1
        params = factories.AlternateVerificationParams.create()
        params.update(factories.StandardVerificationParams.create())
        eligibility_service.e9y.get_by_alternate_verification.return_value = None
        eligibility_service.e9y.get_by_standard_verification.return_value = (
            mock.MagicMock()
        )
        # When
        eligibility_service.get_enterprise_association(
            user_id=user_id, verification_type=verification_type, **params
        )
        # Then
        assert eligibility_service.e9y.create_verification_for_user.called

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_alternate_missing_params(self, eligibility_service):
        # Given
        verification_type = "alternate"
        user_id = 1
        params = factories.AlternateVerificationParams.create(date_of_birth=None)
        eligibility_service.e9y.get_by_alternate_verification.return_value = (
            mock.MagicMock()
        )
        # When/Then
        with pytest.raises(service.EnterpriseVerificationQueryError):
            eligibility_service.get_enterprise_association(
                user_id=user_id, verification_type=verification_type, **params
            )

    def test_alternate_fails(self, eligibility_service):
        # Given
        verification_type = "alternate"
        user_id = 1
        params = factories.AlternateVerificationParams.create()
        params.update(factories.StandardVerificationParams.create())
        eligibility_service.e9y.get_by_alternate_verification.return_value = None
        eligibility_service.e9y.get_by_standard_verification.return_value = None
        # When/Then
        with pytest.raises(service.EnterpriseVerificationFailedError):
            eligibility_service.get_enterprise_association(
                user_id=user_id, verification_type=verification_type, **params
            )

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_multistep_succeeds(self, eligibility_service):
        # Given
        verification_type = "multistep"
        user_id = 1
        params = factories.AlternateVerificationParams.create()
        eligibility_service.e9y.get_by_alternate_verification.return_value = (
            mock.MagicMock()
        )
        # When
        eligibility_service.get_enterprise_association(
            user_id=user_id, verification_type=verification_type, **params
        )
        # Then
        assert eligibility_service.e9y.create_verification_for_user.called

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_multistep_work_state_fallthrough_succeeds(self, eligibility_service):
        # Given
        verification_type = "multistep"
        user_id = 1
        params = factories.AlternateVerificationParams.create()
        params.update(factories.StandardVerificationParams.create())
        eligibility_service.e9y.get_by_alternate_verification.side_effect = iter(
            [None, mock.MagicMock()]
        )
        eligibility_service.e9y.get_by_standard_verification.return_value = (
            mock.MagicMock()
        )
        # When
        eligibility_service.get_enterprise_association(
            user_id=user_id, verification_type=verification_type, **params
        )
        # Then
        assert eligibility_service.e9y.create_verification_for_user.called

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_multistep_standard_fallthrough_succeeds(self, eligibility_service):
        # Given
        verification_type = "multistep"
        user_id = 1
        params = factories.AlternateVerificationParams.create()
        params.update(factories.StandardVerificationParams.create())
        eligibility_service.e9y.get_by_alternate_verification.side_effect = iter(
            [None, None]
        )
        eligibility_service.e9y.get_by_standard_verification.return_value = (
            mock.MagicMock()
        )
        # When
        eligibility_service.get_enterprise_association(
            user_id=user_id, verification_type=verification_type, **params
        )
        # Then
        assert eligibility_service.e9y.create_verification_for_user.called

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_multistep_missing_params(self, eligibility_service):
        # Given
        verification_type = "multistep"
        user_id = 1
        params = factories.AlternateVerificationParams.create()
        params.update(factories.StandardVerificationParams.create())
        params["date_of_birth"] = None
        eligibility_service.e9y.get_by_alternate_verification.return_value = (
            mock.MagicMock()
        )
        # When/Then
        with pytest.raises(service.EnterpriseVerificationQueryError):
            eligibility_service.get_enterprise_association(
                user_id=user_id, verification_type=verification_type, **params
            )

    def test_multistep_fails(self, eligibility_service):
        # Given
        verification_type = "multistep"
        user_id = 1
        params = factories.AlternateVerificationParams.create()
        params.update(factories.StandardVerificationParams.create())
        eligibility_service.e9y.get_by_alternate_verification.return_value = None
        eligibility_service.e9y.get_by_standard_verification.return_value = None
        # When/Then
        with pytest.raises(service.EnterpriseVerificationFailedError):
            eligibility_service.get_enterprise_association(
                user_id=user_id, verification_type=verification_type, **params
            )

    def test_client_specific_succeeds(self, eligibility_service):
        # Given
        verification_type = "client_specific"
        user_id = 1
        params = factories.ClientSpecificParams.create()
        eligibility_service.e9y.get_by_client_specific.return_value = mock.MagicMock()
        # When
        eligibility_service.get_enterprise_association(
            user_id=user_id, verification_type=verification_type, **params
        )
        # Then
        assert eligibility_service.e9y.create_verification_for_user.called

    def test_client_specific_missing_params(self, eligibility_service):
        # Given
        verification_type = "client_specific"
        user_id = 1
        params = factories.ClientSpecificParams.create(
            unique_corp_id=None,
        )
        # When/Then
        with pytest.raises(service.EnterpriseVerificationQueryError):
            eligibility_service.get_enterprise_association(
                user_id=user_id, verification_type=verification_type, **params
            )

    def test_client_specific_fails(self, eligibility_service):
        # Given
        verification_type = "client_specific"
        user_id = 1
        params = factories.ClientSpecificParams.create()
        eligibility_service.e9y.get_by_client_specific.return_value = None
        # When/Then
        with pytest.raises(service.EnterpriseVerificationFailedError):
            eligibility_service.get_enterprise_association(
                user_id=user_id, verification_type=verification_type, **params
            )


class TestGetEnterpriseAssociations:
    def test_member_id_override(self, eligibility_service):
        """Test the manual enrollment flow via admin, where an eligibility_member_id is provided"""
        # Given
        verification_type = "lookup"
        user_id = 1
        eligibility_member_id = 1
        # member_versioned record is returned
        eligibility_service.e9y.get_by_member_id.return_value = mock.MagicMock()
        # existing verification doesn't exist
        eligibility_service.e9y.get_all_verifications_for_user.return_value = []
        # verification returned upon create
        eligibility_service.e9y.create_multiple_verifications_for_user.return_value = (
            mock.MagicMock()
        )

        # When
        eligibility_service.get_enterprise_associations(
            user_id=user_id,
            verification_type=verification_type,
            eligibility_member_id=eligibility_member_id,
        )

        # Then
        assert eligibility_service.e9y.create_multiple_verifications_for_user.called

    def test_identities_override(self, eligibility_service):
        # Given
        verification_type = "lookup"
        user_id = 1
        expected_call = mock.call(user_id=user_id)
        eligibility_service.sso.fetch_identities.return_value = [mock.MagicMock()]
        # When
        eligibility_service.get_enterprise_associations(
            user_id=user_id, verification_type=verification_type
        )
        # Then
        assert eligibility_service.employees.get_by_user_id.call_args == expected_call

    def test_lookup_succeeds(self, eligibility_service):
        # Given
        verification_type = "lookup"
        user_id = 1
        expected_call = mock.call(user_id=user_id)
        eligibility_service.employees.get_by_user_id.return_value = mock.MagicMock()
        # The found organization has a restricted eligibility-type,
        #   which we should ignore.
        settings = (
            eligibility_service.orgs.get_eligibility_settings_by_email.return_value
        )
        settings.eligibility_type = "FILELESS"
        # When
        eligibility_service.get_enterprise_associations(
            user_id=user_id, verification_type=verification_type
        )
        # Then
        assert eligibility_service.employees.get_by_user_id.call_args == expected_call

    def test_lookup_fails(self, eligibility_service):
        # Given
        verification_type = "lookup"
        user_id = 1
        eligibility_service.e9y.get_all_verifications_for_user.return_value = None
        # When/Then
        with pytest.raises(service.EnterpriseVerificationFailedError):
            eligibility_service.get_enterprise_associations(
                user_id=user_id, verification_type=verification_type
            )

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_standard_succeeds(self, eligibility_service):
        # Given
        verification_type = "standard"
        user_id = 1
        params = factories.StandardVerificationParams.create()
        eligibility_service.e9y.get_by_standard_verification.return_value = (
            mock.MagicMock()
        )
        # When
        eligibility_service.get_enterprise_associations(
            user_id=user_id,
            verification_type=verification_type,
            **params,
        )
        # Then
        assert eligibility_service.e9y.create_multiple_verifications_for_user.called

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_standard_fallthrough_succeeds(self, eligibility_service):
        # Given
        verification_type = "standard"
        user_id = 1
        params = factories.StandardVerificationParams.create()
        params.update(factories.AlternateVerificationParams.create())
        eligibility_service.e9y.get_by_standard_verification.return_value = None
        eligibility_service.e9y.get_by_alternate_verification.return_value = (
            mock.MagicMock()
        )
        # When
        eligibility_service.get_enterprise_associations(
            user_id=user_id, verification_type=verification_type, **params
        )
        # Then
        assert eligibility_service.e9y.create_multiple_verifications_for_user.called

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_standard_missing_params(self, eligibility_service):
        # Given
        verification_type = "standard"
        user_id = 1
        params = factories.StandardVerificationParams.create(date_of_birth=None)
        eligibility_service.e9y.get_by_standard_verification.return_value = (
            mock.MagicMock()
        )
        # When/Then
        with pytest.raises(service.EnterpriseVerificationQueryError):
            eligibility_service.get_enterprise_associations(
                user_id=user_id, verification_type=verification_type, **params
            )

    def test_standard_fails(self, eligibility_service):
        # Given
        verification_type = "standard"
        user_id = 1
        params = factories.StandardVerificationParams.create()
        params.update(factories.AlternateVerificationParams.create())
        eligibility_service.e9y.get_by_standard_verification.return_value = None
        eligibility_service.e9y.get_by_alternate_verification.return_value = None
        # When/Then
        with pytest.raises(service.EnterpriseVerificationFailedError):
            eligibility_service.get_enterprise_associations(
                user_id=user_id, verification_type=verification_type, **params
            )

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_alternate_succeeds(self, eligibility_service):
        # Given
        verification_type = "alternate"
        user_id = 1
        params = factories.AlternateVerificationParams.create()
        eligibility_service.e9y.get_by_alternate_verification.return_value = (
            mock.MagicMock()
        )
        # When
        eligibility_service.get_enterprise_associations(
            user_id=user_id, verification_type=verification_type, **params
        )
        # Then
        assert eligibility_service.e9y.create_multiple_verifications_for_user.called

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_alternate_no_verification_create_if_already_exist(
        self, eligibility_service
    ):
        # Given
        verification_type = "alternate"
        user_id = 1
        params = factories.AlternateVerificationParams.create()
        org_id = 101
        existing_verifications = [
            factories.VerificationFactory.create(
                organization_id=org_id,
                user_id=user_id,
            )
        ]
        member_found = factories.EligibilityMemberFactory.create(
            organization_id=org_id,
        )

        eligibility_service.e9y.get_by_alternate_verification.return_value = (
            member_found
        )

        eligibility_service.e9y.get_all_verifications_for_user.return_value = (
            existing_verifications
        )
        # When
        with patch(
            "eligibility.service.EnterpriseVerificationService.validate_verification_type_for_multiple_member_records",
            return_value=[member_found],
        ):
            eligibility_service.get_enterprise_associations(
                user_id=user_id, verification_type=verification_type, **params
            )
        # Then
        assert not eligibility_service.e9y.create_multiple_verifications_for_user.called

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_alternate_fallthrough_succeeds(self, eligibility_service):
        # Given
        verification_type = "alternate"
        user_id = 1
        params = factories.AlternateVerificationParams.create()
        params.update(factories.StandardVerificationParams.create())
        eligibility_service.e9y.get_by_alternate_verification.return_value = None
        eligibility_service.e9y.get_by_standard_verification.return_value = (
            mock.MagicMock()
        )
        # When
        eligibility_service.get_enterprise_associations(
            user_id=user_id, verification_type=verification_type, **params
        )
        # Then
        assert eligibility_service.e9y.create_multiple_verifications_for_user.called

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_alternate_missing_params(self, eligibility_service):
        # Given
        verification_type = "alternate"
        user_id = 1
        params = factories.AlternateVerificationParams.create(date_of_birth=None)
        eligibility_service.e9y.get_by_alternate_verification.return_value = (
            mock.MagicMock()
        )
        # When/Then
        with pytest.raises(service.EnterpriseVerificationQueryError):
            eligibility_service.get_enterprise_associations(
                user_id=user_id, verification_type=verification_type, **params
            )

    def test_alternate_fails(self, eligibility_service):
        # Given
        verification_type = "alternate"
        user_id = 1
        params = factories.AlternateVerificationParams.create()
        params.update(factories.StandardVerificationParams.create())
        eligibility_service.e9y.get_by_alternate_verification.return_value = None
        eligibility_service.e9y.get_by_standard_verification.return_value = None
        # When/Then
        with pytest.raises(service.EnterpriseVerificationFailedError):
            eligibility_service.get_enterprise_associations(
                user_id=user_id, verification_type=verification_type, **params
            )

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_multistep_succeeds(self, eligibility_service):
        # Given
        verification_type = "multistep"
        user_id = 1
        params = factories.AlternateVerificationParams.create()
        eligibility_service.e9y.get_by_alternate_verification.return_value = (
            mock.MagicMock()
        )
        # When
        eligibility_service.get_enterprise_associations(
            user_id=user_id, verification_type=verification_type, **params
        )
        # Then
        assert eligibility_service.e9y.create_multiple_verifications_for_user.called

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_multistep_work_state_fallthrough_succeeds(self, eligibility_service):
        # Given
        verification_type = "multistep"
        user_id = 1
        params = factories.AlternateVerificationParams.create()
        params.update(factories.StandardVerificationParams.create())
        eligibility_service.e9y.get_by_alternate_verification.side_effect = iter(
            [None, mock.MagicMock()]
        )
        eligibility_service.e9y.get_by_standard_verification.return_value = (
            mock.MagicMock()
        )
        # When
        eligibility_service.get_enterprise_associations(
            user_id=user_id, verification_type=verification_type, **params
        )
        # Then
        assert eligibility_service.e9y.create_multiple_verifications_for_user.called

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_multistep_standard_fallthrough_succeeds(self, eligibility_service):
        # Given
        verification_type = "multistep"
        user_id = 1
        params = factories.AlternateVerificationParams.create()
        params.update(factories.StandardVerificationParams.create())
        eligibility_service.e9y.get_by_alternate_verification.side_effect = iter(
            [None, None]
        )
        eligibility_service.e9y.get_by_standard_verification.return_value = (
            mock.MagicMock()
        )
        # When
        eligibility_service.get_enterprise_associations(
            user_id=user_id, verification_type=verification_type, **params
        )
        # Then
        assert eligibility_service.e9y.create_multiple_verifications_for_user.called

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_multistep_missing_params(self, eligibility_service):
        # Given
        verification_type = "multistep"
        user_id = 1
        params = factories.AlternateVerificationParams.create()
        params.update(factories.StandardVerificationParams.create())
        params["date_of_birth"] = None
        eligibility_service.e9y.get_by_alternate_verification.return_value = (
            mock.MagicMock()
        )
        # When/Then
        with pytest.raises(service.EnterpriseVerificationQueryError):
            eligibility_service.get_enterprise_associations(
                user_id=user_id, verification_type=verification_type, **params
            )

    def test_multistep_fails(self, eligibility_service):
        # Given
        verification_type = "multistep"
        user_id = 1
        params = factories.AlternateVerificationParams.create()
        params.update(factories.StandardVerificationParams.create())
        eligibility_service.e9y.get_by_alternate_verification.return_value = None
        eligibility_service.e9y.get_by_standard_verification.return_value = None
        # When/Then
        with pytest.raises(service.EnterpriseVerificationFailedError):
            eligibility_service.get_enterprise_associations(
                user_id=user_id, verification_type=verification_type, **params
            )

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_simplified_verification_flow_invalid_verification_type(
        self,
        eligibility_service,
    ):
        # Given
        verification_type = "alternate"
        verification_type_v2 = "not_found"
        user_id = 1
        params = factories.BasicVerificationParams.create()
        updated_params = {**params, "verification_type_v2": verification_type_v2}
        eligibility_service.e9y.get_by_basic_verification.return_value = []
        # When
        eligibility_service.get_enterprise_associations(
            user_id=user_id, verification_type=verification_type, **updated_params
        )
        # Then
        assert eligibility_service.e9y.create_multiple_verifications_for_user.called

    def test_basic_verification_missing_params(
        self,
        eligibility_service,
    ):
        # Given
        verification_type = "basic"
        verification_type_v2 = "basic"
        user_id = 1
        params = factories.BasicVerificationParams.create()
        updated_params = {
            **params,
            "first_name": "",
            "verification_type_v2": verification_type_v2,
        }
        eligibility_service.e9y.get_by_basic_verification.return_value = []
        # When/Then
        with pytest.raises(service.EnterpriseVerificationQueryError):
            eligibility_service.get_enterprise_associations(
                user_id=user_id, verification_type=verification_type, **updated_params
            )

    def test_basic_verification_succeeds(
        self,
        eligibility_service,
    ):
        # Given
        verification_type = "basic"
        verification_type_v2 = "basic"
        user_id = 1
        params = factories.BasicVerificationParams.create()
        updated_params = {**params, "verification_type_v2": verification_type_v2}
        eligibility_service.e9y.get_by_basic_verification.return_value = [
            mock.MagicMock()
        ]
        # When

        with patch(
            "eligibility.service.EnterpriseVerificationService.validate_verification_type_for_multiple_member_records",
            return_value=[mock.MagicMock()],
        ):
            eligibility_service.get_enterprise_associations(
                user_id=user_id, verification_type=verification_type, **updated_params
            )
        # Then
        assert eligibility_service.e9y.create_multiple_verifications_for_user.called

    def test_basic_verification_fails_due_to_overeligibility(
        self,
        eligibility_service,
    ):
        # Given
        verification_type = "alternate"
        verification_type_v2 = "basic"
        user_id = 1
        params = factories.BasicVerificationParams.create()
        updated_params = {**params, "verification_type_v2": verification_type_v2}
        eligibility_service.e9y.get_by_basic_verification.return_value = [
            mock.MagicMock(),
            mock.MagicMock(),
        ]
        # When

        with patch(
            "eligibility.service.EnterpriseVerificationService.validate_verification_type_for_multiple_member_records",
            return_value=[mock.MagicMock(), mock.MagicMock()],
        ):
            with pytest.raises(service.EnterpriseVerificationFailedError):
                eligibility_service.get_enterprise_associations(
                    user_id=user_id,
                    verification_type=verification_type,
                    **updated_params,
                )

    def test_basic_verification_fails(
        self,
        eligibility_service,
    ):
        # Given
        verification_type = "basic"
        verification_type_v2 = "basic"
        user_id = 1
        params = factories.BasicVerificationParams.create()
        updated_params = {**params, "verification_type_v2": verification_type_v2}
        eligibility_service.e9y.get_by_basic_verification.return_value = []
        # When/Then
        with pytest.raises(service.EnterpriseVerificationFailedError):
            eligibility_service.get_enterprise_associations(
                user_id=user_id, verification_type=verification_type, **updated_params
            )

    def test_employer_verification_with_work_state_success(
        self,
        eligibility_service,
    ):
        # Given
        verification_type = "alternate"
        verification_type_v2 = "employer"
        user_id = 1
        params = factories.EmployerVerificationParams.create()
        updated_params = {
            **params,
            "company_email": "",
            "verification_type_v2": verification_type_v2,
        }
        eligibility_service.e9y.get_by_employer_verification.return_value = (
            mock.MagicMock()
        )
        # When
        eligibility_service.get_enterprise_associations(
            user_id=user_id, verification_type=verification_type, **updated_params
        )

        # Then
        assert eligibility_service.e9y.create_multiple_verifications_for_user.called

    def test_employer_verification_without_work_state_fail(
        self,
        eligibility_service,
    ):
        # Given
        verification_type = "alternate"
        verification_type_v2 = "employer"
        user_id = 1
        params = factories.EmployerVerificationParams.create()
        updated_params = {
            **params,
            "date_of_birth": "",
            "company_email": "",
            "work_state": "",
            "verification_type_v2": verification_type_v2,
        }
        eligibility_service.e9y.get_by_employer_verification.return_value = (
            mock.MagicMock()
        )
        # When/Then
        with pytest.raises(service.EnterpriseVerificationQueryError):
            eligibility_service.get_enterprise_associations(
                user_id=user_id, verification_type=verification_type, **updated_params
            )

    def test_employer_verification_succeeds(
        self,
        eligibility_service,
    ):
        # Given
        verification_type = "employer"
        verification_type_v2 = "employer"
        user_id = 1
        params = factories.EmployerVerificationParams.create()
        updated_params = {**params, "verification_type_v2": verification_type_v2}
        eligibility_service.e9y.get_by_employer_verification.return_value = (
            mock.MagicMock()
        )
        # When
        with patch(
            "eligibility.service.EnterpriseVerificationService.validate_verification_type_for_multiple_member_records",
            return_value=[mock.MagicMock()],
        ):
            eligibility_service.get_enterprise_associations(
                user_id=user_id, verification_type=verification_type, **updated_params
            )
        # Then
        assert eligibility_service.e9y.create_multiple_verifications_for_user.called

    def test_employer_verification_fails(
        self,
        eligibility_service,
    ):
        # Given
        verification_type = "employer"
        verification_type_v2 = "employer"
        user_id = 1
        params = factories.EmployerVerificationParams.create()
        updated_params = {**params, "verification_type_v2": verification_type_v2}
        eligibility_service.e9y.get_by_employer_verification.return_value = []

        # When/Then
        with pytest.raises(service.EnterpriseVerificationFailedError):
            eligibility_service.get_enterprise_associations(
                user_id=user_id, verification_type=verification_type, **updated_params
            )

    def test_healthplan_verification_missing_params(
        self,
        eligibility_service,
    ):
        # Given
        verification_type = "healthplan"
        verification_type_v2 = "healthplan"
        user_id = 1
        params = factories.HealthPlanVerificationParams.create()
        updated_params = {
            **params,
            "unique_corp_id": "",
            "date_of_birth": "",
            "verification_type_v2": verification_type_v2,
        }
        eligibility_service.e9y.get_by_healthplan_verification.return_value = []

        # When/Then
        with pytest.raises(service.EnterpriseVerificationQueryError):
            eligibility_service.get_enterprise_associations(
                user_id=user_id, verification_type=verification_type, **updated_params
            )

    def test_healthplan_verification_succeeds(
        self,
        eligibility_service,
    ):
        # Given
        verification_type = "healthplan"
        verification_type_v2 = "healthplan"
        user_id = 1
        params = factories.HealthPlanVerificationParams.create()
        updated_params = {**params, "verification_type_v2": verification_type_v2}
        eligibility_service.e9y.get_by_healthplan_verification.return_value = (
            mock.MagicMock()
        )
        # When
        with patch(
            "eligibility.service.EnterpriseVerificationService.validate_verification_type_for_multiple_member_records",
            return_value=[mock.MagicMock()],
        ):
            eligibility_service.get_enterprise_associations(
                user_id=user_id, verification_type=verification_type, **updated_params
            )
        # Then
        assert eligibility_service.e9y.create_multiple_verifications_for_user.called

    def test_healthplan_verification_succeeds_with_basic_params(
        self,
        eligibility_service,
    ):
        # Given
        verification_type = "healthplan"
        verification_type_v2 = "healthplan"
        user_id = 1
        params = factories.BasicVerificationParams.create()
        updated_params = {**params, "verification_type_v2": verification_type_v2}
        eligibility_service.e9y.get_by_healthplan_verification.return_value = (
            mock.MagicMock()
        )
        # When
        with patch(
            "eligibility.service.EnterpriseVerificationService.validate_verification_type_for_multiple_member_records",
            return_value=[mock.MagicMock()],
        ):
            eligibility_service.get_enterprise_associations(
                user_id=user_id, verification_type=verification_type, **updated_params
            )
        # Then
        assert eligibility_service.e9y.create_multiple_verifications_for_user.called

    def test_healthplan_verification_fails(
        self,
        eligibility_service,
    ):
        # Given
        verification_type = "healthplan"
        verification_type_v2 = "healthplan"
        user_id = 1
        params = factories.HealthPlanVerificationParams.create()
        updated_params = {**params, "verification_type_v2": verification_type_v2}
        eligibility_service.e9y.get_by_healthplan_verification.return_value = []

        # When/Then
        with pytest.raises(service.EnterpriseVerificationFailedError):
            eligibility_service.get_enterprise_associations(
                user_id=user_id, verification_type=verification_type, **updated_params
            )

    def test_client_specific_succeeds(self, eligibility_service):
        # Given
        verification_type = "client_specific"
        user_id = 1
        params = factories.ClientSpecificParams.create()
        eligibility_service.e9y.get_by_client_specific.return_value = mock.MagicMock()
        # When
        eligibility_service.get_enterprise_associations(
            user_id=user_id, verification_type=verification_type, **params
        )
        # Then
        assert eligibility_service.e9y.create_multiple_verifications_for_user.called

    def test_client_specific_missing_params(self, eligibility_service):
        # Given
        verification_type = "client_specific"
        user_id = 1
        params = factories.ClientSpecificParams.create(
            unique_corp_id=None,
        )
        # When/Then
        with pytest.raises(service.EnterpriseVerificationQueryError):
            eligibility_service.get_enterprise_associations(
                user_id=user_id, verification_type=verification_type, **params
            )

    def test_client_specific_fails(self, eligibility_service):
        # Given
        verification_type = "client_specific"
        user_id = 1
        params = factories.ClientSpecificParams.create()
        eligibility_service.e9y.get_by_client_specific.return_value = None
        # When/Then
        with pytest.raises(service.EnterpriseVerificationFailedError):
            eligibility_service.get_enterprise_associations(
                user_id=user_id, verification_type=verification_type, **params
            )

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_create_verification_succeeds_should_call_create_oe(
        self, eligibility_service, mock_associate_user_id_to_members
    ):
        # Given
        verification_type = "alternate"
        user_id = 1
        params = factories.AlternateVerificationParams.create()
        eligibility_service.e9y.get_by_alternate_verification.return_value = (
            mock.MagicMock()
        )
        # When
        eligibility_service.get_enterprise_associations(
            user_id=user_id, verification_type=verification_type, **params
        )
        # Then
        # Check that associate_user_id_to_members was called
        assert (
            eligibility_service.associate_user_id_to_members.called
        ), "associate_user_id_to_members should have been called"

        # check if it was called with the correct arguments
        eligibility_service.associate_user_id_to_members.assert_called_once_with(
            user_id=user_id,
            members=mock.ANY,
            verification_type=verification_type,
        )

    def test_create_verification_failed_should_not_call_create_oe(
        self,
        eligibility_service,
        mock_associate_user_id_to_members,
        multiple_eligibility_member_records_for_user,
    ):
        # Given
        verification_type = "alternate"
        user_id = 1
        params = factories.AlternateVerificationParams.create()

        # Mock `generate_multiple_verifications_for_user` to raise `EnterpriseVerificationFailedError`
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.generate_multiple_verifications_for_user",
            side_effect=service.EnterpriseVerificationFailedError(
                message="error creating multiple verifications",
                verification_type=verification_type,
            ),
        ):
            # When/Then: Ensure that the method raises `EnterpriseVerificationFailedError`
            with pytest.raises(service.EnterpriseVerificationFailedError):
                eligibility_service.generate_multiple_verifications_for_user(
                    user_id=user_id,
                    verification_type=verification_type,
                    date_of_birth=params["date_of_birth"],
                    members=multiple_eligibility_member_records_for_user,
                )

        # Ensure that `associate_user_id_to_members` was NOT called
        mock_associate_user_id_to_members.assert_not_called()

    @pytest.mark.parametrize("mock_get_multiple_orgs_for_user", [1, 3], indirect=True)
    def test_all_verifications_match_associations(
        self, eligibility_service, mock_get_multiple_orgs_for_user
    ):
        # Given
        user_id = 1
        verifications = []
        associations = []
        for org in mock_get_multiple_orgs_for_user:
            verification = factories.VerificationFactory.create(
                organization_id=org.id,
                user_id=user_id,
            )
            verifications.append(verification)
            association = OrganizationEmployeeFactory.create(organization=org)
            associations.append(association)

        # When
        result = eligibility_service.match_verifications_to_associations(
            verifications, associations
        )

        # Then
        # All verifications should have matching associations
        expected_result = [
            (verification, association)
            for verification, association in zip(verifications, associations)
        ]

        assert result == expected_result

    @pytest.mark.parametrize("mock_get_multiple_orgs_for_user", [1, 3], indirect=True)
    def test_empty_verifications_and_associations(
        self, eligibility_service, mock_get_multiple_orgs_for_user
    ):
        # Given
        # empty lists for verifications and associations
        verifications: List[EligibilityVerification] = []
        associations: List[OrganizationEmployee] = []

        result = eligibility_service.match_verifications_to_associations(
            verifications, associations
        )

        # Then
        # result should be an empty list
        assert result == []

    @pytest.mark.parametrize("mock_get_multiple_orgs_for_user", [1, 3], indirect=True)
    def test_no_associations(
        self, eligibility_service, mock_get_multiple_orgs_for_user
    ):
        # Given
        user_id = 1
        verifications = []
        # No associations
        associations = []
        for org in mock_get_multiple_orgs_for_user:
            verification = factories.VerificationFactory.create(
                organization_id=org.id,
                user_id=user_id,
            )
            verifications.append(verification)

        # When
        result = eligibility_service.match_verifications_to_associations(
            verifications, associations
        )

        # Then
        expected_result = [(verification, None) for verification in verifications]
        assert result == expected_result

    @pytest.mark.parametrize("mock_get_multiple_orgs_for_user", [1, 3], indirect=True)
    def test_no_verifications_match_associations(
        self, eligibility_service, mock_get_multiple_orgs_for_user
    ):
        # Given
        user_id = 1
        verifications = []
        associations = []

        for org in mock_get_multiple_orgs_for_user:
            # no verifications match associations
            verification = factories.VerificationFactory.create(
                organization_id=(org.id + 100),
                user_id=user_id,
            )
            verifications.append(verification)
            association = OrganizationEmployeeFactory.create(organization=org)
            associations.append(association)

        # When
        result = eligibility_service.match_verifications_to_associations(
            verifications, associations
        )

        # Then
        # None of the verifications should match, so they should all pair with None
        # Additionally, all associations should be included with None for verification
        expected_result = [(verification, None) for verification in verifications]
        expected_result += [(None, association) for association in associations]

        assert result == expected_result


class TestGetFilelessEnterpriseAssociation:
    def test_found_existing_association_by_user_id(self, eligibility_service):
        # Given
        org: Organization = OrganizationFactory.create()
        params = factories.FilelessInviteVerificationParams.create()
        oe: OrganizationEmployee = OrganizationEmployeeFactory.create(organization=org)
        eligibility_service.employees.get_by_user_id.return_value = [oe]
        settings = (
            eligibility_service.orgs.get_eligibility_settings_by_email.return_value
        )
        settings.eligibility_type = "FILELESS"
        settings.organization_id = org.id
        # When
        association = eligibility_service.get_fileless_enterprise_association(**params)
        # Then
        assert association is not None
        assert not eligibility_service.employees.get_by_org_id_email_dob.called

    def test_found_existing_association_by_pii(
        self, eligibility_service, patch_report_last_eligible_through_organization
    ):
        # Given
        params = factories.FilelessInviteVerificationParams.create()
        eligibility_service.employees.get_by_user_id.return_value = []
        eligibility_service.employees.get_existing_claims.return_value = []
        # When
        eligibility_service.get_fileless_enterprise_association(**params)
        # Then
        assert eligibility_service.employees.get_existing_claims.called
        assert not eligibility_service.employees.create.called
        assert not patch_report_last_eligible_through_organization.delay.called
        assert eligibility_service.employees.associate_to_user_id.called

    def test_no_existing_association(
        self, eligibility_service, patch_report_last_eligible_through_organization
    ):
        # Given
        params = factories.FilelessInviteVerificationParams.create()
        eligibility_service.employees.get_by_user_id.return_value = []
        eligibility_service.employees.get_by_org_id_email_dob.return_value = None
        # When
        eligibility_service.get_fileless_enterprise_association(**params)
        # Then
        assert not eligibility_service.employees.get_existing_claims.called
        assert eligibility_service.employees.create.called
        assert patch_report_last_eligible_through_organization.delay.called
        assert eligibility_service.employees.associate_to_user_id.called

    def test_no_existing_association_oe_conflict(
        self, eligibility_service, patch_report_last_eligible_through_organization
    ):
        # Given
        params = factories.FilelessInviteVerificationParams.create()
        eligibility_service.employees.get_by_user_id.return_value = []
        eligibility_service.employees.get_by_org_id_email_dob.return_value = None
        eligibility_service.employees.create.side_effect = (
            sqlalchemy.exc.IntegrityError("mock-sql", [], None)
        )
        # When
        with pytest.raises(EnterpriseVerificationFilelessError):
            eligibility_service.get_fileless_enterprise_association(**params)
        # Then
        assert not eligibility_service.employees.get_existing_claims.called
        assert eligibility_service.employees.create.called
        patch_report_last_eligible_through_organization.delay.assert_not_called()
        eligibility_service.employees.associate_to_user_id.assert_not_called()

    def test_org_is_not_configured(self, eligibility_service):
        # Given
        params = factories.FilelessInviteVerificationParams.create()
        eligibility_service.employees.get_by_user_id.return_value = []
        eligibility_service.orgs.get_eligibility_settings_by_email.return_value = None
        # When/Then
        with pytest.raises(service.EnterpriseVerificationQueryError):
            eligibility_service.get_fileless_enterprise_association(**params)


class TestCreateFilelessVerification:
    @staticmethod
    def test_create_fileless_verification_existing_verification_same_org(
        eligibility_service,
    ):
        # Given
        user_id = 1
        org_id = 1
        expected_verification = factories.VerificationFactory.create(
            organization_id=org_id, user_id=user_id
        )
        org_settings = factories.EnterpriseEligibilitySettingsFactory.create(
            organization_id=org_id
        )
        eligibility_service.e9y.get_all_verifications_for_user = mock.MagicMock(
            return_value=[expected_verification]
        )
        eligibility_service.orgs.get_eligibility_settings_by_email = mock.MagicMock(
            return_value=org_settings
        )

        # When
        verification = eligibility_service.create_fileless_verification(
            user_id=user_id,
            first_name="daffy",
            last_name="duck",
            date_of_birth=datetime.date(year=2020, month=5, day=12),
            company_email="daffy@fileless.com",
            is_dependent=False,
        )

        # Then
        assert verification == expected_verification

    @staticmethod
    def test_create_fileless_verification_existing_verification_diff_org(
        eligibility_service,
    ):
        # Given
        user_id = 1
        target_org_id = 1
        existing_org_id = 2
        verification = factories.VerificationFactory.create(
            organization_id=existing_org_id, user_id=user_id
        )
        org_settings = factories.EnterpriseEligibilitySettingsFactory.create(
            organization_id=target_org_id
        )
        eligibility_service.e9y.get_verification_for_user = mock.MagicMock(
            return_value=verification
        )
        eligibility_service.orgs.get_eligibility_settings_by_email = mock.MagicMock(
            return_value=org_settings
        )

        # When
        with mock.patch.object(
            EnterpriseVerificationService, "generate_multiple_verifications_for_user"
        ) as mock_generate_verification_list:
            eligibility_service.create_fileless_verification(
                user_id=user_id,
                first_name="daffy",
                last_name="duck",
                date_of_birth=datetime.date(year=2020, month=5, day=12),
                company_email="daffy@fileless.com",
                is_dependent=False,
            )

        # Then
        mock_generate_verification_list.assert_called()

    @staticmethod
    def test_create_fileless_verification_no_existing_verification(eligibility_service):
        # Given
        user_id = 1
        org_id = 1
        org_settings = factories.EnterpriseEligibilitySettingsFactory.create(
            organization_id=org_id
        )
        expected_verification = factories.VerificationFactory.create(
            organization_id=org_id, user_id=user_id
        )
        eligibility_service.e9y.get_verification_for_user = mock.MagicMock(
            return_value=None
        )
        eligibility_service.orgs.get_eligibility_settings_by_email = mock.MagicMock(
            return_value=org_settings
        )

        # When
        with mock.patch.object(
            EnterpriseVerificationService, "generate_multiple_verifications_for_user"
        ) as mock_generate_verification_list:
            mock_generate_verification_list.return_value = [expected_verification]
            verification = eligibility_service.create_fileless_verification(
                user_id=user_id,
                first_name="daffy",
                last_name="duck",
                date_of_birth=datetime.date(year=2020, month=5, day=12),
                company_email="daffy@fileless.com",
                is_dependent=False,
            )

        # Then
        assert verification == expected_verification


class TestRunVerificationForUser:
    def test_standard_flow_calls_overeligibility(
        self, eligibility_service, mock_overeligibility_enabled
    ):
        # Given
        params = factories.OvereligibilityVerificationParams.create()
        updated_params = {**params, "verification_type": "standard", "user_id": 1234}
        mock_overeligibility_enabled(True)
        eligibility_service.e9y.get_by_standard_verification.side_effect = iter([None])
        eligibility_service.e9y.get_by_alternate_verification.side_effect = iter([None])

        expected_number_overeligibility_calls = 1

        # When
        eligibility_service.run_verification_for_user(**updated_params)

        # Then
        assert (
            len(
                eligibility_service.e9y.get_by_overeligibility_verification.call_args_list
            )
            == expected_number_overeligibility_calls
        )

    def test_alternate_flow_calls_overeligibility(
        self, eligibility_service, mock_overeligibility_enabled
    ):
        # Given
        params = factories.OvereligibilityVerificationParams.create()
        updated_params = {**params, "verification_type": "alternate", "user_id": 1234}
        mock_overeligibility_enabled(True)
        expected_number_overeligibility_calls = 1
        eligibility_service.e9y.get_by_standard_verification.side_effect = iter([None])
        eligibility_service.e9y.get_by_alternate_verification.side_effect = iter([None])

        # When
        eligibility_service.run_verification_for_user(**updated_params)

        # Then
        assert (
            len(
                eligibility_service.e9y.get_by_overeligibility_verification.call_args_list
            )
            == expected_number_overeligibility_calls
        )

    def test_multistep_flow_calls_overeligibility(
        self, eligibility_service, mock_overeligibility_enabled
    ):
        # Given
        params = factories.OvereligibilityVerificationParams.create()
        updated_params = {**params, "verification_type": "multistep", "user_id": 1234}
        mock_overeligibility_enabled(True)
        expected_number_overeligibility_calls = 1
        eligibility_service.e9y.get_by_standard_verification.side_effect = iter([None])
        eligibility_service.e9y.get_by_alternate_verification.side_effect = iter([None])

        # When
        eligibility_service.run_verification_for_user(**updated_params)

        # Then
        assert (
            len(
                eligibility_service.e9y.get_by_overeligibility_verification.call_args_list
            )
            == expected_number_overeligibility_calls
        )

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_standard_flow_calls_no_dob_verification(
        self,
        eligibility_service,
        mock_no_dob_verification_enabled,
    ):
        mock_no_dob_verification_enabled(True)
        params = factories.NoDOBVerificationParams.create()
        updated_params = {**params, "verification_type": "standard", "user_id": 1234}
        eligibility_service.e9y.get_by_standard_verification.side_effect = iter([None])
        eligibility_service.e9y.get_by_no_dob_verification.side_effect = iter(
            [mock.MagicMock()]
        )
        expected_num_no_dob_calls = 1
        # When
        eligibility_service.run_verification_for_user(**updated_params)
        # Then
        assert (
            len(eligibility_service.e9y.get_by_no_dob_verification.call_args_list)
            == expected_num_no_dob_calls
        )

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_alternate_flow_calls_no_dob_verification(
        self,
        eligibility_service,
        mock_no_dob_verification_enabled,
    ):
        mock_no_dob_verification_enabled(True)
        params = factories.NoDOBVerificationParams.create()
        updated_params = {**params, "verification_type": "alternate", "user_id": 1234}
        eligibility_service.e9y.get_by_alternate_verification.side_effect = iter([None])
        eligibility_service.e9y.get_by_no_dob_verification.side_effect = iter(
            [mock.MagicMock()]
        )
        expected_num_no_dob_calls = 1
        # When
        eligibility_service.run_verification_for_user(**updated_params)
        # Then
        assert (
            len(eligibility_service.e9y.get_by_no_dob_verification.call_args_list)
            == expected_num_no_dob_calls
        )

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_multistep_flow_calls_no_dob_verification(
        self,
        eligibility_service,
        mock_no_dob_verification_enabled,
    ):
        mock_no_dob_verification_enabled(True)
        params = factories.NoDOBVerificationParams.create()
        updated_params = {
            **params,
            "verification_type": "multistep",
            "user_id": 1234,
            "date_of_birth": datetime.date(1999, 1, 1),
        }
        eligibility_service.e9y.get_by_standard_verification.side_effect = iter([None])
        eligibility_service.e9y.get_by_alternate_verification.side_effect = iter([None])
        eligibility_service.e9y.get_by_no_dob_verification.side_effect = iter(
            [mock.MagicMock()]
        )
        expected_num_no_dob_calls = 1
        # When
        eligibility_service.run_verification_for_user(**updated_params)
        # Then
        assert (
            len(eligibility_service.e9y.get_by_no_dob_verification.call_args_list)
            == expected_num_no_dob_calls
        )

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_overeligibility_flow_calls_no_dob_verification(
        self,
        eligibility_service,
        mock_overeligibility_enabled,
        mock_no_dob_verification_enabled,
    ):
        mock_overeligibility_enabled(True)
        mock_no_dob_verification_enabled(True)
        params = factories.OvereligibilityVerificationParams.create()
        expected_number_overeligibility_calls = 1
        expected_number_nodob_calls = 1
        eligibility_service.e9y.get_by_standard_verification.side_effect = iter([None])
        eligibility_service.e9y.get_by_alternate_verification.side_effect = iter([None])
        eligibility_service.e9y.get_by_overeligibility_verification.side_effect = iter(
            [None]
        )

        # When
        eligibility_service.run_verification_for_user(**params)

        # Then
        assert (
            len(
                eligibility_service.e9y.get_by_overeligibility_verification.call_args_list
            )
            == expected_number_overeligibility_calls
        )
        assert (
            len(eligibility_service.e9y.get_by_no_dob_verification.call_args_list)
            == expected_number_nodob_calls
        )

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_overeligibility_flow_success_should_not_call_no_dob_verification(
        self,
        eligibility_service,
        mock_overeligibility_enabled,
        mock_no_dob_verification_enabled,
    ):
        mock_overeligibility_enabled(True)
        mock_no_dob_verification_enabled(True)
        params = factories.OvereligibilityVerificationParams.create()
        expected_number_overeligibility_calls = 1
        expected_num_no_dob_calls = 1
        eligibility_service.e9y.get_by_standard_verification.side_effect = iter([None])
        eligibility_service.e9y.get_by_alternate_verification.side_effect = iter([None])
        eligibility_service.e9y.get_by_overeligibility_verification.side_effect = iter(
            [mock.MagicMock()]
        )

        # When
        eligibility_service.run_verification_for_user(**params)

        # Then
        assert (
            len(
                eligibility_service.e9y.get_by_overeligibility_verification.call_args_list
            )
            == expected_number_overeligibility_calls
        )
        assert (
            len(eligibility_service.e9y.get_by_no_dob_verification.call_args_list)
            == expected_num_no_dob_calls
        )

    def test_run_verification_by_verification_type_v1_warns(
        self,
        eligibility_service,
    ):
        params = factories.VerificationParams.create()

        # When
        with pytest.warns(
            DeprecationWarning,
            match="_run_verification_by_verification_type_v1 is deprecated",
        ):
            eligibility_service._run_verification_by_verification_type_v1(params)


class TestRunVerificationByVerificationType:
    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_verification_simplification_flag_off_calls_v1_flows(
        self,
        eligibility_service,
        mock_run_verification_v1,
        mock_run_verification_v2,
    ):
        # Given
        params = factories.VerificationParams.create()

        # When
        eligibility_service.run_verification_by_verification_type(params)

        # Then
        assert mock_run_verification_v1.call_args.kwargs["params"] == params
        assert mock_run_verification_v2.call_args is None

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_verification_simplification_flag_on_org_enabled_calls_v1_flows(
        self,
        eligibility_service,
        mock_run_verification_v1,
        mock_run_verification_v2,
        org_enabled_for_e9y_v2,
    ):
        # Given
        params = factories.VerificationParams.create()

        # When
        eligibility_service.run_verification_by_verification_type(params)

        # Then
        assert mock_run_verification_v1.call_args.kwargs["params"] == params
        assert mock_run_verification_v2.call_args is None

    def test_verification_simplification_flag_on_org_disabled_calls_v2_flows(
        self,
        eligibility_service,
        mock_run_verification_v1,
        mock_run_verification_v2,
        org_disabled_for_e9y_v2,
    ):
        # Given
        params = factories.VerificationParams.create()

        # When
        eligibility_service.run_verification_by_verification_type(params)

        # Then
        assert mock_run_verification_v2.call_args.kwargs["params"] == params
        assert mock_run_verification_v1.call_args is None

        employer_params = factories.VerificationParams.create(
            verification_type_v2="employer"
        )
        eligibility_service.run_verification_by_verification_type(employer_params)
        assert mock_run_verification_v2.call_args.kwargs["params"] == employer_params
        assert mock_run_verification_v1.call_args is None

        healthplan_params = factories.VerificationParams.create(
            verification_type_v2="healthplan"
        )
        eligibility_service.run_verification_by_verification_type(healthplan_params)
        assert mock_run_verification_v2.call_args.kwargs["params"] == healthplan_params
        assert mock_run_verification_v1.call_args is None

        basic_params = factories.VerificationParams.create(verification_type_v2="basic")
        eligibility_service.run_verification_by_verification_type(basic_params)
        assert mock_run_verification_v2.call_args.kwargs["params"] == basic_params
        assert mock_run_verification_v1.call_args is None

    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_verification_simplification_flag_on_invalid_verification_type_calls_v1_flows(
        self,
        eligibility_service,
        mock_run_verification_v1,
        mock_run_verification_v2,
        org_enabled_for_e9y_v2,
    ):
        # Given
        params = factories.VerificationParams.create(
            verification_type_v2="random",
        )

        # When
        eligibility_service.run_verification_by_verification_type(params)

        # Then
        assert mock_run_verification_v1.call_args.kwargs["params"] == params
        assert mock_run_verification_v2.call_args is None


class TestRunVerificationForUserV2:
    def test_multistep_flow_calls_healthplan(
        self,
        eligibility_service,
    ):
        # Given
        params = factories.HealthPlanVerificationParams.create()
        updated_params = {
            **params,
            "verification_type_v2": "multistep",
            "user_id": 1234,
        }

        expected_number_healthplan_calls = 1

        # When
        eligibility_service.run_verification_for_user(**updated_params)

        # Then
        assert (
            len(eligibility_service.e9y.get_by_healthplan_verification.call_args_list)
            == expected_number_healthplan_calls
        )

    def test_multistep_flow_calls_employer(
        self,
        eligibility_service,
    ):
        # Given
        params = factories.EmployerVerificationParams.create()
        updated_params = {
            **params,
            "verification_type_v2": "multistep",
            "user_id": 1234,
        }
        expected_number_healthplan_calls = 0
        expected_number_employer_calls = 1

        # When
        eligibility_service.run_verification_for_user(**updated_params)

        # Then
        assert (
            len(eligibility_service.e9y.get_by_healthplan_verification.call_args_list)
            == expected_number_healthplan_calls
        )
        assert (
            len(eligibility_service.e9y.get_by_employer_verification.call_args_list)
            == expected_number_employer_calls
        )

    def test_multistep_flow_calls_basic(
        self,
        eligibility_service,
    ):
        # Given
        params = factories.BasicVerificationParams.create()
        updated_params = {
            **params,
            "verification_type_v2": "multistep",
            "user_id": 1234,
        }
        expected_number_healthplan_calls = 0
        expected_number_employer_calls = 0
        expected_number_basic_calls = 1

        # When
        eligibility_service.run_verification_for_user(**updated_params)

        # Then
        assert (
            len(eligibility_service.e9y.get_by_healthplan_verification.call_args_list)
            == expected_number_healthplan_calls
        )
        assert (
            len(eligibility_service.e9y.get_by_employer_verification.call_args_list)
            == expected_number_employer_calls
        )
        assert (
            len(eligibility_service.e9y.get_by_basic_verification.call_args_list)
            == expected_number_basic_calls
        )

    def test_multistep_flow_calls_overeligibility(
        self,
        eligibility_service,
        mock_overeligibility_enabled,
    ):
        mock_overeligibility_enabled(True)
        params = factories.OvereligibilityVerificationParams.create()
        updated_params = {
            **params,
            "verification_type_v2": "multistep",
            "user_id": 1234,
            "date_of_birth": datetime.date(1999, 1, 1),
        }
        eligibility_service.e9y.get_by_healthplan_verification.return_value = None
        eligibility_service.e9y.get_by_employer_verification.return_value = None
        eligibility_service.e9y.get_by_basic_verification.return_value = []
        expected_num_overeligibility_calls = 1
        # When
        eligibility_service.run_verification_for_user(**updated_params)
        # Then
        assert (
            len(
                eligibility_service.e9y.get_by_overeligibility_verification.call_args_list
            )
            == expected_num_overeligibility_calls
        )


class TestRunExternalVerification:
    user_id = 1
    dependent_date_of_birth = datetime.date(1999, 12, 16)
    params = VerificationParams(user_id=user_id)
    member_found = EligibilityMemberFactory.create()
    client_specific = "client_specific"
    sso = "sso"
    alternate = "alternate"

    @staticmethod
    def test_run_client_specific_when_member_found():
        svc = EnterpriseVerificationService()
        with mock.patch(
            "eligibility.utils.verification_utils.VerificationParams.has_necessary_client_specific_params",
            return_value=True,
        ), mock.patch(
            "eligibility.service.EnterpriseVerificationService.verify_member_client_specific",
            return_value=TestRunExternalVerification.member_found,
        ):
            res = svc._run_external_verification(
                verification_type=TestRunExternalVerification.client_specific,
                user_id=TestRunExternalVerification.user_id,
                dependent_date_of_birth=TestRunExternalVerification.dependent_date_of_birth,
                params=TestRunExternalVerification.params,
            )

        assert res == [TestRunExternalVerification.member_found]

    @staticmethod
    def test_run_client_specific_when_member_not_found():
        svc = EnterpriseVerificationService()
        with mock.patch(
            "eligibility.utils.verification_utils.VerificationParams.has_necessary_client_specific_params",
            return_value=True,
        ), mock.patch(
            "eligibility.service.EnterpriseVerificationService.verify_member_client_specific",
            return_value=None,
        ):
            res = svc._run_external_verification(
                verification_type=TestRunExternalVerification.client_specific,
                user_id=TestRunExternalVerification.user_id,
                dependent_date_of_birth=TestRunExternalVerification.dependent_date_of_birth,
                params=TestRunExternalVerification.params,
            )
        assert res == []

    @staticmethod
    def test_run_client_specific_when_missing_params():
        svc = EnterpriseVerificationService()
        with mock.patch(
            "eligibility.utils.verification_utils.VerificationParams.has_necessary_client_specific_params",
            return_value=False,
        ), pytest.raises(EnterpriseVerificationQueryError):
            _ = svc._run_external_verification(
                verification_type=TestRunExternalVerification.client_specific,
                user_id=TestRunExternalVerification.user_id,
                dependent_date_of_birth=TestRunExternalVerification.dependent_date_of_birth,
                params=TestRunExternalVerification.params,
            )

    @staticmethod
    def test_run_sso_when_member_found():
        svc = EnterpriseVerificationService()
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.verify_member_sso",
            return_value=TestRunExternalVerification.member_found,
        ):
            res = svc._run_external_verification(
                verification_type=TestRunExternalVerification.sso,
                user_id=TestRunExternalVerification.user_id,
                dependent_date_of_birth=TestRunExternalVerification.dependent_date_of_birth,
                params=TestRunExternalVerification.params,
            )

        assert res == [TestRunExternalVerification.member_found]

    @staticmethod
    def test_run_sso_when_member_not_found():
        svc = EnterpriseVerificationService()
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.verify_member_sso",
            return_value=None,
        ):
            res = svc._run_external_verification(
                verification_type=TestRunExternalVerification.sso,
                user_id=TestRunExternalVerification.user_id,
                dependent_date_of_birth=TestRunExternalVerification.dependent_date_of_birth,
                params=TestRunExternalVerification.params,
            )
        assert res == []

    @staticmethod
    def test_non_external_verification_type_return_empty_list():
        svc = EnterpriseVerificationService()
        res = svc._run_external_verification(
            verification_type=TestRunExternalVerification.alternate,
            user_id=TestRunExternalVerification.user_id,
            dependent_date_of_birth=TestRunExternalVerification.dependent_date_of_birth,
            params=TestRunExternalVerification.params,
        )

        assert res == []


class TestRunAdditionalVerification:
    @staticmethod
    def test_no_dob_not_called_if_over_eligibility_found():
        member_found = EligibilityMemberFactory.create()
        svc = EnterpriseVerificationService()
        with mock.patch(
            "eligibility.utils.verification_utils.is_over_eligibility_enabled",
            return_value=True,
        ), mock.patch(
            "eligibility.utils.verification_utils.VerificationParams.has_necessary_params_for_overeligibility",
            return_value=True,
        ), mock.patch(
            "eligibility.service.EnterpriseVerificationService.verify_member_overeligibility",
            return_value=[member_found],
        ), mock.patch(
            "eligibility.utils.verification_utils.is_no_dob_verification_enabled",
            return_value=True,
        ), mock.patch(
            "eligibility.utils.verification_utils.VerificationParams.has_necessary_params_for_no_dob_verification",
            return_value=True,
        ), mock.patch(
            "eligibility.service.EnterpriseVerificationService.verify_member_no_dob",
        ) as mock_no_dob:
            res = svc._run_additional_verification(
                verification_type="aleternate",
                user_id=1,
                dependent_date_of_birth=datetime.date(1999, 12, 16),
                params=VerificationParams(user_id=1),
            )
        assert res == [member_found]
        mock_no_dob.assert_not_called

    @staticmethod
    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_no_dob_no_when_over_eligibility_not_found():
        svc = EnterpriseVerificationService()

        with mock.patch(
            "eligibility.utils.verification_utils.is_over_eligibility_enabled",
            return_value=True,
        ), mock.patch(
            "eligibility.utils.verification_utils.VerificationParams.has_necessary_params_for_overeligibility",
            return_value=True,
        ), mock.patch(
            "eligibility.service.EnterpriseVerificationService.verify_member_overeligibility",
            return_value=[],
        ), mock.patch(
            "eligibility.utils.verification_utils.is_no_dob_verification_enabled",
            return_value=True,
        ), mock.patch(
            "eligibility.utils.verification_utils.VerificationParams.has_necessary_params_for_no_dob_verification",
            return_value=True,
        ), mock.patch(
            "eligibility.service.EnterpriseVerificationService.verify_member_no_dob",
            return_value=[],
        ) as mock_no_dob:
            res = svc._run_additional_verification(
                user_id=1,
                verification_type="aleternate",
                dependent_date_of_birth=datetime.date(1999, 12, 16),
                params=VerificationParams(
                    user_id=1,
                    company_email="mock@sso.com",
                    first_name="user_fn",
                    last_name="user_ln",
                ),
            )
        assert res == []
        mock_no_dob.assert_called_once_with(
            email="mock@sso.com", first_name="user_fn", last_name="user_ln"
        )

    @staticmethod
    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_no_dob_no_when_over_eligibility_not_found_partner_enroll():
        svc = EnterpriseVerificationService()

        with mock.patch(
            "eligibility.utils.verification_utils.is_over_eligibility_enabled",
            return_value=True,
        ), mock.patch(
            "eligibility.utils.verification_utils.VerificationParams.has_necessary_params_for_overeligibility",
            return_value=True,
        ), mock.patch(
            "eligibility.service.EnterpriseVerificationService.verify_member_overeligibility",
            return_value=[],
        ), mock.patch(
            "eligibility.utils.verification_utils.is_no_dob_verification_enabled",
            return_value=True,
        ), mock.patch(
            "eligibility.utils.verification_utils.VerificationParams.has_necessary_params_for_no_dob_verification",
            return_value=True,
        ), mock.patch(
            "eligibility.service.EnterpriseVerificationService.verify_member_no_dob",
            return_value=[],
        ) as mock_no_dob:
            res = svc._run_additional_verification(
                verification_type="aleternate",
                user_id=1,
                dependent_date_of_birth=datetime.date(1999, 12, 16),
                params=VerificationParams(
                    user_id=1,
                    company_email="mock@sso.com",
                    first_name="user_fn",
                    last_name="user_ln",
                    employee_first_name="emp_fn",
                    employee_last_name="emp_ln",
                ),
            )
        assert res == []
        mock_no_dob.assert_called_once_with(
            email="mock@sso.com", first_name="emp_fn", last_name="emp_ln"
        )


class TestGetEnterpriseAssociationAndVerifications:
    @staticmethod
    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_get_verification_for_user_is_called(eligibility_service):
        # Given
        user_id = 1
        verification_type = "standard"
        params = factories.StandardVerificationParams.create()
        eligibility_service.e9y.get_verification_for_user = mock.MagicMock()

        # When
        eligibility_service.get_enterprise_association(
            user_id=user_id,
            verification_type=verification_type,
            **params,
        )

        # Then
        eligibility_service.e9y.get_verification_for_user.assert_called()

    @staticmethod
    def test_create_verification_not_called_if_verification_exists_same_org(
        eligibility_service,
    ):
        # Given
        user_id = 1
        verification_type = "standard"
        params = factories.StandardVerificationParams.create()
        verification = factories.VerificationFactory.create(organization_id=1)
        eligibility_service.e9y.get_verification_for_user = mock.MagicMock(
            return_value=verification
        )
        eligibility_service.e9y.create_verification_for_user = mock.MagicMock()

        # When
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.run_verification_for_user"
        ) as mock_run_verification:
            # member returned from same org
            mock_run_verification.return_value = [
                factories.EligibilityMemberFactory.create(organization_id=1)
            ]

            eligibility_service.get_enterprise_association(
                user_id=user_id,
                verification_type=verification_type,
                **params,
            )

        # Then
        eligibility_service.e9y.create_verification_for_user.assert_not_called()

    @staticmethod
    def test_create_verification_not_called_if_verification_exists_different_org(
        eligibility_service,
    ):
        # Given
        user_id = 1
        verification_type = "standard"
        params = factories.StandardVerificationParams.create()
        verification = factories.VerificationFactory.create(organization_id=1)
        eligibility_service.e9y.get_verification_for_user = mock.MagicMock(
            return_value=verification
        )
        eligibility_service.e9y.create_verification_for_user = mock.MagicMock()

        # When
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.run_verification_for_user"
        ) as mock_run_verification:
            # member returned from different org
            mock_run_verification.return_value = [
                factories.EligibilityMemberFactory.create(organization_id=222)
            ]

            eligibility_service.get_enterprise_association(
                user_id=user_id,
                verification_type=verification_type,
                **params,
            )

        # Then
        eligibility_service.e9y.create_verification_for_user.assert_called()

    @staticmethod
    @pytest.mark.skip(reason="Skip deprecated test.")
    def test_create_verification_called_if_verification_not_found(eligibility_service):
        # Given
        user_id = 1
        verification_type = "standard"
        params = factories.StandardVerificationParams.create()
        eligibility_service.e9y.get_verification_for_user = mock.MagicMock(
            return_value=None
        )
        eligibility_service.e9y.create_verification_for_user = mock.MagicMock()

        # When
        eligibility_service.get_enterprise_association(
            user_id=user_id,
            verification_type=verification_type,
            **params,
        )

        # Then
        eligibility_service.e9y.create_verification_for_user.assert_called()


class TestShadowReadVerification:
    @staticmethod
    def test_get_all_verifications_for_user_called(eligibility_service):
        # Given
        user_id = 1
        eligibility_service.e9y.get_all_verifications_for_user = mock.MagicMock()

        # When
        eligibility_service.get_eligible_organization_ids_for_user(user_id=user_id)

        # Then
        eligibility_service.e9y.get_all_verifications_for_user.assert_called()

    @staticmethod
    @pytest.mark.parametrize(
        argnames="a,b,expected",
        argvalues=[
            ("", None, True),
            (None, "", True),
            ("", "", True),
            (None, None, True),
            ("I LOVE ELIGIBILITY", "I LOVE ELIGIBILITY", True),
            ("NYC", None, False),
            ("", "NYC", False),
            ("  dreams", "dreams    ", True),
            ("DREAMS", "dreAMS", True),
        ],
    )
    def test_empty_or_equal(a, b, expected):
        # Given / When
        result: bool = _empty_or_equal(a, b)
        # Then
        assert expected == result

    @staticmethod
    def test_get_verification_for_user_cache_hit(eligibility_service):
        # Given
        user_id = 1
        oe: OrganizationEmployee = OrganizationEmployeeFactory()
        verification: EligibilityVerification = factories.VerificationFactory(
            organization_id=oe.organization_id,
            unique_corp_id=oe.unique_corp_id,
            dependent_id=oe.dependent_id,
            first_name=oe.first_name,
            last_name=oe.last_name,
            date_of_birth=oe.date_of_birth,
            email=oe.email,
            work_state=oe.work_state,
        )

        # When
        eligibility_service.org_id_cache.get.return_value = [1]
        eligibility_service.e9y.get_all_verifications_for_user = mock.MagicMock(
            return_value=[verification]
        )
        # When
        eligibility_service.get_eligible_organization_ids_for_user(user_id=user_id)

        # Then
        eligibility_service.org_id_cache.get.assert_called()
        eligibility_service.e9y.get_all_verifications_for_user.assert_not_called()

    @staticmethod
    def test_get_verification_for_user_cache_miss(eligibility_service):
        # Given
        user_id = 1
        oe: OrganizationEmployee = OrganizationEmployeeFactory()
        verification: EligibilityVerification = factories.VerificationFactory(
            organization_id=oe.organization_id,
            unique_corp_id=oe.unique_corp_id,
            dependent_id=oe.dependent_id,
            first_name=oe.first_name,
            last_name=oe.last_name,
            date_of_birth=oe.date_of_birth,
            email=oe.email,
            work_state=oe.work_state,
        )
        eligibility_service.e9y.get_all_verifications_for_user = mock.MagicMock(
            return_value=[verification]
        )

        # When
        eligibility_service.get_eligible_organization_ids_for_user(user_id=user_id)

        # Then
        eligibility_service.org_id_cache.get.assert_called()
        eligibility_service.org_id_cache.add.assert_called()
        eligibility_service.e9y.get_all_verifications_for_user.assert_called()

    @staticmethod
    def test_get_eligible_organization_ids_for_user_only_cache_list(
        eligibility_service,
    ):
        with mock.patch(
            "api.eligibility.service.EnterpriseVerificationService._get_raw_organization_ids_for_user",
            return_value={1, 2, 3},
        ):
            # When
            eligibility_service.get_eligible_organization_ids_for_user(user_id=111)
            eligibility_service.org_id_cache.add.assert_not_called()

    @staticmethod
    def test_get_eligible_organization_ids_for_user_handle_old_cache_value(
        eligibility_service,
    ):
        # Given
        user_id = 1
        oe: OrganizationEmployee = OrganizationEmployeeFactory()
        verification: EligibilityVerification = factories.VerificationFactory(
            organization_id=oe.organization_id,
            unique_corp_id=oe.unique_corp_id,
            dependent_id=oe.dependent_id,
            first_name=oe.first_name,
            last_name=oe.last_name,
            date_of_birth=oe.date_of_birth,
            email=oe.email,
            work_state=oe.work_state,
        )

        # When
        eligibility_service.org_id_cache.get.return_value = 1
        eligibility_service.e9y.get_all_verifications_for_user = mock.MagicMock(
            return_value=[verification]
        )
        # When
        eligibility_service.get_eligible_organization_ids_for_user(user_id=user_id)

        # Then
        eligibility_service.org_id_cache.get.assert_called()
        eligibility_service.e9y.get_all_verifications_for_user.assert_called()


class TestAssociateUserToMember:
    def test_associate_user_id_to_member_bad_input(self, eligibility_service):
        # Given
        member_1: EligibilityMember = factories.EligibilityMemberFactory.create()
        member_2: EligibilityMember = factories.EligibilityMemberFactory.create(
            organization_id=member_1.organization_id
        )

        with pytest.raises(EnterpriseVerificationOverEligibilityError) as exc_info:
            eligibility_service.associate_user_id_to_members(
                user_id=12, members=[member_1, member_2], verification_type="lookup"
            )

        assert exc_info.value.verification_type == "lookup"
        assert exc_info.value.user_id == 12
        assert set(exc_info.value.orgs_and_members) == set(
            [
                (member_1.organization_id, member_1.id),
                (member_2.organization_id, member_2.id),
            ]
        )

    def test_associate_user_id_to_member_bad_org(
        self, eligibility_service, mock_organization_employee_repository, factories
    ):
        # Given
        user = factories.DefaultUserFactory.create()

        member_1: EligibilityMember = EligibilityMemberFactory.create()
        member_2: EligibilityMember = EligibilityMemberFactory.create()

        employee_1 = factories.OrganizationEmployeeFactory.create(
            eligibility_member_id=member_1.id,
            organization_id=member_1.organization_id + 10,
        )
        factories.UserOrganizationEmployeeFactory.create(
            user=user,
            organization_employee=employee_1,
            ended_at=datetime.datetime.utcnow() - datetime.timedelta(days=7),
        )
        verification_type = "standard"

        # When
        mock_organization_employee_repository.get_by_e9y_member_id_or_org_identity.return_value = [
            employee_1
        ]

        with mock.patch("logging.getLogger") as mock_get_logger:
            mock_logger = mock_get_logger.return_value
            eligibility_service.associate_user_id_to_members(
                user_id=user.id,
                members=[member_1, member_2],
                verification_type=verification_type,
            )

            mock_logger.warning.assert_called()

    def test_associate_user_id_to_member(
        self,
        mock_organization_employee_repository,
        mock_user_organization_employee_repository,
        eligibility_service,
        factories,
    ):
        # Given
        user = factories.DefaultUserFactory.create()

        member_1: EligibilityMember = EligibilityMemberFactory.create()
        member_2: EligibilityMember = EligibilityMemberFactory.create()
        employee_1 = factories.OrganizationEmployeeFactory.create(
            eligibility_member_id=member_1.id
        )
        factories.UserOrganizationEmployeeFactory.create(
            user=user,
            organization_employee=employee_1,
            ended_at=datetime.datetime.utcnow() - datetime.timedelta(days=7),
        )
        verification_type = "standard"

        # When
        mock_organization_employee_repository.get_by_e9y_member_id_or_org_identity.return_value = [
            member_1
        ]

        # Then
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.associate_user_id_to_employees"
        ) as mock_user_to_employees:
            eligibility_service.associate_user_id_to_members(
                user_id=user.id,
                members=[member_1, member_2],
                verification_type=verification_type,
            )

            assert (
                mock_organization_employee_repository.get_by_e9y_member_id_or_org_identity.call_count
                == 1
            )
            assert mock_user_to_employees.call_count == 1


class TestIsAssociatedToUser:
    @pytest.mark.parametrize(
        argnames="settings",
        argvalues=[
            OrganizationAssociationSettings(
                organization_id=1,
                employee_only=False,
                medical_plan_only=False,
                beneficiaries_enabled=False,
            ),
            OrganizationAssociationSettings(
                organization_id=1,
                employee_only=False,
                medical_plan_only=True,
                beneficiaries_enabled=True,
            ),
        ],
        ids=[
            "not-employee-only",
            "medical-plan-only-and-beneficiaries-enabled",
        ],
    )
    @pytest.mark.parametrize(
        argnames="user_id,claims,expected_is_claimed",
        argvalues=[
            (1, {2}, False),
            (1, {1}, True),
        ],
        ids=["user-not-associated", "user-is-associated"],
    )
    def test_is_claimed(
        self, eligibility_service, settings, user_id, claims, expected_is_claimed
    ):
        # Given
        verification_type = "client_specific"
        association_id = 10
        member_id = 11
        eligibility_service.employees.get_existing_claims.return_value = claims
        eligibility_service.employees.get_association_settings.return_value = settings
        # When
        is_claimed = eligibility_service.is_associated_to_user(
            user_id=user_id,
            association_id=association_id,
            verification_type=verification_type,
            member_id=member_id,
        )
        # Then
        assert is_claimed == expected_is_claimed

    @pytest.mark.parametrize(
        argnames="settings",
        argvalues=[
            OrganizationAssociationSettings(
                organization_id=1,
                employee_only=True,
                medical_plan_only=False,
                beneficiaries_enabled=False,
            ),
            OrganizationAssociationSettings(
                organization_id=1,
                employee_only=False,
                medical_plan_only=True,
                beneficiaries_enabled=False,
            ),
        ],
        ids=["employee-only", "medical-plan-only-and-no-beneficiaries"],
    )
    def test_exclusive_claims_is_claimed(self, eligibility_service, settings):
        # Given
        verification_type = "client_specific"
        user_id = 1
        association_id = 10
        claims = {2}
        member_id = 11
        eligibility_service.employees.get_existing_claims.return_value = claims
        eligibility_service.employees.get_association_settings.return_value = settings
        # When/Then
        with pytest.raises(service.EnterpriseVerificationConflictError):
            eligibility_service.is_associated_to_user(
                user_id=user_id,
                association_id=association_id,
                verification_type=verification_type,
                member_id=member_id,
            )


class TestGetEligibleOrganizationIdsForUser:
    user_id = 1
    organization_id = 100
    verification: EligibilityVerification = factories.VerificationFactory(
        organization_id=organization_id,
        unique_corp_id="mock_unique_corp_id",
        dependent_id="mock_dependent_id",
        first_name="mock_first_name",
        last_name="mock_last_name",
    )

    def test_get_organization_id_for_user(self, eligibility_service):
        # Given
        eligibility_service.e9y.get_all_verifications_for_user = mock.MagicMock(
            return_value=[TestGetEligibleOrganizationIdsForUser.verification]
        )

        # When
        org_ids = eligibility_service.get_eligible_organization_ids_for_user(
            user_id=TestGetEligibleOrganizationIdsForUser.user_id
        )

        # Then
        assert org_ids == {TestGetEligibleOrganizationIdsForUser.organization_id}

    def test_get_organization_id_for_user_none(self, eligibility_service):
        # Given
        eligibility_service.e9y.get_all_verifications_for_user = mock.MagicMock(
            return_value=[]
        )

        # When
        org_ids = eligibility_service.get_eligible_organization_ids_for_user(
            user_id=TestGetEligibleOrganizationIdsForUser.user_id
        )

        # Then
        assert org_ids == set()


class TestGetOrgE9ySettings:
    def test_get_org_e9y_settings(self, eligibility_service):
        # Given
        expected: EnterpriseEligibilitySettings = (
            factories.EnterpriseEligibilitySettingsFactory.create()
        )
        eligibility_service.orgs.get_eligibility_settings.return_value = expected

        # When
        fetched: EnterpriseEligibilitySettings = (
            eligibility_service.get_org_e9y_settings(
                organization_id=expected.organization_id
            )
        )

        # Then
        assert expected == fetched


class TestGetVerificationForUser:
    def test_get_verification_for_user_when_not_found(self, eligibility_service):
        # Given
        eligibility_service.e9y.get_verification_for_user.return_value = None

        # When
        verification: EligibilityVerification = (
            eligibility_service.get_verification_for_user(user_id=1, organization_id=1)
        )

        # Then
        assert verification is None

    def test_get_verification_for_user_when_found(self, eligibility_service):
        # Given
        org: Organization = OrganizationFactory.create()
        expected: OrganizationEmployee = OrganizationEmployeeFactory.create(
            organization=org
        )
        eligibility_service.e9y.get_verification_for_user.return_value = expected

        # When
        verification: EligibilityVerification = (
            eligibility_service.get_verification_for_user(
                user_id=1, organization_id=org.id
            )
        )

        # Then
        assert verification


class TestGetVerificationForUserAndOrg:
    def test_get_verification_for_user_and_org_no_member_found(
        self, eligibility_service: service.EnterpriseVerificationService
    ):
        # Given
        eligibility_service.e9y.get_all_verifications_for_user.return_value = []

        # When
        verification = eligibility_service.get_verification_for_user_and_org(
            user_id=1, organization_id=1
        )

        # Then
        assert verification is None

    def test_get_verification_for_user_and_org_one_member_found(
        self, eligibility_service: service.EnterpriseVerificationService
    ):
        # Given
        org: Organization = OrganizationFactory.create()
        member = factories.EligibilityMemberFactory.create(organization_id=org.id)

        eligibility_service.e9y.get_all_verifications_for_user.return_value = [member]

        # When
        verification = eligibility_service.get_verification_for_user_and_org(
            user_id=1,
            organization_id=org.id,
        )

        # Then
        assert verification == member

    def test_get_verification_for_user_and_org_success_comparison_fail(
        self, eligibility_service: service.EnterpriseVerificationService
    ):
        # Given
        org: Organization = OrganizationFactory.create()
        member = factories.EligibilityMemberFactory.create(organization_id=org.id)

        eligibility_service.e9y.get_all_verifications_for_user.return_value = [member]

        # When
        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_verification_for_user",
            side_effect=Exception(),
        ):
            verification = eligibility_service.get_verification_for_user_and_org(
                user_id=1,
                organization_id=org.id,
            )

        # Then
        assert verification == member

    def test_get_verification_for_user_and_org_multi_member_found(
        self, eligibility_service: service.EnterpriseVerificationService
    ):
        # Given
        org: Organization = OrganizationFactory.create()
        member_1 = factories.EligibilityMemberFactory.create(organization_id=org.id)
        member_2 = factories.EligibilityMemberFactory.create(organization_id=org.id)

        eligibility_service.e9y.get_all_verifications_for_user.return_value = [
            member_1,
            member_2,
        ]

        # When
        verification = eligibility_service.get_verification_for_user_and_org(
            user_id=1,
            organization_id=org.id,
        )

        # Then
        assert verification is None


class TestGetAllVerificationsForUser:
    def test_get_all_verification_for_user_no_members(self, eligibility_service):
        # Given
        eligibility_service.e9y.get_all_verifications_for_user.return_value = []

        # When
        verifications: List[
            EligibilityVerification
        ] = eligibility_service.get_all_verifications_for_user(
            user_id=1,
        )

        # Then
        assert len(verifications) == 0

    def test_get_all_verification_for_user(
        self, eligibility_service: service.EnterpriseVerificationService
    ):
        # Given
        member_1: EligibilityMember = factories.EligibilityMemberFactory.create(
            effective_range=DateRange(
                lower=datetime.datetime.utcnow() - datetime.timedelta(days=180),
                upper=datetime.datetime.utcnow() - datetime.timedelta(days=7),
                upper_inc=True,
                lower_inc=True,
            )
        )
        member_2: EligibilityMember = factories.EligibilityMemberFactory.create(
            effective_range=DateRange(
                lower=datetime.datetime.utcnow() - datetime.timedelta(days=180),
                upper=datetime.datetime.utcnow() + datetime.timedelta(days=7),
                upper_inc=True,
                lower_inc=True,
            )
        )

        # When
        eligibility_service.e9y.get_all_verifications_for_user.return_value = [
            member_1,
            member_2,
        ]
        eligibility_service.get_all_verifications_for_user(
            user_id=1,
            organization_ids=[member_1.organization_id, member_2.organization_id],
            active_verifications_only=False,
        )
        eligibility_service.e9y.get_all_verifications_for_user.assert_called()


class TestDeactivateVerificationForUser:
    def test_deactivate_verification_for_user_success(
        self, eligibility_service: service.EnterpriseVerificationService
    ):
        # Given
        eligibility_service.e9y.deactivate_verification_for_user.return_value = 1

        # When
        assert (
            eligibility_service.deactivate_verification_for_user(
                user_id=1, verification_id=1
            )
            == 1
        )


class TestIsUserKnownToBeEligibleForOrg:
    def test_is_user_known_to_be_eligible_for_org_no_org_no_verifications(
        self, eligibility_service
    ):
        eligibility_service.e9y.get_all_verifications_for_user.return_value = None
        response = eligibility_service.is_user_known_to_be_eligible_for_org(user_id=1)
        assert response is False

    def test_is_user_known_to_be_eligible_for_org_no_org_with_verifications(
        self, eligibility_service
    ):
        verification: EligibilityVerification = VerificationFactory.create(
            user_id=1, organization_id=70
        )
        eligibility_service.e9y.get_all_verifications_for_user.return_value = [
            verification
        ]
        response = eligibility_service.is_user_known_to_be_eligible_for_org(
            user_id=1, organization_id=None
        )
        assert response is True

    def test_is_user_known_to_be_eligible_for_org_no_existing_member(
        self, eligibility_service
    ):
        eligibility_service.e9y.get_all_verifications_for_user.return_value = None
        response = eligibility_service.is_user_known_to_be_eligible_for_org(
            user_id=1, organization_id=1
        )
        assert response is False

    def test_is_user_known_to_be_eligible_for_org_existing_member(
        self, eligibility_service
    ):
        verification: EligibilityVerification = VerificationFactory.create(
            user_id=1, organization_id=70
        )
        eligibility_service.e9y.get_all_verifications_for_user.return_value = [
            verification
        ]
        response = eligibility_service.is_user_known_to_be_eligible_for_org(
            user_id=1, organization_id=70
        )
        assert response is True

    def test_is_user_known_to_be_eligible_for_org_exception(self, eligibility_service):
        eligibility_service.e9y.get_all_verifications_for_user.side_effect = Exception()
        response = eligibility_service.is_user_known_to_be_eligible_for_org(
            user_id=1, organization_id=70
        )
        assert response is False


class TestGetPreEligibilityRecords:
    def test_get_pre_eligibility_records_missing_params(self, eligibility_service):
        # When
        response: PreEligibilityResponse = (
            eligibility_service.get_pre_eligibility_records(
                user_id=None,
                first_name=None,
                last_name=None,
                date_of_birth=None,
            )
        )
        # Then
        assert response.match_type == MatchType.INVALID

    def test_get_pre_eligibility_records_missing_user_id(self, eligibility_service):
        oe: OrganizationEmployee = OrganizationEmployeeFactory.create()
        # When
        eligibility_service.get_pre_eligibility_records(
            user_id=None,
            first_name=oe.first_name,
            last_name=oe.last_name,
            date_of_birth=oe.date_of_birth,
        )
        user_id = eligibility_service.e9y.get_by_member_details.call_args_list[
            0
        ].kwargs["user_id"]
        # Then
        assert user_id is None

    def test_get_pre_eligibility_records_with_user_id(self, eligibility_service):
        # Given
        eligibility_verification_for_user: EligibilityVerification = (
            VerificationFactory.create(user_id=1)
        )
        eligibility_service.e9y.get_verification_for_user = (
            eligibility_verification_for_user
        )
        # When
        eligibility_service.get_pre_eligibility_records(
            user_id=1,
            first_name="jane",
            last_name="doe",
            date_of_birth="2000-01-01",
        )
        user_id = eligibility_service.e9y.get_by_member_details.call_args_list[
            0
        ].kwargs["user_id"]
        # Then
        assert user_id == eligibility_verification_for_user.user_id

    def test_is_user_known_to_be_eligible(self, eligibility_service, verification):
        with mock.patch.object(
            service.EnterpriseVerificationService,
            "check_if_user_has_existing_eligibility",
        ) as mock_check_if_user_has_existing_eligibility:
            # Given
            mock_check_if_user_has_existing_eligibility.return_value = True
            # When
            is_known_to_be_eligible = eligibility_service.is_user_known_to_be_eligible(
                user_id=1,
                first_name="jane",
                last_name="doe",
                date_of_birth="2000-01-01",
            )
            # Then
            assert is_known_to_be_eligible is True

    def test_is_user_known_to_be_eligible_not_eligible(
        self, eligibility_service, default_user
    ):
        with mock.patch.object(
            service.EnterpriseVerificationService,
            "check_if_user_has_existing_eligibility",
        ) as mock_check_if_user_has_existing_eligibility:
            # Given
            mock_check_if_user_has_existing_eligibility.return_value = False

            # When
            is_known_to_be_eligible = eligibility_service.is_user_known_to_be_eligible(
                user_id=1,
                first_name="jane",
                last_name="doe",
                date_of_birth="2000-01-01",
            )
            # Then
            assert is_known_to_be_eligible is False

    def test_is_user_known_to_be_eligible_no_e9y_response(
        self, eligibility_service, default_user
    ):
        with mock.patch.object(
            eligibility_service.e9y, "get_verification_for_user"
        ) as mock_get_pre_eligibility_records:
            # Given
            mock_get_pre_eligibility_records.return_value = None

            # When
            is_known_to_be_eligible = eligibility_service.is_user_known_to_be_eligible(
                user_id=1,
                first_name="jane",
                last_name="doe",
                date_of_birth="2000-01-01",
            )
            # Then
            assert is_known_to_be_eligible is False


class TestGetEligibleFeaturesForUser:
    def test_get_eligible_features_for_user(self, eligibility_service):
        filtered_ids = [1, 3, 5]

        eligibility_service.features.get_eligible_features_for_user.return_value = (
            e9y_model.EligibleFeaturesForUserResponse(
                features=filtered_ids,
                has_population=True,
            )
        )
        # When
        eligible_features = eligibility_service.get_eligible_features_for_user(
            user_id=1,
            feature_type=e9y_model.FeatureTypes.TRACK_FEATURE,
        )
        # Then
        assert eligible_features == filtered_ids

    def test_get_eligible_features_for_user_no_population(self, eligibility_service):
        eligibility_service.features.get_eligible_features_for_user.return_value = (
            e9y_model.EligibleFeaturesForUserResponse(
                features=[],
                has_population=False,
            )
        )
        # When
        eligible_features = eligibility_service.get_eligible_features_for_user(
            user_id=1,
            feature_type=e9y_model.FeatureTypes.TRACK_FEATURE,
        )
        # Then
        assert eligible_features is None

    def test_get_eligible_features_for_user_no_eligible_features(
        self, eligibility_service
    ):
        eligibility_service.features.get_eligible_features_for_user.return_value = (
            e9y_model.EligibleFeaturesForUserResponse(
                features=[],
                has_population=True,
            )
        )
        # When
        eligible_features = eligibility_service.get_eligible_features_for_user(
            user_id=1,
            feature_type=e9y_model.FeatureTypes.TRACK_FEATURE,
        )
        # Then
        assert eligible_features == []

    @pytest.mark.parametrize(
        argnames="user_id,feature_type",
        argvalues=[
            (1, None),
            (None, 1),
            (None, None),
        ],
        ids=[
            "missing_feature_type",
            "missing_user_id",
            "missing_both",
        ],
    )
    def test_get_eligible_features_for_user_no_params(
        self, user_id, feature_type, eligibility_service
    ):
        # When/Then
        # Expect to throw EligibilityFeaturesQueryError
        # get_eligible_features_for_user() missing required keyword-only arguments 'user_id' and/or 'feature_type'
        with pytest.raises(service.EligibilityFeaturesQueryError):
            eligibility_service.get_eligible_features_for_user(
                user_id=user_id, feature_type=feature_type
            )


class TestGetEligibleFeaturesForUserAndOrg:
    def test_get_eligible_features_for_user_and_org(self, eligibility_service):
        filtered_ids = [1, 3, 5]

        eligibility_service.features.get_eligible_features_for_user_and_org.return_value = e9y_model.EligibleFeaturesForUserAndOrgResponse(
            features=filtered_ids,
            has_population=True,
        )
        # When
        eligible_features = eligibility_service.get_eligible_features_for_user_and_org(
            user_id=1,
            organization_id=1,
            feature_type=e9y_model.FeatureTypes.TRACK_FEATURE,
        )
        # Then
        assert eligible_features == filtered_ids

    def test_get_eligible_features_for_user_and_org_no_population(
        self, eligibility_service
    ):
        eligibility_service.features.get_eligible_features_for_user_and_org.return_value = e9y_model.EligibleFeaturesForUserAndOrgResponse(
            features=[],
            has_population=False,
        )
        # When
        eligible_features = eligibility_service.get_eligible_features_for_user_and_org(
            user_id=1,
            organization_id=1,
            feature_type=e9y_model.FeatureTypes.TRACK_FEATURE,
        )
        # Then
        assert eligible_features is None

    def test_get_eligible_features_for_user_and_org_no_eligible_features(
        self, eligibility_service
    ):
        eligibility_service.features.get_eligible_features_for_user_and_org.return_value = e9y_model.EligibleFeaturesForUserAndOrgResponse(
            features=[],
            has_population=True,
        )
        # When
        eligible_features = eligibility_service.get_eligible_features_for_user_and_org(
            user_id=1,
            organization_id=1,
            feature_type=e9y_model.FeatureTypes.TRACK_FEATURE,
        )
        # Then
        assert eligible_features == []

    @pytest.mark.parametrize(
        argnames="user_id,organization_id,feature_type",
        argvalues=[
            (1, 1, None),
            (1, None, 1),
            (1, None, None),
            (None, 1, 1),
            (None, 1, None),
            (None, None, 1),
            (None, None, None),
        ],
        ids=[
            "missing_feature_type",
            "missing_organization_id",
            "missing_org_and_feature_type",
            "missing_user_id",
            "missing_user_and_feature_type",
            "missing_user_and_org",
            "missing_all",
        ],
    )
    def test_get_eligible_features_for_user_and_org_no_params(
        self, user_id, organization_id, feature_type, eligibility_service
    ):
        # When/Then
        # Expect to throw EligibilityFeaturesQueryError
        # get_eligible_features_for_user() missing required keyword-only arguments 'user_id' and/or 'feature_type'
        with pytest.raises(service.EligibilityFeaturesQueryError):
            eligibility_service.get_eligible_features_for_user_and_org(
                user_id=user_id,
                organization_id=organization_id,
                feature_type=feature_type,
            )


class TestGetEligibleFeaturesBySubPopulationId:
    def test_get_eligible_features_by_sub_population_id(self, eligibility_service):
        filtered_ids = [1, 3, 5]

        eligibility_service.features.get_eligible_features_by_sub_population_id.return_value = e9y_model.EligibleFeaturesBySubPopulationIdResponse(
            features=filtered_ids,
            has_definition=True,
        )
        # When
        eligible_features = (
            eligibility_service.get_eligible_features_by_sub_population_id(
                sub_population_id=1,
                feature_type=e9y_model.FeatureTypes.TRACK_FEATURE,
            )
        )
        # Then
        assert eligible_features == filtered_ids

    def test_get_eligible_features_by_sub_population_id_no_features(
        self, eligibility_service
    ):
        eligibility_service.features.get_eligible_features_by_sub_population_id.return_value = e9y_model.EligibleFeaturesBySubPopulationIdResponse(
            features=[],
            has_definition=True,
        )
        # When
        eligible_features = (
            eligibility_service.get_eligible_features_by_sub_population_id(
                sub_population_id=1,
                feature_type=e9y_model.FeatureTypes.TRACK_FEATURE,
            )
        )
        # Then
        assert eligible_features == []

    def test_get_eligible_features_by_sub_population_id_no(self, eligibility_service):
        eligibility_service.features.get_eligible_features_by_sub_population_id.return_value = e9y_model.EligibleFeaturesBySubPopulationIdResponse(
            features=[],
            has_definition=False,
        )
        # When
        eligible_features = (
            eligibility_service.get_eligible_features_by_sub_population_id(
                sub_population_id=1,
                feature_type=e9y_model.FeatureTypes.TRACK_FEATURE,
            )
        )
        # Then
        assert eligible_features is None


class TestGetSubPopulationIdForUser:
    def test_get_sub_population_id(self, eligibility_service):
        eligibility_service.features.get_sub_population_id_for_user.return_value = 1
        # When
        sub_population_id = eligibility_service.get_sub_population_id_for_user(
            user_id=1,
        )
        # Then
        assert sub_population_id == 1

    def test_get_sub_population_id_no_population(self, eligibility_service):
        eligibility_service.features.get_sub_population_id_for_user.return_value = None
        # When
        sub_population_id = eligibility_service.get_sub_population_id_for_user(
            user_id=1,
        )
        # Then
        assert sub_population_id is None


class TestGetSubPopulationIdForUserAndOrg:
    def test_get_sub_population_id_for_user_and_org(self, eligibility_service):
        eligibility_service.features.get_sub_population_id_for_user_and_org.return_value = (
            1
        )
        # When
        sub_population_id = eligibility_service.get_sub_population_id_for_user_and_org(
            user_id=1, organization_id=1
        )
        # Then
        assert sub_population_id == 1

    def test_get_sub_population_id_for_user_and_org_no_population(
        self, eligibility_service
    ):
        eligibility_service.features.get_sub_population_id_for_user_and_org.return_value = (
            None
        )
        # When
        sub_population_id = eligibility_service.get_sub_population_id_for_user_and_org(
            user_id=1, organization_id=1
        )
        # Then
        assert sub_population_id is None


class TestGetOtherUserIdsForFamily:
    def test_get_other_user_ids_in_family(self, eligibility_service):
        # Given
        eligibility_service.e9y.get_other_user_ids_in_family.return_value = [2]
        # When
        user_ids = eligibility_service.get_other_user_ids_in_family(
            user_id=1,
        )
        # Then
        assert user_ids == [2]

    def test_get_other_user_ids_in_family_invalid_input(self, eligibility_service):
        # Given
        user_id = None
        # When - Then
        with pytest.raises(ValueError):
            eligibility_service.get_other_user_ids_in_family(
                user_id=user_id,
            )


class TestIsSingleUser:
    @pytest.mark.parametrize(
        argnames="is_employee_only,is_medical_plan_only,is_beneficiaries_enabled,expected_is_single_user",
        argvalues=[
            (True, False, False, True),
            (False, True, False, True),
            (False, True, True, False),
            (False, False, True, False),
        ],
        ids=[
            "employee-only",
            "medical-plan-beneficiaries-disabled",
            "medical-plan-beneficiaries-enabled",
            "not-employee-not-medical-plan-only",
        ],
    )
    def test_is_single_user(
        self,
        eligibility_service,
        is_employee_only,
        is_medical_plan_only,
        is_beneficiaries_enabled,
        expected_is_single_user,
    ):
        # When
        assert (
            eligibility_service.is_single_user(
                employee_only=is_employee_only,
                medical_plan_only=is_medical_plan_only,
                beneficiaries_enabled=is_beneficiaries_enabled,
            )
            == expected_is_single_user
        )


class TestIsActive:
    @pytest.mark.parametrize(
        argnames="activated_at, expected_is_active",
        argvalues=[
            (None, False),
            (datetime.datetime.utcnow() + datetime.timedelta(days=1), False),
            (datetime.datetime.utcnow() - datetime.timedelta(days=1), True),
            (datetime.datetime.utcnow(), True),
        ],
        ids=[
            "activated-at-is-none",
            "activated-at-in-future",
            "activated-at-in-past",
            "activated-at-is-now",
        ],
    )
    def test_is_active(self, eligibility_service, activated_at, expected_is_active):
        # Given parameterized inputs
        # When
        is_active: bool = eligibility_service.is_active(activated_at=activated_at)
        # Then
        assert is_active == expected_is_active


@contextlib.contextmanager
def no_exception():
    yield


@pytest.mark.parametrize(
    argnames="eligibility_type,verification_type,expectation",
    argvalues=[
        (OrganizationEligibilityType.STANDARD, "standard", no_exception()),
        (OrganizationEligibilityType.FILELESS, "fileless", no_exception()),
        (
            OrganizationEligibilityType.CLIENT_SPECIFIC,
            "client_specific",
            no_exception(),
        ),
        (
            OrganizationEligibilityType.FILELESS,
            "standard",
            pytest.raises(service.EnterpriseVerificationConfigurationError),
        ),
        (
            OrganizationEligibilityType.CLIENT_SPECIFIC,
            "standard",
            pytest.raises(service.EnterpriseVerificationConfigurationError),
        ),
    ],
    ids=[
        "match-non-custom",
        "match-fileless",
        "match-client-specific",
        "no-match-fileless",
        "no-match-client-specific",
    ],
)
def test_validate_verification_type(
    eligibility_service, faker, eligibility_type, verification_type, expectation
):
    # Given
    company_email = faker.email()
    settings = factories.EnterpriseEligibilitySettingsFactory.create(
        eligibility_type=eligibility_type,
    )
    eligibility_service.orgs.get_eligibility_settings_by_email.return_value = settings
    # When/Then
    with expectation:
        eligibility_service.validate_verification_type(
            company_email=company_email, verification_type=verification_type
        )


@pytest.mark.parametrize(
    argnames="verification_type, use_member_record",
    argvalues=[("lookup", True), ("valid_verification_type", False)],
    ids=["short_circuit_lookup", "short_circuit_empty_member_records_and_email"],
)
def test_validate_verification_type_multiple_records_no_records_removed(
    eligibility_service, verification_type, use_member_record, eligibility_member
):
    # Given
    member_records = []
    if use_member_record:
        member_records = [eligibility_member]

    # When
    result = eligibility_service.validate_verification_type_for_multiple_member_records(
        member_records=member_records,
        company_email=None,
        verification_type=verification_type,
    )

    # Then
    assert result == member_records


def test_validate_verification_type_for_multiple_member_records_no_settings_for_org(
    eligibility_service, eligibility_member
):
    # Given
    member_records = [eligibility_member]
    eligibility_service.orgs.get_eligibility_settings_by_email.return_value = None

    # When
    result = eligibility_service.validate_verification_type_for_multiple_member_records(
        member_records=member_records,
        company_email=None,
        verification_type="fileless",
    )

    # Then
    assert result == member_records


def test_validate_verification_type_for_multiple_member_records_org_eligiblity_compatible_verification_type(
    eligibility_service, eligibility_member
):

    # Given
    member_records = [eligibility_member]
    settings = factories.EnterpriseEligibilitySettingsFactory.create(
        eligibility_type=OrganizationEligibilityType.STANDARD,
    )
    eligibility_service.orgs.get_eligibility_settings_by_email.return_value = settings

    # When
    result = eligibility_service.validate_verification_type_for_multiple_member_records(
        member_records=member_records,
        company_email=None,
        verification_type="standard",
    )

    # Then
    assert result == member_records


@pytest.mark.parametrize(
    argnames="eligibility_type",
    argvalues=[
        "lookup",
        OrganizationEligibilityType.CLIENT_SPECIFIC,
    ],
    ids=["short_circuit_lookup", "short_circuit_empty_member_records_and_email"],
)
def test_validate_verification_type_for_multiple_member_records_org_eligiblity_not_compatible_verification_type(
    eligibility_service, eligibility_member, eligibility_type
):
    """Exclude records because the client requires fileless/client_specific, and this was not used for verification"""
    # Given
    member_records = []
    settings = factories.EnterpriseEligibilitySettingsFactory.create(
        eligibility_type=eligibility_type,
    )
    eligibility_service.orgs.get_eligibility_settings.return_value = settings

    # When
    result = eligibility_service.validate_verification_type_for_multiple_member_records(
        member_records=member_records,
        company_email=None,
        verification_type="standard",
    )

    # Then
    assert result == []


def test_associate_to_user_handle_integrity_error(
    eligibility_service, patch_report_last_eligible_through_organization
):
    # Given
    user_id = 1
    verification_type = "standard"
    employee = mock.MagicMock()
    eligibility_service.employees.associate_to_user_id.side_effect = integrity_error
    eligibility_service.employees.get_existing_claims.return_value = set()
    # When/Then
    with pytest.raises(service.EnterpriseVerificationError):
        eligibility_service.associate_user_id_to_employees(
            user_id=user_id,
            employee_info_list=[
                EmployeeInfo(employee=employee, associated_to_user=False)
            ],
            verification_type=verification_type,
        )
    patch_report_last_eligible_through_organization.assert_not_called()


@pytest.mark.parametrize(
    argnames="associated_to_user",
    argvalues=[
        True,
        False,
    ],
    ids=("associated_to_user", "not_associated_to_user"),
)
def test_associate_to_user_single(
    associated_to_user,
    mock_organization_employee_repository,
    mock_user_organization_employee_repository,
    eligibility_service,
    patch_report_last_eligible_through_organization,
    factories,
):
    # Given
    user = factories.DefaultUserFactory.create()
    employee = factories.OrganizationEmployeeFactory.create()
    verification_type = "standard"
    # When
    eligibility_service.associate_user_id_to_employees(
        user_id=user.id,
        employee_info_list=[
            EmployeeInfo(
                employee=employee,
                associated_to_user=associated_to_user,
                member_id=None,
            )
        ],
        verification_type=verification_type,
    )

    # Then
    assert mock_organization_employee_repository.associate_to_user_id.call_count == (
        0 if associated_to_user else 1
    )
    assert (
        mock_user_organization_employee_repository.reset_user_associations.call_count
        == (1 if associated_to_user else 0)
    )
    patch_report_last_eligible_through_organization.delay.assert_called_with(user.id)


def test_associate_to_user(
    mock_organization_employee_repository,
    mock_user_organization_employee_repository,
    eligibility_service,
    patch_report_last_eligible_through_organization,
    factories,
):
    # Given
    user = factories.DefaultUserFactory.create()
    employee_1 = factories.OrganizationEmployeeFactory.create()
    factories.UserOrganizationEmployeeFactory.create(
        user=user,
        organization_employee=employee_1,
        ended_at=datetime.datetime.utcnow() - datetime.timedelta(days=7),
    )

    employee_2 = factories.OrganizationEmployeeFactory.create()
    verification_type = "standard"

    # When
    eligibility_service.associate_user_id_to_employees(
        user_id=user.id,
        employee_info_list=[
            EmployeeInfo(
                employee=employee_1,
                associated_to_user=True,
                member_id=None,
            ),
            EmployeeInfo(employee=employee_2, associated_to_user=False),
        ],
        verification_type=verification_type,
    )

    # Then
    assert mock_organization_employee_repository.associate_to_user_id.call_count == 1
    assert (
        mock_user_organization_employee_repository.reset_user_associations.call_count
        == 1
    )

    patch_report_last_eligible_through_organization.delay.assert_called_with(user.id)


def integrity_error(**_):
    raise sqlalchemy.exc.IntegrityError("", {}, "")


class TestSuccessfullyEnrollPartner:
    def test_successfully_enroll_partner_no_inviter_tracks(self, factories):
        enterprise_user = factories.EnterpriseUserFactory.create()
        new_user = factories.DefaultUserFactory.create()

        assert len(new_user.active_tracks) == 0
        enterprise_user.active_tracks = []
        assert len(enterprise_user.active_tracks) == 0

        result = service.successfully_enroll_partner(
            enterprise_user.id, new_user, "whatever"
        )

        assert result is True
        assert len(new_user.active_tracks) == 0

    def test_successfully_enroll_partner_recipient_already_has_tracks(self, factories):
        enterprise_user = factories.EnterpriseUserFactory.create()
        new_user = factories.DefaultUserFactory.create()

        new_user.active_tracks = enterprise_user.active_tracks
        previous_active_tracks = new_user.active_tracks[:]
        assert len(new_user.active_tracks) > 0

        result = service.successfully_enroll_partner(
            enterprise_user.id, new_user, "whatever"
        )

        assert result is True
        assert new_user.active_tracks == previous_active_tracks

    def test_successfully_enroll_partner_sender_has_no_active_verification(
        self, factories
    ):
        # Given
        enterprise_user = factories.EnterpriseUserFactory.create()
        new_user = factories.DefaultUserFactory.create()

        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_verification_for_user"
        ) as mock_get_verification_for_user:
            mock_get_verification_for_user.return_value = None

            # When
            result = service.successfully_enroll_partner(
                enterprise_user.id, new_user, "whatever"
            )

            # Then
            assert result is False

    def test_successfully_enroll_partner_partner_verification_failed(self, factories):
        # Given
        enterprise_user = factories.EnterpriseUserFactory.create()
        new_user = factories.DefaultUserFactory.create()
        verification = e9y_factories.build_verification_from_oe(
            user_id=enterprise_user.id, employee=enterprise_user.organization_employee
        )

        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_verification_for_user",
            return_value=verification,
        ), mock.patch(
            "eligibility.service.EnterpriseVerificationService.generate_verification_for_user"
        ) as mock_generate_verification_for_user:
            mock_generate_verification_for_user.return_value = None

            # When
            result = service.successfully_enroll_partner(
                enterprise_user.id, new_user, "whatever"
            )

            # Then
            assert result is False

    def test_successfully_enroll_partner_with_active_tracks(self, factories):
        # Given
        enterprise_user = factories.EnterpriseUserFactory.create()
        new_user = factories.DefaultUserFactory.create()

        verification = e9y_factories.build_verification_from_oe(
            user_id=enterprise_user.id, employee=enterprise_user.organization_employee
        )
        partner_verification = e9y_factories.VerificationFactory.create(
            user_id=new_user.id,
        )

        member_track = factories.MemberTrackFactory.create()

        with mock.patch(
            "eligibility.service.EnterpriseVerificationService.get_verification_for_user",
            return_value=verification,
        ), mock.patch(
            "eligibility.service.EnterpriseVerificationService.generate_verification_for_user",
            return_value=partner_verification,
        ) as mock_create_verification, mock.patch(
            "models.tracks.lifecycle.initiate",
            return_value=member_track,
        ):

            # When
            result = service.successfully_enroll_partner(
                enterprise_user.id, new_user, "whatever"
            )

            # Then
            assert result is True
            mock_create_verification.assert_called_once_with(
                user_id=new_user.id,
                verification_type=mock.ANY,
                organization_id=mock.ANY,
                unique_corp_id=mock.ANY,
                dependent_id=mock.ANY,
                first_name=mock.ANY,
                last_name=mock.ANY,
                eligibility_member_id=mock.ANY,
                additional_fields=mock.ANY,
                verification_session=mock.ANY,
            )


class TestCreateTestEligibilityMembersForOrganization:
    def test_create_records_for_organization_success(self, eligibility_service):
        organization_id = 1
        json_str = '[{"first_name": "TestQA", "last_name": "User", "dependent_id": "", "email": "test@test.com", "unique_corp_id": "", "date_of_birth": "2001-01-01", "work_state": "WA", "work_country": "US"}]'
        data: List[Dict[str, str]] = json.loads(json_str)
        expected_response = []
        eligibility_service.e9y.create_test_member_records_for_organization.return_value = (
            expected_response
        )
        actual_response = eligibility_service.create_test_eligibility_member_records(
            organization_id=organization_id, test_member_records=data
        )
        assert actual_response == expected_response

    def test_create_records_for_organization_missing_params_organization_id(
        self, eligibility_service
    ):
        json_str = '[{"first_name": "TestQA", "last_name": "User", "dependent_id": "", "email": "test@test.com", "unique_corp_id": "", "date_of_birth": "2001-01-01", "work_state": "WA", "work_country": "US"}]'
        data: List[Dict[str, str]] = json.loads(json_str)
        with pytest.raises(service.EligibilityTestMemberCreationError):
            eligibility_service.create_test_eligibility_member_records(
                organization_id=None, test_member_records=data
            )

    def test_create_records_for_organization_missing_params_test_members(
        self, eligibility_service
    ):
        with pytest.raises(service.EligibilityTestMemberCreationError):
            eligibility_service.create_test_eligibility_member_records(
                organization_id=1, test_member_records=[]
            )

    def test_create_records_for_organization_prod_env(self, eligibility_service):
        json_str = '[{"first_name": "TestQA", "last_name": "User", "dependent_id": "", "email": "test@test.com", "unique_corp_id": "", "date_of_birth": "2001-01-01", "work_state": "WA", "work_country": "US"}]'
        data: List[Dict[str, str]] = json.loads(json_str)
        with pytest.raises(service.EligibilityTestMemberCreationError):
            with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
                eligibility_service.create_test_eligibility_member_records(
                    organization_id=1,
                    test_member_records=data,
                )


class TestCompareVerifications:
    def test_compare_verifications_both_none(self):
        assert (
            compare_verifications(
                user_id=1, previous_verification=None, new_verification=None
            )
            is True
        )

    def test_compare_verifications_one_none(self):
        verification = VerificationFactory.create(user_id=1)
        assert (
            compare_verifications(
                user_id=1, previous_verification=None, new_verification=verification
            )
            is False
        )

    def test_compare_verifications_success(self):
        verification = VerificationFactory.create(user_id=1)
        cloned_verification = copy.copy(verification)
        assert (
            compare_verifications(
                user_id=1,
                previous_verification=verification,
                new_verification=cloned_verification,
            )
            is True
        )

    def test_compare_verifications_different(self):
        verification = VerificationFactory.create(user_id=1)
        cloned_verification = copy.copy(verification)
        cloned_verification.last_name = "changed"
        assert (
            compare_verifications(
                user_id=1,
                previous_verification=verification,
                new_verification=cloned_verification,
            )
            is False
        )
