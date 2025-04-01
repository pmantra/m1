from __future__ import annotations

import uuid
from datetime import datetime
from unittest import mock

import factory
from factory import alchemy
from onelogin.saml2 import auth

from authn.domain import model
from authn.models import sso
from authn.services.integrations import saml
from pytests import factories


class OneLoginAuthFactory(factory.Factory):
    class Meta:
        model = mock.MagicMock(spec=auth.OneLogin_Saml2_Auth)


class SAMLAssertionFactory(factory.Factory):
    class Meta:
        model = saml.SAMLAssertion

    idp = factory.Faker("uri")
    issuer = factory.Faker("swift11")
    subject = factory.Faker("swift11")
    email = factory.Faker("email")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    employee_id = factory.Faker("swift11")
    rewards_id = factory.Faker("swift11")
    organization_external_id = factory.Faker("swift11")


class SAMLRequestBodyFactory(factory.Factory):
    class Meta:
        model = saml.SAMLRequestBody

    https = factory.Faker("random_element", elements=["on", "off"])
    http_host = factory.Faker("hostname")
    server_port = None
    script_name = factory.Faker("swift11")
    get_data = factory.SubFactory(factory.DictFactory)
    post_data = factory.SubFactory(factory.DictFactory)


class LegacyExternalIdentityFactory(alchemy.SQLAlchemyModelFactory):
    class Meta(factories.BaseMeta):
        model = sso.ExternalIdentity

    idp = factory.Faker("uri")
    external_user_id = factory.Faker("swift11")
    rewards_id = factory.Faker("swift11")
    unique_corp_id = factory.Faker("swift11")
    user = factory.SubFactory(factories.DefaultUserFactory)
    organization = factory.SubFactory(factories.OrganizationFactory)


class UserFactory(factory.Factory):
    class Meta:
        model = model.User

    email = factory.Faker("email")
    password = factory.Faker("swift11")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    id = None
    email_confirmed = False
    active = False
    created_at = None
    modified_at = None


class UserMigrationFactory(factory.Factory):
    class Meta:
        model = model.UserMigration

    id = 1
    esp_id = str(uuid.uuid4())
    email = factory.Faker("email")
    username = factory.Faker("email")
    first_name = factory.Faker("first_name")
    middle_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    active = False
    email_confirmed = False
    password = factory.Faker("swift11")
    image_id = None
    zendesk_user_id = 1234
    mfa_state = "DISABLED"
    sms_phone_number = factory.Faker("cellphone_number_e_164")
    created_at = datetime.utcnow()
    modified_at = datetime.utcnow()


class UserAuthFactory(factory.Factory):
    class Meta:
        model = model.UserAuth

    id = None
    user_id = factory.Sequence(lambda n: n + 1)
    refresh_token = factory.Faker("swift11")
    external_id = factory.Faker("swift11")


class UserMFAFactory(factory.Factory):
    class Meta:
        model = model.UserMFA

    user_id = factory.Sequence(lambda n: n + 1)
    sms_phone_number = factory.Faker("cellphone_number_e_164")
    otp_secret = factory.Faker("swift11")
    external_user_id = factory.Sequence(lambda n: n + 1)
    verified = False
    created_at = None
    modified_at = None


class UserMetadataFactory(factory.Factory):
    class Meta:
        model = model.UserMetadata

    user_id = factory.Sequence(lambda n: n + 1)
    zendesk_user_id = factory.Sequence(lambda n: n + 1)
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    timezone = factory.Faker("timezone")
    middle_name = factory.Faker("first_name")
    image_id = None
    created_at = None
    modified_at = None


class UserExternalIdentityFactory(factory.Factory):
    class Meta:
        model = model.UserExternalIdentity

    external_user_id = factory.Faker("swift11")
    reporting_id = factory.Faker("swift11")
    user_id = factory.Sequence(lambda n: n + 1)
    unique_corp_id = factory.Faker("swift11")
    identity_provider_id = factory.Sequence(lambda n: n + 1)
    external_organization_id = factory.Faker("swift11")
    id = None
    sso_email = None
    auth0_user_id = None
    sso_user_first_name = None
    sso_user_last_name = None


class IdentityProviderFactory(factory.Factory):
    class Meta:
        model = model.IdentityProvider

    name = factory.Faker("domain_name")
    metadata = factory.Faker("bs")


class IdentityProviderFieldAliasFactory(factory.Factory):
    class Meta:
        model = model.IdentityProviderFieldAlias

    field = factory.Faker("domain_name")
    alias = factory.Faker("domain_name")
    identity_provider_id = factory.Sequence(lambda n: n + 1)


class OrganizationAuthFactory(factory.Factory):
    class Meta:
        model = model.OrganizationAuth

    organization_id = factory.Sequence(lambda n: n + 1)
    id = None
    mfa_required = False
