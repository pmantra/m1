from unittest import mock

import pytest

from authn.domain.service import mfa
from authn.domain.service.mfa import MFA_REQUIRED_TYPE_TO_REASON_MAP, MFARequireType
from authn.models.user import MFAState
from authn.pytests import factories
from authn.services.integrations import twilio
from pytests.factories import PractitionerProfileFactory, PractitionerUserFactory


class TestTokenVerification:
    @staticmethod
    def test_verify_token_succeeds(mfa_service, mock_twilio, faker):
        # Given
        token = faker.swift11()
        user = factories.UserFactory.create()
        mfa = factories.UserMFAFactory.create(user_id=user.id)
        mfa_service.repo.get.return_value = mfa
        mock_twilio.verify_otp.return_value = True
        # When
        enablement = mfa_service.verify_token(user=user, token=token)
        # Then
        assert enablement == mfa

    @staticmethod
    def test_verify_token_not_configured(mfa_service, faker):
        # Given
        token = faker.swift11()
        user = factories.UserFactory.create()
        mfa_service.repo.get.return_value = None
        # When/Then
        with pytest.raises(mfa.UserMFAConfigurationError):
            mfa_service.verify_token(user=user, token=token)

    @staticmethod
    def test_verify_token_verification_fails(mfa_service, mock_twilio, faker):
        # Given
        token = faker.swift11()
        user = factories.UserFactory.create()
        enablement = factories.UserMFAFactory.create(user_id=user.id)
        mfa_service.repo.get.return_value = enablement
        mock_twilio.verify_otp.return_value = False
        # When/Then
        with pytest.raises(mfa.UserMFAVerificationError):
            mfa_service.verify_token(user=user, token=token)


class TestSendChallenge:
    @staticmethod
    def test_send_challenge_succeeds(mfa_service, mock_twilio):
        # Given
        mock_twilio.request_otp_via_sms.return_value = True
        # When
        sent = mfa_service.send_challenge(sms_phone_number=1)
        # Then
        assert sent is True

    @staticmethod
    def test_send_challenge_fails(mfa_service, mock_twilio):
        # Given
        mock_twilio.request_otp_via_sms.return_value = False
        # When/Then
        with pytest.raises(mfa.UserMFAIntegrationError):
            mfa_service.send_challenge(sms_phone_number=1)


class TestMFABeginDisable:
    @staticmethod
    def test_begin_disable(mfa_service, mock_twilio):
        # Given
        user = factories.UserFactory.create()
        enablement = factories.UserMFAFactory.create(user_id=user.id)
        mfa_service.repo.get.return_value = enablement
        mfa_service.repo.update.return_value = enablement
        mock_twilio.request_otp_via_sms.return_value = True
        # When
        disabled = mfa_service.begin_disable(user=user)
        # Then
        assert disabled.verified is False

    @staticmethod
    def test_begin_disable_no_configuration(mfa_service):
        # Given
        user = factories.UserFactory.create()
        mfa_service.repo.get.return_value = None
        # When/Then
        assert mfa_service.begin_disable(user=user) is None


