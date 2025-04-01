import datetime
from unittest import mock

import pytest
from requests import Response

from eligibility.e9y import model as e9y_model


@pytest.fixture
def marketplace_user(factories):
    return factories.MemberFactory.create()


def test_invalid_does_not_exist_referral_code(client, api_helpers, marketplace_user):
    res: Response = client.post(
        "api/v1/referral_code_uses",
        headers=api_helpers.json_headers(user=marketplace_user),
        json={"referral_code": "DAJ38"},
    )

    assert res.json == {
        "errors": [
            {
                "detail": "Referral code does not exist!",
                "status": 422,
                "title": "Unprocessable Entity",
            }
        ],
        "message": "Referral code does not exist!",
    }
    assert res.status_code == 422


def test_invalid_code_referral_code(client, api_helpers, marketplace_user, factories):
    code_obj = factories.ReferralCodeFactory.create(
        expires_at=datetime.datetime.now()  # noqa: needs to be now without timezone for comparison purposes
        - datetime.timedelta(weeks=42)
    )
    res: Response = client.post(
        "api/v1/referral_code_uses",
        headers=api_helpers.json_headers(user=marketplace_user),
        json={"referral_code": code_obj.code},
    )

    assert res.json == {
        "errors": [
            {
                "detail": "Referral code is invalid: Contact support@mavenclinic.com for help "
                "and give the reference: invalid_code",
                "status": 422,
                "title": "Unprocessable Entity",
            }
        ],
        "message": "Referral code is invalid: Contact support@mavenclinic.com for help "
        "and give the reference: invalid_code",
    }
    assert res.status_code == 422


def test_add_credit_for_marketplace_user(factories):
    code_obj = factories.ReferralCodeFactory.create(
        expires_at=datetime.datetime.now()  # noqa: needs to be now without timezone for comparison purposes
        - datetime.timedelta(weeks=42)
    )
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_all_verifications_for_user",
        return_value=[],
    ):
        credit = code_obj.add_credit(
            amount=0.01, user_id=123456, expires_at=datetime.datetime.utcnow()
        )
        assert credit.eligibility_verification_id is None
        assert credit.eligibility_member_id is None
        assert credit.eligibility_member_2_id is None
        assert credit.eligibility_verification_2_id is None
        assert credit.eligibility_member_2_version is None


def test_add_credit_for_enterprise_user(factories):
    code_obj = factories.ReferralCodeFactory.create(
        expires_at=datetime.datetime.now()  # noqa: needs to be now without timezone for comparison purposes
        - datetime.timedelta(weeks=42)
    )
    user_id = 123456
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_all_verifications_for_user",
        return_value=[
            e9y_model.EligibilityVerification(
                user_id=user_id,
                organization_id=1,
                unique_corp_id="mocked",
                dependent_id="mocked",
                first_name="mockded",
                last_name="mockded",
                date_of_birth=datetime.date.today(),
                email="mockded",
                record={},
                verified_at=datetime.datetime.utcnow(),
                created_at=datetime.datetime.utcnow(),
                verification_type="mocked",
                is_active=True,
                verification_id=1,
                eligibility_member_id=2,
                verification_2_id=3,
                eligibility_member_2_id=4,
                eligibility_member_2_version=5,
            )
        ],
    ):
        credit = code_obj.add_credit(
            amount=0.01, user_id=user_id, expires_at=datetime.datetime.utcnow()
        )
        assert credit.eligibility_verification_id == 1
        assert credit.eligibility_member_id == 2
        assert credit.eligibility_member_2_id == 4
        assert credit.eligibility_verification_2_id == 3
        assert credit.eligibility_member_2_version == 5
