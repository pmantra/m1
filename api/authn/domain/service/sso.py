from __future__ import annotations

import base64
import dataclasses
import datetime
from typing import Any

import ddtrace
import sqlalchemy.orm.scoping
from maven import feature_flags

from authn.domain import model, repository
from authn.domain.service import authn, user
from authn.services.integrations import idp, saml
from authn.services.integrations.idp.models import IDPIdentity, IDPUser
from authn.util.constants import (
    ERROR_REASON_1_FOR_EXISTING_SSO_USER,
    ERROR_REASON_1_FOR_NEW_SSO_USER,
    ERROR_REASON_2_FOR_EXISTING_SSO_USER,
    ERROR_REASON_2_FOR_NEW_SSO_USER,
    ERROR_REASON_3_FOR_EXISTING_SSO_USER,
    ERROR_REASON_4_FOR_EXISTING_SSO_USER,
    OPTUM_MSO_CONNECTION_NAME,
    OPTUM_WEB_CONNECTION_NAME,
    REJECT_DUE_TO_HARD_CHECK_FAIL,
    SSO_HARD_CHECK_FF_KEY,
    SSO_SOFT_CHECK_FF_KEY,
    SSO_USER_DATA_STORAGE,
    SSO_VALIDATION_METRICS_PREFIX,
    SUCCESS_CHECK_FOR_EXISTING_SSO_USER,
    SUCCESS_CHECK_FOR_NEW_SSO_USER,
)
from common import stats
from storage.connection import db
from utils.launchdarkly import idp_user_context
from utils.log import logger

log = logger(__name__)

__all__ = (
    "SSOService",
    "SSOError",
    "SSOIdentityError",
    "SSOLoginError",
    "IDPAssertion",
    "get_sso_service",
)


@dataclasses.dataclass
class IDPAssertion:
    """Class for handling IDP assertion values."""

    __slots__ = (
        "subject",
        "email",
        "first_name",
        "last_name",
        "organization_external_id",
        "rewards_id",
        "employee_id",
        "auth0_user_id",
    )

    subject: str
    email: str
    first_name: str
    last_name: str
    organization_external_id: str
    rewards_id: str
    employee_id: str
    auth0_user_id: str


def get_sso_service(session: sqlalchemy.orm.scoping.ScopedSession = None) -> SSOService:  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
    return SSOService(session=session)


