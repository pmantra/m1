import datetime
from unittest import mock

import pytest

from eligibility.utils.verification_utils import VerificationParams


class TestVerificationParams:
    @pytest.mark.parametrize(
        "date_of_birth,organization_id,is_employee,unique_corp_id,expected",
        [
            # date_of_birth None, Not None
            (datetime.date(2022, 1, 1), 1, True, "mock_unique_corp_id", True),
            (None, 1, True, "mock_unique_corp_id", False),
            # organization_id None, Not None
            (datetime.date(2022, 1, 1), None, True, "mock_unique_corp_id", False),
            (None, None, True, "mock_unique_corp_id", False),
            # is_employee False
            (datetime.date(2022, 1, 1), 1, False, "mock_unique_corp_id", True),
            (None, 1, False, "mock_unique_corp_id", False),
            (datetime.date(2022, 1, 1), None, False, "mock_unique_corp_id", False),
            (None, None, False, "mock_unique_corp_id", False),
            # is_employee None
            (datetime.date(2022, 1, 1), 1, None, "mock_unique_corp_id", False),
            (None, 1, None, "mock_unique_corp_id", False),
            (datetime.date(2022, 1, 1), None, None, "mock_unique_corp_id", False),
            (None, None, None, "mock_unique_corp_id", False),
            # unique_corp_id empty
            (datetime.date(2022, 1, 1), 1, True, "", False),
            (None, 1, True, "mock_unique_corp_id", False),
            (datetime.date(2022, 1, 1), None, True, "", False),
            (None, None, True, "", False),
            (datetime.date(2022, 1, 1), 1, False, "", False),
            (None, 1, False, "", False),
            (datetime.date(2022, 1, 1), None, False, "", False),
            (None, None, False, "", False),
            (datetime.date(2022, 1, 1), 1, None, "", False),
            (None, 1, None, "", False),
            (datetime.date(2022, 1, 1), None, None, "", False),
            (None, None, None, "", False),
            # unique_corp_id None
            (datetime.date(2022, 1, 1), 1, True, None, False),
            (None, 1, True, "mock_unique_corp_id", False),
            (datetime.date(2022, 1, 1), None, True, None, False),
            (None, None, True, None, False),
            (datetime.date(2022, 1, 1), 1, False, None, False),
            (None, 1, False, None, False),
            (datetime.date(2022, 1, 1), None, False, None, False),
            (None, None, False, None, False),
            (datetime.date(2022, 1, 1), 1, None, None, False),
            (None, 1, None, None, False),
            (datetime.date(2022, 1, 1), None, None, None, False),
            (None, None, None, None, False),
        ],
    )
    def test_has_necessary_client_specific_params(
        self, date_of_birth, organization_id, is_employee, unique_corp_id, expected
    ):
        # Given
        params = VerificationParams(
            user_id=1,
            organization_id=organization_id,
            is_employee=is_employee,
            date_of_birth=date_of_birth,
            unique_corp_id=unique_corp_id,
        )
        assert params.has_necessary_client_specific_params() == expected

    @pytest.mark.parametrize(
        "work_state,expected",
        [
            ("CA", True),
            ("", False),
            (None, False),
        ],
    )
    def test_has_work_state(self, work_state, expected):
        # Given
        params = VerificationParams(
            user_id=1,
            work_state=work_state,
        )
        assert params.has_work_state() == expected

    @pytest.mark.parametrize(
        "company_email,first_name,last_name,expected",
        [
            ("mock_company_email", "mock_first_name", "mock_last_name", True),
            ("", "mock_first_name", "mock_last_name", False),
            (None, "mock_first_name", "mock_last_name", False),
            ("mock_company_email", "", "mock_last_name", False),
            ("", "", "mock_last_name", False),
            (None, "", "mock_last_name", False),
            ("mock_company_email", None, "mock_last_name", False),
            ("", None, "mock_last_name", False),
            (None, None, "mock_last_name", False),
            ("mock_company_email", "mock_first_name", "", False),
            ("", "mock_first_name", "", False),
            (None, "mock_first_name", "", False),
            ("mock_company_email", "", "", False),
            ("", "", "", False),
            (None, "", "", False),
            ("mock_company_email", None, "", False),
            ("", None, "", False),
            (None, None, "", False),
            ("mock_company_email", "mock_first_name", None, False),
            ("", "mock_first_name", None, False),
            (None, "mock_first_name", None, False),
            ("mock_company_email", "", None, False),
            ("", "", None, False),
            (None, "", None, False),
            ("mock_company_email", None, None, False),
            ("", None, None, False),
            (None, None, None, False),
        ],
    )
    def test_has_email_and_names(self, company_email, first_name, last_name, expected):
        # When
        params = VerificationParams(
            user_id=1,
            company_email=company_email,
            first_name=first_name,
            last_name=last_name,
        )
        # Then
        assert params.has_email_and_name() == expected

        # When
        params = VerificationParams(
            user_id=1,
            company_email=company_email,
            employee_first_name=first_name,
            employee_last_name=last_name,
        )
        # Then
        assert params.has_email_and_employee_name() == expected

    @pytest.mark.parametrize(
        "has_email_and_name,has_email_and_employee_name,expected",
        [
            (True, True, True),
            (True, False, True),
            (False, True, True),
            (False, False, False),
        ],
    )
    def test_has_necessary_params_for_no_dob_verification(
        self, has_email_and_name, has_email_and_employee_name, expected
    ):
        user_id = 1
        params = VerificationParams(user_id=user_id)
        with mock.patch(
            "eligibility.utils.verification_utils.VerificationParams.has_email_and_name",
            return_value=has_email_and_name,
        ), mock.patch(
            "eligibility.utils.verification_utils.VerificationParams.has_email_and_employee_name",
            return_value=has_email_and_employee_name,
        ):
            assert params.has_necessary_params_for_no_dob_verification() == expected

    @pytest.mark.parametrize(
        "date_of_birth,company_email,expected",
        [
            (datetime.date(2022, 1, 1), "mock_company_email", True),
            (None, "mock_company_email", False),
            (datetime.date(2022, 1, 1), "", False),
            (None, "", False),
            (datetime.date(2022, 1, 1), None, False),
            (None, None, False),
        ],
    )
    def test_has_necessary_standard_params(
        self, date_of_birth, company_email, expected
    ):
        # Given
        params = VerificationParams(
            user_id=1,
            date_of_birth=date_of_birth,
            company_email=company_email,
        )
        assert params.has_necessary_standard_params() == expected

    @pytest.mark.parametrize(
        "date_of_birth,first_name,last_name,expected",
        [
            (datetime.date(2022, 1, 1), "mock_first_name", "mock_last_name", True),
            (None, "mock_first_name", "mock_last_name", False),
            (datetime.date(2022, 1, 1), "", "mock_last_name", False),
            (None, "", "mock_last_name", False),
            (datetime.date(2022, 1, 1), None, "mock_last_name", False),
            (None, None, "mock_last_name", False),
            (datetime.date(2022, 1, 1), "mock_first_name", "", False),
            (None, "mock_first_name", "", False),
            (datetime.date(2022, 1, 1), "", "", False),
            (None, "", "", False),
            (datetime.date(2022, 1, 1), None, "", False),
            (None, None, "", False),
            (datetime.date(2022, 1, 1), "mock_first_name", None, False),
            (None, "mock_first_name", None, False),
            (datetime.date(2022, 1, 1), "", None, False),
            (None, "", None, False),
            (datetime.date(2022, 1, 1), None, None, False),
            (None, None, None, False),
        ],
    )
    def test_has_necessary_alternate_params_and_has_necessary_basic_params(
        self, date_of_birth, first_name, last_name, expected
    ):
        # Given
        params = VerificationParams(
            user_id=1,
            date_of_birth=date_of_birth,
            first_name=first_name,
            last_name=last_name,
        )
        assert params.has_necessary_alternate_params() == expected
        assert params.has_necessary_basic_params() == expected

    @pytest.mark.parametrize(
        "date_of_birth,first_name,last_name,company_email,unique_corp_id,expected",
        [
            (
                datetime.date(2022, 1, 1),
                "mock_first_name",
                "mock_last_name",
                "mock_company_email",
                "mock_unique_corp_id",
                True,
            ),
            (
                None,
                "mock_first_name",
                "mock_last_name",
                "mock_company_email",
                "mock_unique_corp_id",
                False,
            ),
            (
                datetime.date(2022, 1, 1),
                "",
                "mock_last_name",
                "mock_company_email",
                "mock_unique_corp_id",
                False,
            ),
            (
                None,
                "",
                "mock_last_name",
                "mock_company_email",
                "mock_unique_corp_id",
                False,
            ),
            (
                datetime.date(2022, 1, 1),
                None,
                "mock_last_name",
                "mock_company_email",
                "mock_unique_corp_id",
                False,
            ),
            (
                None,
                None,
                "mock_last_name",
                "mock_company_email",
                "mock_unique_corp_id",
                False,
            ),
            (
                datetime.date(2022, 1, 1),
                "mock_first_name",
                "",
                "mock_company_email",
                "mock_unique_corp_id",
                False,
            ),
            (
                None,
                "mock_first_name",
                "",
                "mock_company_email",
                "mock_unique_corp_id",
                False,
            ),
            (
                datetime.date(2022, 1, 1),
                "",
                "",
                "mock_company_email",
                "mock_unique_corp_id",
                False,
            ),
            (None, "", "", "mock_company_email", "mock_unique_corp_id", False),
            (
                datetime.date(2022, 1, 1),
                None,
                "",
                "mock_company_email",
                "mock_unique_corp_id",
                False,
            ),
            (None, None, "", "mock_company_email", "mock_unique_corp_id", False),
            (
                datetime.date(2022, 1, 1),
                "mock_first_name",
                None,
                "mock_company_email",
                "mock_unique_corp_id",
                False,
            ),
            (
                None,
                "mock_first_name",
                None,
                "mock_company_email",
                "mock_unique_corp_id",
                False,
            ),
            (
                datetime.date(2022, 1, 1),
                "",
                None,
                "mock_company_email",
                "mock_unique_corp_id",
                False,
            ),
            (None, "", None, "mock_company_email", "mock_unique_corp_id", False),
            (
                datetime.date(2022, 1, 1),
                None,
                None,
                "mock_company_email",
                "mock_unique_corp_id",
                False,
            ),
            (None, None, None, "mock_company_email", "mock_unique_corp_id", False),
            (
                datetime.date(2022, 1, 1),
                "mock_first_name",
                "mock_last_name",
                "",
                "mock_unique_corp_id",
                True,
            ),
            (
                None,
                "mock_first_name",
                "mock_last_name",
                "",
                "mock_unique_corp_id",
                False,
            ),
            (
                datetime.date(2022, 1, 1),
                "",
                "mock_last_name",
                "",
                "mock_unique_corp_id",
                False,
            ),
            (None, "", "mock_last_name", "", "mock_unique_corp_id", False),
            (
                datetime.date(2022, 1, 1),
                None,
                "mock_last_name",
                "",
                "mock_unique_corp_id",
                False,
            ),
            (None, None, "mock_last_name", "", "mock_unique_corp_id", False),
            (
                datetime.date(2022, 1, 1),
                "mock_first_name",
                "",
                "",
                "mock_unique_corp_id",
                False,
            ),
            (None, "mock_first_name", "", "", "mock_unique_corp_id", False),
            (datetime.date(2022, 1, 1), "", "", "", "mock_unique_corp_id", False),
            (None, "", "", "", "mock_unique_corp_id", False),
            (datetime.date(2022, 1, 1), None, "", "", "mock_unique_corp_id", False),
            (None, None, "", "", "mock_unique_corp_id", False),
            (
                datetime.date(2022, 1, 1),
                "mock_first_name",
                None,
                "",
                "mock_unique_corp_id",
                False,
            ),
            (None, "mock_first_name", None, "", "mock_unique_corp_id", False),
            (datetime.date(2022, 1, 1), "", None, "", "mock_unique_corp_id", False),
            (None, "", None, "", "mock_unique_corp_id", False),
            (datetime.date(2022, 1, 1), None, None, "", "mock_unique_corp_id", False),
            (None, None, None, "", "mock_unique_corp_id", False),
            (
                datetime.date(2022, 1, 1),
                "mock_first_name",
                "mock_last_name",
                None,
                "mock_unique_corp_id",
                True,
            ),
            (
                None,
                "mock_first_name",
                "mock_last_name",
                None,
                "mock_unique_corp_id",
                False,
            ),
            (
                datetime.date(2022, 1, 1),
                "",
                "mock_last_name",
                None,
                "mock_unique_corp_id",
                False,
            ),
            (None, "", "mock_last_name", None, "mock_unique_corp_id", False),
            (
                datetime.date(2022, 1, 1),
                None,
                "mock_last_name",
                None,
                "mock_unique_corp_id",
                False,
            ),
            (None, None, "mock_last_name", None, "mock_unique_corp_id", False),
            (
                datetime.date(2022, 1, 1),
                "mock_first_name",
                "",
                None,
                "mock_unique_corp_id",
                False,
            ),
            (None, "mock_first_name", "", None, "mock_unique_corp_id", False),
            (datetime.date(2022, 1, 1), "", "", None, "mock_unique_corp_id", False),
            (None, "", "", None, "mock_unique_corp_id", False),
            (datetime.date(2022, 1, 1), None, "", None, "mock_unique_corp_id", False),
            (None, None, "", None, "mock_unique_corp_id", False),
            (
                datetime.date(2022, 1, 1),
                "mock_first_name",
                None,
                None,
                "mock_unique_corp_id",
                False,
            ),
            (None, "mock_first_name", None, None, "mock_unique_corp_id", False),
            (datetime.date(2022, 1, 1), "", None, None, "mock_unique_corp_id", False),
            (None, "", None, None, "mock_unique_corp_id", False),
            (datetime.date(2022, 1, 1), None, None, None, "mock_unique_corp_id", False),
            (None, None, None, None, "mock_unique_corp_id", False),
            (
                datetime.date(2022, 1, 1),
                "mock_first_name",
                "mock_last_name",
                "mock_company_email",
                "",
                True,
            ),
            (
                None,
                "mock_first_name",
                "mock_last_name",
                "mock_company_email",
                "",
                False,
            ),
            (
                datetime.date(2022, 1, 1),
                "",
                "mock_last_name",
                "mock_company_email",
                "",
                False,
            ),
            (None, "", "mock_last_name", "mock_company_email", "", False),
            (
                datetime.date(2022, 1, 1),
                None,
                "mock_last_name",
                "mock_company_email",
                "",
                False,
            ),
            (None, None, "mock_last_name", "mock_company_email", "", False),
            (
                datetime.date(2022, 1, 1),
                "mock_first_name",
                "",
                "mock_company_email",
                "",
                False,
            ),
            (None, "mock_first_name", "", "mock_company_email", "", False),
            (datetime.date(2022, 1, 1), "", "", "mock_company_email", "", False),
            (None, "", "", "mock_company_email", "", False),
            (datetime.date(2022, 1, 1), None, "", "mock_company_email", "", False),
            (None, None, "", "mock_company_email", "", False),
            (
                datetime.date(2022, 1, 1),
                "mock_first_name",
                None,
                "mock_company_email",
                "",
                False,
            ),
            (None, "mock_first_name", None, "mock_company_email", "", False),
            (datetime.date(2022, 1, 1), "", None, "mock_company_email", "", False),
            (None, "", None, "mock_company_email", "", False),
            (datetime.date(2022, 1, 1), None, None, "mock_company_email", "", False),
            (None, None, None, "mock_company_email", "", False),
            (
                datetime.date(2022, 1, 1),
                "mock_first_name",
                "mock_last_name",
                "",
                "",
                False,
            ),
            (None, "mock_first_name", "mock_last_name", "", "", False),
            (datetime.date(2022, 1, 1), "", "mock_last_name", "", "", False),
            (None, "", "mock_last_name", "", "", False),
            (datetime.date(2022, 1, 1), None, "mock_last_name", "", "", False),
            (None, None, "mock_last_name", "", "", False),
            (datetime.date(2022, 1, 1), "mock_first_name", "", "", "", False),
            (None, "mock_first_name", "", "", "", False),
            (datetime.date(2022, 1, 1), "", "", "", "", False),
            (None, "", "", "", "", False),
            (datetime.date(2022, 1, 1), None, "", "", "", False),
            (None, None, "", "", "", False),
            (datetime.date(2022, 1, 1), "mock_first_name", None, "", "", False),
            (None, "mock_first_name", None, "", "", False),
            (datetime.date(2022, 1, 1), "", None, "", "", False),
            (None, "", None, "", "", False),
            (datetime.date(2022, 1, 1), None, None, "", "", False),
            (None, None, None, "", "", False),
            (
                datetime.date(2022, 1, 1),
                "mock_first_name",
                "mock_last_name",
                None,
                "",
                False,
            ),
            (None, "mock_first_name", "mock_last_name", None, "", False),
            (datetime.date(2022, 1, 1), "", "mock_last_name", None, "", False),
            (None, "", "mock_last_name", None, "", False),
            (datetime.date(2022, 1, 1), None, "mock_last_name", None, "", False),
            (None, None, "mock_last_name", None, "", False),
            (datetime.date(2022, 1, 1), "mock_first_name", "", None, "", False),
            (None, "mock_first_name", "", None, "", False),
            (datetime.date(2022, 1, 1), "", "", None, "", False),
            (None, "", "", None, "", False),
            (datetime.date(2022, 1, 1), None, "", None, "", False),
            (None, None, "", None, "", False),
            (datetime.date(2022, 1, 1), "mock_first_name", None, None, "", False),
            (None, "mock_first_name", None, None, "", False),
            (datetime.date(2022, 1, 1), "", None, None, "", False),
            (None, "", None, None, "", False),
            (datetime.date(2022, 1, 1), None, None, None, "", False),
            (None, None, None, None, "", False),
            (
                datetime.date(2022, 1, 1),
                "mock_first_name",
                "mock_last_name",
                "mock_company_email",
                None,
                True,
            ),
            (
                None,
                "mock_first_name",
                "mock_last_name",
                "mock_company_email",
                None,
                False,
            ),
            (
                datetime.date(2022, 1, 1),
                "",
                "mock_last_name",
                "mock_company_email",
                None,
                False,
            ),
            (None, "", "mock_last_name", "mock_company_email", None, False),
            (
                datetime.date(2022, 1, 1),
                None,
                "mock_last_name",
                "mock_company_email",
                None,
                False,
            ),
            (None, None, "mock_last_name", "mock_company_email", None, False),
            (
                datetime.date(2022, 1, 1),
                "mock_first_name",
                "",
                "mock_company_email",
                None,
                False,
            ),
            (None, "mock_first_name", "", "mock_company_email", None, False),
            (datetime.date(2022, 1, 1), "", "", "mock_company_email", None, False),
            (None, "", "", "mock_company_email", None, False),
            (datetime.date(2022, 1, 1), None, "", "mock_company_email", None, False),
            (None, None, "", "mock_company_email", None, False),
            (
                datetime.date(2022, 1, 1),
                "mock_first_name",
                None,
                "mock_company_email",
                None,
                False,
            ),
            (None, "mock_first_name", None, "mock_company_email", None, False),
            (datetime.date(2022, 1, 1), "", None, "mock_company_email", None, False),
            (None, "", None, "mock_company_email", None, False),
            (datetime.date(2022, 1, 1), None, None, "mock_company_email", None, False),
            (None, None, None, "mock_company_email", None, False),
            (
                datetime.date(2022, 1, 1),
                "mock_first_name",
                "mock_last_name",
                "",
                None,
                False,
            ),
            (None, "mock_first_name", "mock_last_name", "", None, False),
            (datetime.date(2022, 1, 1), "", "mock_last_name", "", None, False),
            (None, "", "mock_last_name", "", None, False),
            (datetime.date(2022, 1, 1), None, "mock_last_name", "", None, False),
            (None, None, "mock_last_name", "", None, False),
            (datetime.date(2022, 1, 1), "mock_first_name", "", "", None, False),
            (None, "mock_first_name", "", "", None, False),
            (datetime.date(2022, 1, 1), "", "", "", None, False),
            (None, "", "", "", None, False),
            (datetime.date(2022, 1, 1), None, "", "", None, False),
            (None, None, "", "", None, False),
            (datetime.date(2022, 1, 1), "mock_first_name", None, "", None, False),
            (None, "mock_first_name", None, "", None, False),
            (datetime.date(2022, 1, 1), "", None, "", None, False),
            (None, "", None, "", None, False),
            (datetime.date(2022, 1, 1), None, None, "", None, False),
            (None, None, None, "", None, False),
            (
                datetime.date(2022, 1, 1),
                "mock_first_name",
                "mock_last_name",
                None,
                None,
                False,
            ),
            (None, "mock_first_name", "mock_last_name", None, None, False),
            (datetime.date(2022, 1, 1), "", "mock_last_name", None, None, False),
            (None, "", "mock_last_name", None, None, False),
            (datetime.date(2022, 1, 1), None, "mock_last_name", None, None, False),
            (None, None, "mock_last_name", None, None, False),
            (datetime.date(2022, 1, 1), "mock_first_name", "", None, None, False),
            (None, "mock_first_name", "", None, None, False),
            (datetime.date(2022, 1, 1), "", "", None, None, False),
            (None, "", "", None, None, False),
            (datetime.date(2022, 1, 1), None, "", None, None, False),
            (None, None, "", None, None, False),
            (datetime.date(2022, 1, 1), "mock_first_name", None, None, None, False),
            (None, "mock_first_name", None, None, None, False),
            (datetime.date(2022, 1, 1), "", None, None, None, False),
            (None, "", None, None, None, False),
            (datetime.date(2022, 1, 1), None, None, None, None, False),
            (None, None, None, None, None, False),
        ],
    )
    def test_has_necessary_params_for_overeligibility(
        self,
        date_of_birth,
        first_name,
        last_name,
        company_email,
        unique_corp_id,
        expected,
    ):
        # Given
        params = VerificationParams(
            user_id=1,
            date_of_birth=date_of_birth,
            first_name=first_name,
            last_name=last_name,
            company_email=company_email,
            unique_corp_id=unique_corp_id,
        )
        assert params.has_necessary_params_for_overeligibility() == expected

    @pytest.mark.parametrize(
        "has_necessary_alternate_params,has_necessary_standard_params,expected",
        [
            (True, True, True),
            (False, True, True),
            (True, False, True),
            (False, False, False),
        ],
    )
    def test_has_necessary_multistep_params(
        self, has_necessary_alternate_params, has_necessary_standard_params, expected
    ):
        # Given
        with mock.patch(
            "eligibility.utils.verification_utils.VerificationParams.has_necessary_alternate_params",
            return_value=has_necessary_alternate_params,
        ), mock.patch(
            "eligibility.utils.verification_utils.VerificationParams.has_necessary_standard_params",
            return_value=has_necessary_standard_params,
        ):
            params = VerificationParams(user_id=1)
            assert params.has_necessary_multistep_params() == expected

    @pytest.mark.parametrize(
        "unique_corp_id,date_of_birth,dependent_date_of_birth,first_name,last_name,employee_first_name,employee_last_name,expected",
        [
            ("", None, None, "", "", "", "", False),
            ("1", datetime.date(2022, 1, 1), None, "", "", "", "", True),
            ("1", None, datetime.date(2022, 1, 1), "", "", "", "", True),
            ("1", None, None, "first", "last", "", "", True),
            ("1", None, None, "", "", "emp-first", "emp-last", True),
            ("", datetime.date(2022, 1, 1), None, "", "", "", "", False),
            ("", None, datetime.date(2022, 1, 1), "", "", "", "", False),
            ("", None, None, "first", "last", "", "", False),
            ("", None, None, "", "", "emp-first", "emp-last", False),
        ],
    )
    def test_has_necessary_healthplan_params(
        self,
        unique_corp_id,
        date_of_birth,
        dependent_date_of_birth,
        first_name,
        last_name,
        employee_first_name,
        employee_last_name,
        expected,
    ):
        params = VerificationParams(
            user_id=1,
            unique_corp_id=unique_corp_id,
            date_of_birth=date_of_birth,
            dependent_date_of_birth=dependent_date_of_birth,
            first_name=first_name,
            last_name=last_name,
            employee_first_name=employee_first_name,
            employee_last_name=employee_last_name,
        )
        assert params.has_necessary_healthplan_params() == expected

    @pytest.mark.parametrize(
        "company_email,date_of_birth,first_name,last_name,employee_first_name,employee_last_name,work_state,dependent_date_of_birth,expected",
        [
            ("", None, "", "", "", "", "", None, False),
            ("email.com", datetime.date(2022, 1, 1), "", "", "", "", "", None, True),
            ("email.com", None, "first", "last", "", "", "", None, True),
            ("email.com", None, "", "", "emp-first", "emp-last", "", None, True),
            ("", datetime.date(2022, 1, 1), "first", "last", "", "", "CA", None, True),
            ("email.com", None, "", "", "", "", "", datetime.date(2022, 1, 1), True),
            ("email.com", None, "first", "", "", "emp-last", "", None, False),
            ("email.com", None, "", "", "", "", "", None, False),
            ("", datetime.date(2022, 1, 1), "", "", "", "", "", None, False),
            ("email.com", None, "", "last", "", "", "", None, False),
            ("email.com", None, "", "", "", "emp-last", "", None, False),
            ("", datetime.date(2022, 1, 1), "first", "last", "", "", "", None, False),
            ("", None, "", "", "", "", "", datetime.date(2022, 1, 1), False),
        ],
    )
    def test_has_necessary_employer_params(
        self,
        company_email,
        date_of_birth,
        first_name,
        last_name,
        employee_first_name,
        employee_last_name,
        work_state,
        dependent_date_of_birth,
        expected,
    ):
        params = VerificationParams(
            user_id=1,
            company_email=company_email,
            date_of_birth=date_of_birth,
            first_name=first_name,
            last_name=last_name,
            employee_first_name=employee_first_name,
            employee_last_name=employee_last_name,
            work_state=work_state,
            dependent_date_of_birth=dependent_date_of_birth,
        )
        assert params.has_necessary_employer_params() == expected


"""
def has_necessary_employer_params(self) -> bool:
        return (
            all((self.company_email, self.date_of_birth))
            or all((self.first_name, self.last_name, self.company_email))
            or all(
                (self.employee_first_name, self.employee_last_name, self.company_email)
            )
            or all(
                (self.first_name, self.last_name, self.date_of_birth, self.work_state)
            )
            or all((self.company_email, self.dependent_date_of_birth))
        )

"""