class TestMFABeginEnable:
    @staticmethod
    def test_already_verified_match_existing_phone(mfa_service):
        # Given
        user = factories.UserFactory.create()
        enablement = factories.UserMFAFactory.create(user_id=user.id, verified=True)
        mfa_service.repo.get.return_value = enablement
        # When
        result = mfa_service.begin_enable(
            user=user, sms_phone_number=enablement.sms_phone_number
        )
        # Then
        assert result == enablement

    @staticmethod
    def test_already_verified_match_existing_phone_but_require_resend(
        mfa_service, mock_twilio
    ):
        # Given
        user = factories.UserFactory.create()
        enablement = factories.UserMFAFactory.create(user_id=user.id, verified=True)
        mfa_service.repo.get.return_value = enablement
        # When
        result = mfa_service.begin_enable(
            user=user, sms_phone_number=enablement.sms_phone_number, require_resend=True
        )
        # Then
        assert result == enablement
        assert mock_twilio.request_otp_via_sms.called

    @staticmethod
    def test_not_verified_match_existing_phone(mfa_service, mock_twilio):
        # Given
        user = factories.UserFactory.create()
        enablement = factories.UserMFAFactory.create(user_id=user.id, verified=False)
        mfa_service.repo.get.return_value = enablement
        mock_twilio.request_otp_via_sms.return_value = True
        # When
        result = mfa_service.begin_enable(
            user=user, sms_phone_number=enablement.sms_phone_number
        )
        # Then
        assert result == enablement
        assert mock_twilio.request_otp_via_sms.called

    @staticmethod
    def test_already_verified_different_existing_phone(mfa_service, mock_twilio, faker):
        # Given
        new_phone = faker.cellphone_number_with_country_code()
        _, new_phone_normalized = mfa_service.normalize_phone(new_phone)
        user = factories.UserFactory.create(id=1)
        existing_mfa = factories.UserMFAFactory.create(user_id=user.id, verified=True)
        mfa_service.repo.get.return_value = existing_mfa
        # When
        result = mfa_service.begin_enable(user=user, sms_phone_number=new_phone)
        # Then
        assert (
            result.user_id,
            result.sms_phone_number,
        ) == (user.id, new_phone_normalized)
        assert mock_twilio.request_otp_via_sms.called

    @staticmethod
    def test_not_verified_different_existing_phone(mfa_service, mock_twilio, faker):
        # Given
        new_phone = faker.cellphone_number_with_country_code()
        _, new_phone_normalized = mfa_service.normalize_phone(new_phone)
        user = factories.UserFactory.create()
        existing_mfa = factories.UserMFAFactory.create(user_id=user.id, verified=True)
        mfa_service.repo.get.return_value = existing_mfa
        # When
        result = mfa_service.begin_enable(user=user, sms_phone_number=new_phone)
        # Then
        assert (
            result.user_id,
            result.sms_phone_number,
        ) == (user.id, new_phone_normalized)
        assert mock_twilio.request_otp_via_sms.called

    @staticmethod
    def test_different_existing_phone_twilio_error(mfa_service, mock_twilio, faker):
        # Given
        new_phone = faker.cellphone_number_with_country_code()
        _, new_phone_normalized = mfa_service.normalize_phone(new_phone)
        user = factories.UserFactory.create()
        existing_mfa = factories.UserMFAFactory.create(user_id=user.id, verified=True)
        new_mfa = factories.UserMFAFactory.create(
            user_id=user.id, sms_phone_number=new_phone
        )
        mfa_service.repo.get.return_value = existing_mfa
        mfa_service.repo.create.return_value = new_mfa
        mock_twilio.side_effect = twilio.TwilioApiException
        # When
        result = mfa_service.begin_enable(user=user, sms_phone_number=new_phone)
        # Then
        assert (
            result.user_id,
            result.sms_phone_number,
        ) == (user.id, new_phone_normalized)
        assert mock_twilio.request_otp_via_sms.called

    @staticmethod
    def test_new_phone(mfa_service, mock_twilio, faker):
        # Given
        new_phone = faker.cellphone_number_with_country_code()
        _, new_phone_normalized = mfa_service.normalize_phone(new_phone)
        user = factories.UserFactory.create()
        mfa_service.repo.get.return_value = None
        new_mfa = factories.UserMFAFactory.create(
            user_id=user.id, sms_phone_number=new_phone
        )
        mfa_service.repo.create.return_value = new_mfa
        # When
        result = mfa_service.begin_enable(user=user, sms_phone_number=new_phone)
        # Then
        assert (
            result.user_id,
            result.sms_phone_number,
        ) == (user.id, new_phone_normalized)
        assert mock_twilio.request_otp_via_sms.called

    @staticmethod
    def test_new_phone_no_country_code(mfa_service, mock_twilio, faker):
        # Given
        new_phone = faker.cellphone_number()
        _, new_phone_normalized = mfa_service.normalize_phone(new_phone)
        user = factories.UserFactory.create()
        mfa_service.repo.get.return_value = None
        new_mfa = factories.UserMFAFactory.create(
            user_id=user.id, sms_phone_number=new_phone
        )
        mfa_service.repo.create.return_value = new_mfa
        # When
        result = mfa_service.begin_enable(user=user, sms_phone_number=new_phone)
        # Then
        assert (
            result.user_id,
            result.sms_phone_number,
        ) == (user.id, new_phone_normalized)
        assert mock_twilio.request_otp_via_sms.called