class SSOService:
    """Core business logic managing identities from external SSO Providers."""

    _UTF8 = "utf-8"

    def __init__(
        self,
        identities: repository.UserExternalIdentityRepository | None = None,
        idps: repository.IdentityProviderRepository | None = None,
        field_aliases: repository.IDPFieldAliasRepository | None = None,
        users: user.UserService | None = None,
        session: sqlalchemy.orm.scoping.ScopedSession | None = None,
        management_client: idp.ManagementClient | None = None,
        auth: authn.AuthenticationService | None = None,
        is_in_uow: bool = False,
    ):
        # Save the session to be used during user creation for the user-related
        # objects. If no session was provided db.session is used instead, but it
        # does not get passed to the UserExternalIdentityRepository,
        # IdentityProviderRepository, IDPFieldAliasRepository, or UserService.
        self.session = session or db.session
        self.identities = identities or repository.UserExternalIdentityRepository(
            session=self.session, is_in_uow=is_in_uow
        )
        self.idps = idps or repository.IdentityProviderRepository(
            session=self.session, is_in_uow=is_in_uow
        )
        self.field_aliases = field_aliases or repository.IDPFieldAliasRepository(
            session=self.session, is_in_uow=is_in_uow
        )
        self.users = users or user.UserService(
            session=self.session, is_in_uow=is_in_uow
        )
        self.management_client = management_client or idp.ManagementClient()
        self.auth = auth or authn.AuthenticationService(is_in_uow=is_in_uow)

    def insert_uei_data_from_authn_api(self, data: dict) -> None:
        """
        This function is ONLY used for the data sync from the authn_api service
        """
        data["modified_at"] = data["updated_at"]
        data.pop("updated_at")
        instance = model.UserExternalIdentity(**data)
        identities = self.identities.create(instance=instance)
        if not identities:
            log.error(
                "Failed create user external identity from the authn-api",
                user_id=data.get("id"),
            )

    def update_uei_data_from_authn_api(self, data: dict) -> None:
        """
        This function is ONLY used for the data sync from the authn_api service
        """
        data["modified_at"] = data["updated_at"]
        data.pop("updated_at")
        instance = model.UserExternalIdentity(**data)
        identities = self.identities.update(instance=instance)
        if not identities:
            log.error(
                "Failed update user external identity from the authn-api",
                user_id=data.get("id"),
            )

    def insert_identity_provider_data_from_authn_api(self, data: dict) -> None:
        """
        This function is ONLY used for the data sync from the authn_api service
        """
        data["modified_at"] = data["updated_at"]
        data.pop("updated_at")
        instance = model.IdentityProvider(**data)
        identity_provider = self.idps.create(instance=instance)
        if not identity_provider:
            log.error(
                "Failed create identity provider from the authn-api",
                user_id=data.get("id"),
            )

    def update_identity_provider_data_from_authn_api(self, data: dict) -> None:
        """
        This function is ONLY used for the data sync from the authn_api service
        """
        data["modified_at"] = data["updated_at"]
        data.pop("updated_at")
        instance = model.IdentityProvider(**data)
        identity_provider = self.idps.update(instance=instance)
        if not identity_provider:
            log.error(
                "Failed update identity provider from the authn-api",
                user_id=data.get("id"),
            )

    def retrieval_users_per_connection_from_maven(
        self, connection_name: str
    ) -> list[model.UserExternalIdentity]:
        idp_record = self.idps.get_by_name(name=connection_name)
        if idp_record is None:
            log.error(f"Connection {connection_name} not found in the database")
            stats.increment(
                metric_name=f"{SSO_VALIDATION_METRICS_PREFIX}.fetch_idp_record_from_maven_db",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=[
                    "reason:idp_not_found",
                    f"connection_name: {connection_name.replace(' ', '-')}",
                ],
            )
            return []
        stats.increment(
            metric_name=f"{SSO_VALIDATION_METRICS_PREFIX}.fetch_idp_record_from_maven_db",
            pod_name=stats.PodNames.CORE_SERVICES,
            tags=[
                "reason:idp_found",
                f"connection_name: {connection_name.replace(' ', '-')}",
            ],
        )
        return self.identities.get_by_idp_id(idp_id=idp_record.id)

    def get_idps_by_time_range(
        self, end: datetime.date, start: datetime.date | None = None
    ) -> list[model.IdentityProvider]:
        if start and end <= start:
            log.error(f"{end} time is less or equal to {start} time")
            return []
        return self.idps.get_all_by_time_range(end=end, start=start)

    def get_identities_by_time_range(
        self, end: datetime.date, start: datetime.date | None = None
    ) -> list[model.UserExternalIdentity]:
        if start and end <= start:
            log.error(f"{end} time is less or equal to {start} time")
            return []
        return self.identities.get_all_by_time_range(end=end, start=start)

    def decode_external_id(self, encoded_external_id: str) -> str:
        base64_string = encoded_external_id
        base64_bytes = base64_string.encode(self._UTF8)
        string_bytes = base64.b64decode(base64_bytes)
        decoded_external_id = string_bytes.decode(self._UTF8)

        return decoded_external_id

    def fetch_identities(self, *, user_id: int) -> list[model.UserExternalIdentity]:
        """Fetch all identities associated to the given user ID."""
        identities = self.identities.get_by_user_id(user_id=user_id)
        return identities

    def fetch_idp(self, idp_id: int) -> model.IdentityProvider | None:
        return self.idps.get(id=idp_id)

    def fetch_identity_by_idp_and_external_user_id(
        self, idp_id: int, external_user_id: str
    ) -> model.UserExternalIdentity:
        return self.identities.get_by_idp_and_external_user_id(
            idp_id=idp_id, external_user_id=external_user_id
        )

    def retrieval_idp_user(self, external_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        idp_user = self.management_client.get_user(external_id=external_id)
        if idp_user is None:
            raise SSOLoginError("No user found in the IDP")
        # This IDPAssertion is built to match the format of our legacy SAML assertions
        assertion = IDPAssertion(
            subject=idp_user.external_user_id,
            email=idp_user.email,
            first_name=idp_user.first_name,
            last_name=idp_user.last_name,
            organization_external_id=idp_user.organization_external_id,
            rewards_id=idp_user.rewards_id,
            employee_id=idp_user.employee_id,
            auth0_user_id=idp_user.user_id,
        )

        provider, connection_name = self._extract_idp_from_connection(
            idp_user.identities
        )
        if provider is None:
            log.error("IDP User has no saml connection type")
            raise SSOLoginError("SAML provider not found for connection.")

        """Process a new identity into an internal user."""
        conflict = self.identities.get_by_reporting_id(
            reporting_id=idp_user.rewards_id,
        )
        if conflict:
            raise SSOIdentityError(
                message="This user is already associated to another identity.",
                assertion=assertion,
                provider=provider,
                identity=conflict,
            )

        return idp_user, provider, connection_name

    def _send_metrics(self, reason: str) -> None:
        stats.increment(
            metric_name=f"{SSO_VALIDATION_METRICS_PREFIX}.sso_data_validation",
            pod_name=stats.PodNames.CORE_SERVICES,
            tags=[f"reason:{reason.replace(' ', '-')}"],
        )

    def new_sso_user_check(
        self, idp_id: int, auth0_user: IDPUser
    ) -> tuple[bool, str, model.UserExternalIdentity | None]:
        # Step 1: check whether the identity query by auth0 user_id is missing or not. Expect the identity is missing
        identity_by_auth0_user_id = self.identities.get_by_auth0_user_id(
            auth0_user_id=auth0_user.user_id
        )
        if identity_by_auth0_user_id:
            log.error(
                "Found data cross link issue",
                auth0_user_id=auth0_user.user_id,
                data_classification="confidential",
                auth_related="true",
            )
            self._send_metrics(reason=ERROR_REASON_1_FOR_NEW_SSO_USER.replace(" ", "-"))

            return False, ERROR_REASON_1_FOR_NEW_SSO_USER, None
        # Step 2: check whether the identity query by idp and external user id is missing. Expect the identity is miss
        identity_by_idp_and_external_user_id = (
            self.identities.get_by_idp_and_external_user_id(
                idp_id=idp_id, external_user_id=auth0_user.external_user_id
            )
        )
        if identity_by_idp_and_external_user_id:
            log.error(
                "Found data cross link issue",
                auth0_user_id=auth0_user.user_id,
                data_classification="confidential",
                auth_related="true",
            )
            self._send_metrics(reason=ERROR_REASON_2_FOR_NEW_SSO_USER.replace(" ", "-"))

            return False, ERROR_REASON_2_FOR_NEW_SSO_USER, None

        log.info(
            "Complete sso data check for new sso user",
            auth0_user_id=auth0_user.user_id,
            data_classification="confidential",
            auth_related="true",
        )
        self._send_metrics(reason=SUCCESS_CHECK_FOR_NEW_SSO_USER.replace(" ", "-"))
        return (
            True,
            SUCCESS_CHECK_FOR_NEW_SSO_USER,
            identity_by_idp_and_external_user_id,
        )

    def _check_sso_user_profile_identical(
        self, fields: list[tuple[str, str, str]]
    ) -> tuple[bool, str]:
        # The fields' element is (field_name, field in user_external_identity, filed in auth0_user)
        for field in fields:
            if field[1] != field[2]:
                return False, field[0]
        return True, ""

    def existing_sso_user_check(
        self, idp_id: int, auth0_user: IDPUser, maven_user_id: int
    ) -> tuple[bool, str, model.UserExternalIdentity | None]:
        identity_by_auth0_user_id = self.identities.get_by_auth0_user_id(
            auth0_user_id=auth0_user.user_id
        )
        # Step 1: check whether the record query by auth0 user id is missing or not. Expectation is not missing
        if not identity_by_auth0_user_id:
            self._send_metrics(
                reason=ERROR_REASON_1_FOR_EXISTING_SSO_USER.replace(" ", "-")
            )

            return False, ERROR_REASON_1_FOR_EXISTING_SSO_USER, None
        # Step 2: check the maven user id in the record is identical with the maven user id from the access token
        if identity_by_auth0_user_id.user_id != maven_user_id:
            self._send_metrics(
                reason=ERROR_REASON_2_FOR_EXISTING_SSO_USER.replace(" ", "-")
            )

            return False, ERROR_REASON_2_FOR_EXISTING_SSO_USER, None
        # Step 3: check whether the record query by idp id and external user id is missing or not. Expect not miss
        identity_by_idp_and_user_external_user_id = (
            self.identities.get_by_idp_and_external_user_id(
                idp_id=idp_id, external_user_id=auth0_user.external_user_id
            )
        )
        if not identity_by_idp_and_user_external_user_id:
            self._send_metrics(
                reason=ERROR_REASON_3_FOR_EXISTING_SSO_USER.replace(" ", "-")
            )

            return False, ERROR_REASON_3_FOR_EXISTING_SSO_USER, None
        # Step 4: check the email, first and last name from Auth0 are identical with the existing data.
        pending_check_fields = [
            (
                "email",
                identity_by_idp_and_user_external_user_id.sso_email,
                auth0_user.email,
            ),
            (
                "first name",
                identity_by_idp_and_user_external_user_id.sso_user_first_name,
                auth0_user.first_name,
            ),
            (
                "last name",
                identity_by_idp_and_user_external_user_id.sso_user_last_name,
                auth0_user.last_name,
            ),
        ]
        is_identical, field_name = self._check_sso_user_profile_identical(
            fields=pending_check_fields
        )
        if not is_identical:
            self._send_metrics(
                reason=ERROR_REASON_4_FOR_EXISTING_SSO_USER.replace(" ", "-")
            )
            return (
                False,
                f"{ERROR_REASON_4_FOR_EXISTING_SSO_USER} in {field_name}",
                None,
            )

        log.info(
            "Complete sso data check for existing sso user",
            auth0_user_id=auth0_user.user_id,
            data_classification="confidential",
            auth_related="true",
        )
        self._send_metrics(reason=SUCCESS_CHECK_FOR_EXISTING_SSO_USER.replace(" ", "-"))
        return (
            True,
            SUCCESS_CHECK_FOR_EXISTING_SSO_USER,
            identity_by_idp_and_user_external_user_id,
        )

    @ddtrace.tracer.wrap()
    def handle_sso_login_with_data_check(
        self,
        idp_user: IDPUser,
        token_data: dict | None = None,
        enable_user_data_storage: bool = False,
    ) -> tuple[bool, model.UserExternalIdentity | None, dict]:
        log.info("Entering sso data checking process")
        if not token_data:
            log.error("Missing access token data")
            raise SSOLoginError("Invalid request")

        is_hard_check_enabled = feature_flags.bool_variation(
            SSO_HARD_CHECK_FF_KEY,
            idp_user_context(idp_user),
            default=False,
        )

        is_new_sso_user = False
        # check whether the
        log.info("Check whether has the maven user id in token")
        maven_user_id = token_data.get("user_id", "")
        if not maven_user_id:
            log.info("The user is new")
            is_new_sso_user = True
        else:
            log.info(
                f"It is an existing sso user with maven user id {maven_user_id}",
                user_id=maven_user_id,
            )
            maven_user_id = int(maven_user_id)

        provider, connection_name = self._extract_idp_from_connection(
            idp_user.identities
        )
        if provider is None:
            log.error("IDP User has no saml connection type")
            raise SSOLoginError("SAML provider not found for connection.")

        # This IDPAssertion is built to match the format of our legacy SAML assertions
        assertion = IDPAssertion(
            subject=idp_user.external_user_id,
            email=idp_user.email,
            first_name=idp_user.first_name,
            last_name=idp_user.last_name,
            organization_external_id=idp_user.organization_external_id,
            rewards_id=idp_user.rewards_id,
            employee_id=idp_user.employee_id,
            auth0_user_id=idp_user.user_id,
        )
        if assertion.subject is None or provider.id is None:
            log.error("No external user id or provider id provided by the Idp")
            raise SSOLoginError("Invalid SAML Request")

        check_result = False
        check_result_reason = ""
        if is_new_sso_user:
            check_result, check_result_reason, identity = self.new_sso_user_check(
                idp_id=provider.id, auth0_user=idp_user
            )
        else:
            check_result, check_result_reason, identity = self.existing_sso_user_check(
                idp_id=provider.id,
                auth0_user=idp_user,
                maven_user_id=int(maven_user_id),
            )
        saml_user_data = {"idp_connection_name": connection_name}
        if idp_user.first_name:
            saml_user_data["first_name"] = idp_user.first_name
        if idp_user.email:
            saml_user_data["email"] = idp_user.email
        if not check_result:
            log.error(
                f"Data check result is {check_result} with reason: {check_result_reason}. Auth0 user_id: {idp_user.user_id}",
                user_id=maven_user_id,
                auth0_user_id=idp_user.user_id,
                data_classification="confidential",
                auth_related="true",
            )
            # Use the legacy approach to fetch the identity
            identity = self.identities.get_by_idp_and_external_user_id(
                idp_id=provider.id, external_user_id=assertion.subject
            )
            if not identity:
                # It is to avoid NPE issue when the soft check is on
                log.error(
                    f"User external identity record is missing for maven user {maven_user_id}, auth0 user_id {idp_user.user_id}",
                    user_id=maven_user_id,
                    auth0_user_id=idp_user.user_id,
                    data_classification="confidential",
                    auth_related="true",
                )
                if is_hard_check_enabled:
                    raise SSOError(
                        "This user is already associated to another identity.",
                        assertion=assertion,
                        provider=provider,
                    )
                else:
                    # Fallback to the legacy flow logic to treat it as new SSO user request
                    self._execute_new_assertion(idp=provider, assertion=assertion)
                    return True, None, saml_user_data
            if is_hard_check_enabled:
                log.info("Request rejected due to hard check enabled")
                self._send_metrics(reason=REJECT_DUE_TO_HARD_CHECK_FAIL)
                raise SSOIdentityError(
                    "This user is already associated to another identity.",
                    assertion=assertion,
                    provider=provider,
                    identity=identity,
                )

        if is_new_sso_user:
            self._execute_new_assertion(idp=provider, assertion=assertion)
            return True, None, saml_user_data

        external_identity = self._execute_existing_assertion(
            idp=provider,
            identity=identity,
            assertion=assertion,
            connection_name=connection_name,
            enable_user_data_storage=enable_user_data_storage,
            is_data_check_pass=check_result,
        )

        self.update_external_user_id_link(
            external_id=idp_user.user_id,
            user_id=external_identity.user_id,
            connection_name=connection_name,
            idp_user=idp_user,
        )
        return False, external_identity, saml_user_data

    @ddtrace.tracer.wrap()
    def handle_sso_login(
        self, external_id: str, token_data: dict | None = None
    ) -> tuple[bool, model.UserExternalIdentity | None, dict]:
        idp_user = self.management_client.get_user(external_id=external_id)
        log.info(
            "Start handling sso login",
            data_classification="confidential",
            auth_related="true",
        )
        if idp_user is None:
            log.error(
                f"Auth0 user not found for id {external_id}",
                data_classification="confidential",
                auth_related="true",
            )
            raise SSOLoginError("No user found in the IDP")

        is_soft_check_enabled = feature_flags.bool_variation(
            SSO_SOFT_CHECK_FF_KEY,
            idp_user_context(idp_user),
            default=False,
        )
        enable_user_data_storage = feature_flags.bool_variation(
            SSO_USER_DATA_STORAGE,
            idp_user_context(idp_user),
            default=False,
        )
        # After the release is stable, we can pass the idp user directly to the function
        if is_soft_check_enabled:
            return self.handle_sso_login_with_data_check(
                idp_user=idp_user,
                token_data=token_data,
                enable_user_data_storage=enable_user_data_storage,
            )
        else:
            return self.handle_sso_login_legacy_flow(
                external_id=external_id,
                enable_user_data_storage=enable_user_data_storage,
            )

    @ddtrace.tracer.wrap()
    def handle_sso_login_legacy_flow(
        self, external_id: str, enable_user_data_storage: bool = False
    ) -> tuple[bool, model.UserExternalIdentity | None, dict]:
        idp_user = self.management_client.get_user(external_id=external_id)
        if idp_user is None:
            raise SSOLoginError("No user found in the IDP")

        provider, connection_name = self._extract_idp_from_connection(
            idp_user.identities
        )
        if provider is None:
            log.error("IDP User has no saml connection type")
            raise SSOLoginError("SAML provider not found for connection.")

        # This IDPAssertion is built to match the format of our legacy SAML assertions
        assertion = IDPAssertion(
            subject=idp_user.external_user_id,
            email=idp_user.email,
            first_name=idp_user.first_name,
            last_name=idp_user.last_name,
            organization_external_id=idp_user.organization_external_id,
            rewards_id=idp_user.rewards_id,
            employee_id=idp_user.employee_id,
            auth0_user_id=idp_user.user_id,
        )
        if assertion.subject is None or provider.id is None:
            log.error("No external user id or provider id provided by the Idp")
            raise SSOLoginError("Invalid SAML Request")

        identity = self.identities.get_by_idp_and_external_user_id(
            idp_id=provider.id, external_user_id=assertion.subject
        )
        saml_user_data = {"idp_connection_name": connection_name}
        if idp_user.first_name:
            saml_user_data["first_name"] = idp_user.first_name
        if idp_user.email:
            saml_user_data["email"] = idp_user.email

        if not identity:
            is_new = True
            external_identity = self._execute_new_assertion(
                idp=provider, assertion=assertion
            )
            return is_new, None, saml_user_data
        else:
            is_new = False
            external_identity = self._execute_existing_assertion(
                idp=provider,
                identity=identity,
                assertion=assertion,
                connection_name=connection_name,
                enable_user_data_storage=enable_user_data_storage,
            )

        self.update_external_user_id_link(
            external_id=external_id,
            user_id=external_identity.user_id,
            connection_name=connection_name,
            idp_user=idp_user,
        )
        return is_new, external_identity, saml_user_data

    @ddtrace.tracer.wrap()
    def execute_assertion(
        self, request: saml.SAMLRequestBody
    ) -> tuple[bool, model.UserExternalIdentity]:
        """Process the assertion provided by the SAML request into an internal user."""
        idp, assertion = self.parse_saml_request(request=request)
        identity = self.identities.get_by_idp_and_external_user_id(
            idp_id=idp.id, external_user_id=assertion.subject
        )
        if not identity:
            return True, self._execute_new_assertion(idp=idp, assertion=assertion)
        return False, self._execute_existing_assertion(
            idp=idp, identity=identity, assertion=assertion
        )

    @ddtrace.tracer.wrap()
    def parse_saml_request(
        self, request: saml.SAMLRequestBody
    ) -> tuple[model.IdentityProvider, saml.SAMLAssertion]:
        """Parse a SAML XML request into a normalized assertion for persisting."""
        providers = {p.name: p for p in self.idps.all()}
        name_metadata = {p.name: p.metadata for p in providers.values()}
        onelogin_config = saml.get_onelogin_configuration(**name_metadata)
        onelogin = saml.OneLoginSAMLVerificationService(configuration=onelogin_config)
        idp_name, auth_object = onelogin.process_request(request=request)
        idp = providers[idp_name]
        field_aliases = self.field_aliases.get_by_idp_id(idp_id=idp.id)
        mapping = {f.field: f.alias for f in field_aliases}
        assertion = onelogin.parse_auth_object(
            idp=idp_name, auth_object=auth_object, **mapping
        )
        idp = providers[assertion.idp]
        return idp, assertion

    @ddtrace.tracer.wrap()
    def _extract_idp_from_connection(
        self, identities: list[IDPIdentity]
    ) -> tuple[Any, str] | tuple[None, None]:
        if identities is None:
            return None, None
        try:
            saml_identity = next(i for i in identities if i.provider == "samlp")
        except StopIteration:
            return None, None

        # TODO: Revert this change once the Identity Provider table is deprecated
        connection_name = saml_identity.connection
        if connection_name == "Virgin-Pulse":
            log.info("Converting the connection name from Auth0 to map db")
            connection_name = "VIRGIN_PULSE"

        return self.idps.get_by_name(name=connection_name), saml_identity.connection

    def update_external_user_id_link(
        self,
        external_id: str,
        user_id: int,
        connection_name: str,
        idp_user: IDPUser | None = None,
    ) -> None:
        """Sets the Maven User ID on the Identity in our IDP used for SSO"""
        if connection_name is None:
            log.warning(
                f"Unable to update user metadata for user_id {user_id} due to missing connection_name"
            )
            return

        identities = self.users.get_identities(user_id=user_id)
        app_metadata = {"maven_user_id": user_id, "maven_user_identities": identities}

        if idp_user and (
            idp_user.app_metadata is None
            or idp_user.app_metadata.original_email is None
        ):
            # first time SSO for the user, add the idp_user's email, first name and last name
            # into the app_meta data as the immutable values for subsequent SAML request comparison
            log.info("first time SSO user, adding original_email")
            app_metadata["original_email"] = idp_user.email or ""
            app_metadata["original_first_name"] = idp_user.first_name or ""
            app_metadata["original_last_name"] = idp_user.last_name or ""

        self.management_client.update_user(
            external_id, connection_name=connection_name, app_metadata=app_metadata
        )

    @ddtrace.tracer.wrap()
    def _execute_new_assertion(
        self, *, idp: model.IdentityProvider, assertion: IDPAssertion
    ) -> model.UserExternalIdentity | None:
        log.info("Executing new sso user request")

        """Process a new identity into an internal user."""
        conflict = self.identities.get_by_reporting_id(
            reporting_id=assertion.rewards_id,
        )
        if conflict:
            raise SSOIdentityError(
                "This user is already associated to another identity.",
                assertion=assertion,
                provider=idp,
                identity=conflict,
            )

        return None

    @ddtrace.tracer.wrap()
    def _execute_existing_assertion(
        self,
        *,
        idp: model.IdentityProvider,
        identity: model.UserExternalIdentity,
        assertion: IDPAssertion,
        enable_user_data_storage: bool = False,
        is_data_check_pass: bool = False,
        connection_name: str = None,  # type: ignore[assignment] # Incompatible default for argument "connection_name" (default has type "None", argument has type "str")
    ) -> model.UserExternalIdentity:
        """Validate and update an existing identity with the new assertion data."""
        # We don't check the unique_corp_id for the Optum connection in SSO, because they don't provide it in the SAML request.
        if connection_name is not None and (
            connection_name == OPTUM_WEB_CONNECTION_NAME
            or connection_name == OPTUM_MSO_CONNECTION_NAME
        ):
            log.info("SSO request comes from Optum, skip unique corp id check.")
        else:
            if identity.unique_corp_id != assertion.employee_id:
                raise SSOIdentityError(
                    "The provided employee ID does not match our records for this user.",
                    assertion=assertion,
                    provider=idp,
                    identity=identity,
                )
        if enable_user_data_storage and is_data_check_pass:
            identity = dataclasses.replace(
                identity,
                external_organization_id=assertion.organization_external_id,
                reporting_id=assertion.rewards_id,
                sso_email=assertion.email,
                auth0_user_id=assertion.auth0_user_id,
                sso_user_first_name=assertion.first_name,
                sso_user_last_name=assertion.last_name,
            )
        else:
            identity = dataclasses.replace(
                identity,
                external_organization_id=assertion.organization_external_id,
                reporting_id=assertion.rewards_id,
            )
        updated = self.identities.update(instance=identity)
        return updated


class SSOError(Exception):
    __slots__ = ("request", "assertion", "provider")

    assertion: IDPAssertion
    provider: model.IdentityProvider

    def __init__(
        self,
        message: str,
        assertion: IDPAssertion,
        provider: model.IdentityProvider,
    ):
        self.assertion = assertion
        self.provider = provider
        super().__init__(message)


class SSOIdentityError(SSOError):
    __slots__ = ("identity",)

    identity: model.UserExternalIdentity

    def __init__(
        self,
        message: str,
        assertion: IDPAssertion,
        provider: model.IdentityProvider,
        identity: model.UserExternalIdentity,
    ):
        self.identity = identity
        super().__init__(message, assertion, provider)


class SSOLoginError(Exception):
    ...
