from unittest.mock import MagicMock, patch

from authn.models.user import User
from common.services.stripe import StripeClient, StripeConnectClient
from models.common import PrivilegeType
from services.common import calculate_privilege_type


def test_calculate_privilege_type_for_coaching_provider():
    """
    n.b.: Only medical providers can have anonymous appointments.
    """
    practitioner = MagicMock(autospec=User)

    member = MagicMock(autospec=User)
    member.member_profile.is_international = False
    member.organization.education_only = False

    with patch(
        "providers.service.provider.ProviderService.in_certified_states",
        return_value=False,
    ):
        with patch(
            "providers.service.provider.ProviderService.is_medical_provider",
            return_value=False,
        ):
            _type = calculate_privilege_type(practitioner, member)

    assert _type == PrivilegeType.STANDARD.value


def test_calculate_privilege_type_medical_provider():
    practitioner = MagicMock(autospec=User)

    member = MagicMock(autospec=User)
    member.member_profile.is_international = False
    member.organization.education_only = False

    with patch(
        "providers.service.provider.ProviderService.in_certified_states",
        return_value=False,
    ):
        with patch(
            "providers.service.provider.ProviderService.is_medical_provider",
            return_value=True,
        ):
            _type = calculate_privilege_type(practitioner, member)

    assert _type == PrivilegeType.ANONYMOUS.value


def test_calculate_privilege_type_education_only():
    practitioner = MagicMock(autospec=User)

    member = MagicMock(autospec=User)
    member.organization.education_only = True
    member.member_profile.is_international = False

    with patch(
        "providers.service.provider.ProviderService.in_certified_states",
        return_value=True,
    ):
        with patch(
            "providers.service.provider.ProviderService.is_medical_provider",
            return_value=True,
        ):
            _type = calculate_privilege_type(practitioner, member)

    assert _type == PrivilegeType.EDUCATION_ONLY.value


def test_calculate_privilege_type_international():
    practitioner = MagicMock(autospec=User)

    member = MagicMock(autospec=User)
    member.organization.education_only = False
    member.member_profile.is_international = True

    with patch(
        "providers.service.provider.ProviderService.in_certified_states",
        return_value=True,
    ):
        with patch(
            "providers.service.provider.ProviderService.is_medical_provider",
            return_value=True,
        ):
            _type = calculate_privilege_type(practitioner, member)

    assert _type == PrivilegeType.INTERNATIONAL.value


def test_calculate_privilege_type_standard():
    practitioner = MagicMock(autospec=User)

    member = MagicMock(autospec=User)
    member.organization.education_only = False
    member.member_profile.is_international = False

    with patch(
        "providers.service.provider.ProviderService.in_certified_states",
        return_value=True,
    ):
        with patch(
            "providers.service.provider.ProviderService.is_medical_provider",
            return_value=True,
        ):
            _type = calculate_privilege_type(practitioner, member)

    assert _type == PrivilegeType.STANDARD.value


def test_stripe_connect_client_no_user():
    client = MagicMock(autospec=StripeClient)
    connect_client = StripeConnectClient(client)

    # When called directly, get_connect_account_for_user(None) triggers a type error
    # To solve, we'll wrap in a function to mimic how this is allowed in the code
    # e.g. api/common/services/stripe.py, line 267
    test_func = lambda user: connect_client.get_connect_account_for_user(user)
    account = test_func(None)

    assert account is None