class TestProcessChallengeResponse:
    @staticmethod
    def test_finish_disable(mfa_service, faker, mock_twilio):
        # Given
        token = faker.swift11()
        user = factories.UserFactory.create()
        enablement = factories.UserMFAFactory.create(user_id=user.id)
        mfa_service.repo.get.return_value = enablement
        mfa_service.repo.update.return_value = enablement
        mock_twilio.verify_otp.return_value = True
        expected_delete_call = mock.call(id=user.id)
        # When
        mfa_service.process_challenge_response(
            user=user,
            action=mfa.mfa.VerificationRequiredActions.DISABLE_MFA,
            token=token,
        )
        # Then
        assert mfa_service.repo.delete.call_args == expected_delete_call

    @staticmethod
    def test_finish_enable(mfa_service, faker, mock_twilio):
        # Given
        token = faker.swift11()
        user = factories.UserFactory.create()
        enablement = factories.UserMFAFactory.create(user_id=user.id)
        mfa_service.repo.get.return_value = enablement
        mfa_service.repo.update.return_value = enablement
        mock_twilio.verify_otp.return_value = True
        # When
        processed = mfa_service.process_challenge_response(
            user=user,
            action=mfa.mfa.VerificationRequiredActions.ENABLE_MFA,
            token=token,
        )
        # Then
        assert processed.verified

    @staticmethod
    def test_login(mfa_service, faker, mock_twilio):
        # Given
        token = faker.swift11()
        user = factories.UserFactory.create()
        enablement = factories.UserMFAFactory.create(user_id=user.id)
        mfa_service.repo.get.return_value = enablement
        mock_twilio.verify_otp.return_value = True
        # When
        processed = mfa_service.process_challenge_response(
            user=user,
            action=mfa.mfa.VerificationRequiredActions.LOGIN,
            token=token,
        )
        # Then
        assert processed == enablement


class TestCheckUserMFAState:
    @staticmethod
    def test_user_not_require_mfa(
        mfa_service,
        mock_mfa_service_is_mfa_required_for_user_profile,
        mock_mfa_service_is_mfa_required_for_org,
        mock_mfa_service_get_org_id_by_user_id,
    ):
        # Given
        user = factories.UserFactory.create()
        user_mfa = factories.UserMFAFactory.create(
            user_id=user.id, mfa_state=MFAState.DISABLED
        )
        mfa_service.repo.get.return_value = user_mfa
        mock_mfa_service_get_org_id_by_user_id.return_value = 1
        mock_mfa_service_is_mfa_required_for_org.return_value = False
        mock_mfa_service_is_mfa_required_for_user_profile.return_value = False

        # When
        mfa_result, reason = mfa_service.get_user_mfa_status(user_id=user.id)
        # Then
        assert mfa_result is False
        assert reason == MFA_REQUIRED_TYPE_TO_REASON_MAP[MFARequireType.NOT_REQUIRED]

    @staticmethod
    def test_user_enabled_mfa(
        mfa_service,
        mock_mfa_service_is_mfa_required_for_user_profile,
        mock_mfa_service_is_mfa_required_for_org,
        mock_mfa_service_get_org_id_by_user_id,
    ):
        # Given
        user = factories.UserFactory.create()
        user_mfa = factories.UserMFAFactory.create(
            user_id=user.id, mfa_state=MFAState.ENABLED
        )
        mfa_service.repo.get.return_value = user_mfa
        mock_mfa_service_get_org_id_by_user_id.return_value = 1
        mock_mfa_service_is_mfa_required_for_org.return_value = False
        mock_mfa_service_is_mfa_required_for_user_profile.return_value = False

        # When
        mfa_result, reason = mfa_service.get_user_mfa_status(user_id=user.id)
        # Then
        assert mfa_result is True
        assert reason == MFA_REQUIRED_TYPE_TO_REASON_MAP[MFARequireType.USER]

    @staticmethod
    @pytest.mark.skip(
        reason="MFA enforcement for practitioner is on hold because some practitioners don't have MFA enabled"
    )
    def test_mfa_user_is_practitioner(
        mfa_service,
        mock_mfa_service_is_mfa_required_for_user_profile,
        mock_mfa_service_is_mfa_required_for_org,
        mock_mfa_service_get_org_id_by_user_id,
    ):
        # Given
        user = factories.UserFactory.create()
        mock_mfa_service_get_org_id_by_user_id.return_value = 1
        mock_mfa_service_is_mfa_required_for_org.return_value = False
        mock_mfa_service_is_mfa_required_for_user_profile.return_value = True

        # When
        mfa_result, reason = mfa_service.get_user_mfa_status(user_id=user.id)
        # Then
        assert mfa_result is True
        assert reason == MFA_REQUIRED_TYPE_TO_REASON_MAP[MFARequireType.PRACTITIONER]

    @staticmethod
    def test_org_mfa_require(
        mfa_service,
        mock_mfa_service_is_mfa_required_for_org,
        mock_mfa_service_get_org_id_by_user_id,
        mock_idp_management_client,
        mock_user_auth_repository,
    ):
        # Given
        user = factories.UserFactory.create()
        mock_mfa_service_get_org_id_by_user_id.return_value = 1
        mock_mfa_service_is_mfa_required_for_org.return_value = True
        mock_user_auth_repository.get_by_user_id.return_value = (
            factories.UserAuthFactory.create(user_id=user.id, external_id="abc")
        )

        # When
        mfa_result, reason = mfa_service.get_user_mfa_status(user_id=user.id)
        # Then
        assert mfa_result is True
        assert reason == MFA_REQUIRED_TYPE_TO_REASON_MAP[MFARequireType.ORG]
        assert mock_idp_management_client.update_company_enforce_mfa.called

    @staticmethod
    def test_user_enabled_mfa_with_user_mfa_is_none(
        mfa_service,
        mock_mfa_service_is_mfa_required_for_user_profile,
        mock_mfa_service_is_mfa_required_for_org,
        mock_mfa_service_get_org_id_by_user_id,
    ):
        # Given
        user = factories.UserFactory.create()
        mfa_service.repo.get.return_value = None
        mock_mfa_service_get_org_id_by_user_id.return_value = 1
        mock_mfa_service_is_mfa_required_for_org.return_value = False
        mock_mfa_service_is_mfa_required_for_user_profile.return_value = False

        # When
        mfa_result, reason = mfa_service.get_user_mfa_status(user_id=user.id)
        # Then
        assert mfa_result is False
        assert reason == MFA_REQUIRED_TYPE_TO_REASON_MAP[MFARequireType.NOT_REQUIRED]

    @staticmethod
    def test_get_org_id_by_user_id(mfa_service, mock_get_organization_id_for_user):
        # Given
        mock_get_organization_id_for_user.return_value = 1
        # When
        result = mfa_service.get_org_id_by_user_id(user_id=1)
        # Then
        assert result == 1

    @staticmethod
    def test_get_org_id_by_user_id_with_none_from_e9y(
        mfa_service, mock_get_organization_id_for_user
    ):
        # Given
        mock_get_organization_id_for_user.return_value = None
        # When
        result = mfa_service.get_org_id_by_user_id(user_id=1)
        # Then
        assert result is None

    @staticmethod
    def test_get_org_id_by_user_id_with_error_from_e9y(
        mfa_service, mock_get_organization_id_for_user
    ):
        # Given
        mock_get_organization_id_for_user.side_effect = Exception()
        # When
        result = mfa_service.get_org_id_by_user_id(user_id=1)
        # Then
        assert result is None

    @staticmethod
    def test_is_mfa_required_for_org_with_org(mfa_service):
        # Given
        org_auth = factories.OrganizationAuthFactory.create()
        mfa_service.organization_auth.get_by_organization_id.return_value = org_auth
        # When
        result = mfa_service.is_mfa_required_for_org(org_id=1)
        # Then
        assert result is False

    @staticmethod
    def test_is_mfa_required_for_org_with_org_not_found(mfa_service):
        # Given
        mfa_service.organization_auth.get_by_organization_id.return_value = None
        # When
        result = mfa_service.is_mfa_required_for_org(org_id=1)
        # Then
        assert result is False

    @staticmethod
    def test_mfa_required_for_user_is_practitioner(mfa_service):
        # Given
        prac = PractitionerUserFactory()
        PractitionerProfileFactory.create(user=prac)

        # When
        result: bool = mfa_service.is_mfa_required_for_user_profile(user_id=prac.id)
        # Then
        assert result is True

    @staticmethod
    def test_mfa_required_for_user_is_not_practitioner(mfa_service):
        # Given
        user = factories.UserFactory.create()
        # When
        result: bool = mfa_service.is_mfa_required_for_user_profile(user_id=user.id)
        # Then
        assert result is False


class TestMFADataSync:
    @staticmethod
    def test_mfa_data_sync_to_db(mfa_service):
        # Given
        user = factories.UserFactory.create()
        enablement = factories.UserMFAFactory.create(user_id=user.id)
        mfa_service.repo.get.return_value = enablement
        # When
        mfa_service.update_mfa_status_and_sms_phone_number(
            user_id=user.id, sms_phone_number="+11234567890", is_enable=True
        )
        # Then
        result = mfa_service.repo.get(id=user.id)
        assert result.mfa_state is MFAState.ENABLED

    @staticmethod
    def test_mfa_data_sync_to_auth0(
        mfa_service,
        mock_idp_management_client,
        mock_user_auth_repository,
    ):
        # Given
        user = factories.UserFactory.create()
        mock_user_auth_repository.get_by_user_id.return_value = (
            factories.UserAuthFactory.create(user_id=user.id, external_id="abc")
        )

        mfa_service.update_user_company_mfa_to_auth0(
            user_id=user.id, is_company_mfa_required=True
        )
        # Then
        assert mock_idp_management_client.update_company_enforce_mfa.called
        assert mock_idp_management_client.get_user_mfa_sms_phone_number.called
