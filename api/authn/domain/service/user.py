from __future__ import annotations

import os
import re
from datetime import date, datetime
from typing import Hashable

import sqlalchemy.orm.scoping
from flask_restful import abort
from sqlalchemy import and_, bindparam, func, null, or_, orm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext import baked

from appointments.models.cancellation_policy import (
    CancellationPolicy,
    CancellationPolicyName,
)
from appointments.models.schedule import Schedule
from authn.domain import model, repository
from authn.domain.service import authn
from authn.errors.idp.client_error import ClientError, IdentityClientError
from authn.errors.local.error import PasswordStrengthCheckError
from authn.models.email_domain_denylist import EmailDomainDenylist
from authn.models.user import User
from authn.util.constants import USER_METRICS_PREFIX
from authz.models.roles import ROLES
from care_advocates.models.assignable_advocates import AssignableAdvocate
from common import stats
from common.services.ratelimiting import (
    clear_rate_limit_redis,
    get_email_or_client_ip,
    get_request_endpoint,
)
from health.domain.add_profile import add_profile_to_user
from models.actions import ACTIONS, audit
from models.enterprise import OnboardingState
from models.profiles import Agreement, AgreementAcceptance, PractitionerProfile
from models.referrals import (
    DEFAULT_MEMBER_VALUE,
    PractitionerInvite,
    ReferralCode,
    ReferralCodeValue,
    ReferralCodeValueTypes,
)
from models.verticals_and_specialties import is_cx_vertical_name
from payments.models.practitioner_contract import ContractType
from storage.connection import db
from utils.log import logger
from utils.mail import PRACTITIONER_SUPPORT_EMAIL, alert_admin
from utils.onboarding_state import update_onboarding_state
from utils.passwords import check_password_strength, encode_password, random_password
from utils.service_owner_mapper import service_ns_team_mapper

__all__ = (
    "get_user_service",
    "UserService",
    "UserError",
    "NoUserFound",
    "PasswordStrengthCheckerMixIn",
)


log = logger(__name__)


def get_user_service(
    session: sqlalchemy.orm.scoping.ScopedSession = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
) -> UserService:
    return UserService(session=session)


class PasswordStrengthCheckerMixIn:
    @classmethod
    def check_password_strength(cls, password: str) -> None:
        pw_score = check_password_strength(password)
        if len(pw_score["feedback"]) > 0:
            raise PasswordStrengthCheckError(pw_score["feedback"])


class UserService(PasswordStrengthCheckerMixIn):
    """The core business logic for authenticating a user."""

    __slots__ = ("users", "session", "user_migration")

    def __init__(
        self,
        *,
        users: repository.UserRepository = None,  # type: ignore[assignment] # Incompatible default for argument "users" (default has type "None", argument has type "UserRepository")
        session: sqlalchemy.orm.scoping.ScopedSession = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        user_migration: repository.UserMigrationRepository = None,  # type: ignore[assignment] # Incompatible default for argument "user_migration" (default has type "None", argument has type "scoped_session")
        is_in_uow: bool = False,
    ):
        self.session = session or db.session
        self.users = users or repository.UserRepository(
            session=self.session, is_in_uow=is_in_uow
        )
        self.user_migration = user_migration or repository.UserMigrationRepository(
            session=self.session, is_in_uow=is_in_uow
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(users={self.users})>"

    def get_user(self, *, user_id: int) -> model.User | None:
        return self.users.get(id=user_id)

    def get_by_email(self, *, email: str) -> model.User:
        return self.users.get_by_email(email=email)

    def get_all_by_ids(self, ids: list[int]) -> list[model.User]:
        return self.users.get_all_by_ids(ids)

    def get_all_by_time_range(
        self, end: date, start: date | None = None
    ) -> list[model.UserMigration]:
        if start and end <= start:
            log.error(f"{end} time is less or equal to {start} time")
            return []
        return self.users.get_all_by_time_range(end=end, start=start)

    def fetch_users(self, *, filters: dict = None, limit: int = 250, offset: int = 0):  # type: ignore[no-untyped-def,assignment] # Function is missing a return type annotation #type: ignore[assignment] # Incompatible default for argument "filters" (default has type "None", argument has type "Dict[Any, Any]")
        return self.users.fetch(filters, limit, offset)

    def get_identities(self, *, user_id: int) -> list[str]:
        identities = []
        practitioner = PractitionerProfile.query.get(user_id)
        if practitioner:
            identities.append(ROLES.practitioner)
            care_coordinator = any(
                is_cx_vertical_name(v.name) for v in practitioner.verticals
            )
            if care_coordinator:
                identities.append(ROLES.care_coordinator)
        else:
            identities.append(ROLES.member)

        return identities

    def create_user(
        self,
        *,
        email: str,
        is_active: bool = False,
        first_name: str = None,  # type: ignore[assignment] # Incompatible default for argument "first_name" (default has type "None", argument has type "str")
        last_name: str = None,  # type: ignore[assignment] # Incompatible default for argument "last_name" (default has type "None", argument has type "str")
        **additional_inputs: Hashable,
    ) -> model.User:
        """Create a new Maven user."""

        if email:
            email = email.strip()

        # Save the email and encoded password for future authentication.
        user = self.users.create(
            instance=model.User(
                email=email,
                password=random_password(),
                active=is_active,
                first_name=first_name,
                last_name=last_name,
            )
        )

        # Notify that a user has been created to setup the user-related objects
        # and settings
        self.notify_user_created(user_id=user.id, **additional_inputs)

        return user

    def insert_user_data_from_authn_api(self, data: dict) -> None:
        """
        This function is ONLY used for the data sync from the authn_api service
        """
        data["modified_at"] = data["updated_at"]
        data.pop("updated_at")
        instance = model.UserMigration(**data)
        user = self.user_migration.create(instance=instance)
        if not user:
            log.error("Failed create user from the authn-api", user_id=data.get("id"))

    def update_user_data_from_authn_api(self, data: dict) -> None:
        """
        This function is ONLY used for the data sync from the authn_api service
        """
        data["modified_at"] = data["updated_at"]
        data.pop("updated_at")
        instance = model.UserMigration(**data)
        user = self.user_migration.update(instance=instance)
        if not user:
            log.error("Failed update user from the authn-api", user_id=data.get("id"))

    def notify_user_created(self, user_id, **additional_inputs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # Getting the SQLAlchemy User object using the ID of the domain model from
        # the User Service is a temporary solution until a proper solution is found to
        # call the necessary functions to create the user-related objects and settings
        # that are used by other services.
        user_orm_obj = self.session.query(User).filter(User.id == user_id).first()
        if user_orm_obj is None:
            raise NoUserFound(
                "The newly created user could not be found in the database."
            )

        # These steps create a series of related (downstream) objects to flesh out the user.
        #   We nest this under a no_autoflush block so we can explicitly control *when* we write.
        #   Otherwise, we run the risk of writing incomplete data and introducing potential conflicts.
        with self.session.no_autoflush:
            # Imports moved here to avoid circular import in Data Admin
            from authn.resources import user as user_resources
            from health.domain import add_profile

            try:
                add_profile.add_profile_to_user(user_orm_obj, **additional_inputs)
                user_resources.post_user_create_steps(user_orm_obj)
                user_resources.create_idp_user(user_orm_obj)
            except Exception as err:
                log.error(f"Failed in the post user creation step for user {user_id}")
                self.session.rollback()
                raise err

        self.session.flush()
        self.session.commit()

    def update_user(
        self,
        *,
        user_id: int,
        email: str = None,  # type: ignore[assignment] # Incompatible default for argument "email" (default has type "None", argument has type "str")
        **additional_inputs: Hashable,
    ) -> model.User:
        """Update an existing Maven user."""
        user = self.get_user(user_id=user_id)
        if email and email != user.email:  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "email"
            email = email.strip()
            auth_service = authn.get_auth_service(email=email)
            result = auth_service.update_email(
                user_id=user_id, email=user.email, new_email=email  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "email"
            )
            if not result:
                # TODO: change back to 500 once address the https://mavenclinic.atlassian.net/browse/CPCS-2444
                abort(400, message="Something went wrong, please try again.")
            user.email = email  # type: ignore[union-attr] # Item "None" of "Optional[User]" has no attribute "email"
        user = self.users.update(instance=user)  # type: ignore[arg-type] # Argument "instance" to "update" of "BaseRepository" has incompatible type "Optional[User]"; expected "User"
        return user  # type: ignore[return-value] # Incompatible return value type (got "Optional[User]", expected "User")

    def create_maven_user(
        self,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        session: db.Session,  # type: ignore[name-defined] # Name "db.Session" is not defined
        middle_name: str = None,  # type: ignore[assignment] # Incompatible default for argument "middle_name" (default has type "None", argument has type "str")
        username: str = None,  # type: ignore[assignment] # Incompatible default for argument "username" (default has type "None", argument has type "str")
        image_id: str = None,  # type: ignore[assignment] # Incompatible default for argument "image_id" (default has type "None", argument has type "str")
        external_id: str = None,  # type: ignore[assignment] # Incompatible default for argument "external_id" (default has type "None", argument has type "str")
        is_universal_login: bool = False,
    ) -> User | None:
        if not is_universal_login:
            # we only validate email and password for Maven sign up flow
            if not email:
                log.error("missing email")
                abort(400, message=self.CLIENT_ERROR_MESSAGE)
            self.validate_email(email=email)
            if not password:
                log.error("missing password")
                abort(400, message=self.CLIENT_ERROR_MESSAGE)

            try:
                self.check_password_strength(password)
            except PasswordStrengthCheckError as e:
                log.warning("Password strength check is not passed")
                abort(400, message=str(e))

        with session.no_autoflush:
            query = self._exists_query(db.session)
            exists = query.params(email=email, username=username).scalar()
            if exists:
                log.warning("Found a user with matching email or username.")
                abort(400, message=self.CLIENT_ERROR_MESSAGE)

            user = User(
                first_name=first_name,
                last_name=last_name,
                username=username,
                email=email,
                password=encode_password(password),
                image_id=image_id,
            )

            if middle_name:
                user.middle_name = middle_name

            try:
                session.add(user)
                # We need the user ID before creating the IDP user.
                # Without flush, the auto generated ID won't be present in the user object.
                session.flush()
            except IntegrityError:
                abort(409, message=self.CLIENT_ERROR_MESSAGE)
            temp_user_id = user.id

            if not is_universal_login:
                # create the user at Auth0 (create_idp_user) for the Maven sign up flow.
                try:
                    from authn.resources.user import create_idp_user

                    create_idp_user(user, password)
                except ClientError as err:
                    log.error(f"Failed to create user in IDP due to ClientError: {err}")
                    session.rollback()
                    abort(err.code, message=self.CLIENT_ERROR_MESSAGE)
                except IdentityClientError as err:
                    log.error(
                        f"Failed to create user in IDP due to IdentityClientError: {err}"
                    )
                    session.rollback()
                    abort(err.code, message=self.SERVER_ERROR_MESSAGE)
                except Exception as e:
                    log.error(f"Failed to create user in IDP due to {e}")
                    session.rollback()
                    abort(500, message=self.SERVER_ERROR_MESSAGE)
            else:
                # For universal login, the user is created at Auth0 already,
                # we create the entry at user_auth table and update the auth0 user meta_data
                try:
                    from authn.resources.user import create_user_auth_update_idp_user

                    create_user_auth_update_idp_user(user, external_id)  # type: ignore[arg-type] # Argument 2 to "create_user_auth_update_idp_user" has incompatible type "Optional[str]"; expected "str"
                except ClientError as err:
                    log.error(
                        f"Failed to create user_auth in Maven due to ClientError: {err}"
                    )
                    session.rollback()
                    category = get_request_endpoint()
                    scope = get_email_or_client_ip()
                    clear_rate_limit_redis(category, scope)

                    abort(err.code, message=self.CLIENT_ERROR_MESSAGE)
                except IdentityClientError as err:
                    log.error(
                        f"Failed to create user_auth in Maven due to IdentityClientError: {err}"
                    )
                    session.rollback()
                    category = get_request_endpoint()
                    scope = get_email_or_client_ip()
                    clear_rate_limit_redis(category, scope)

                    abort(err.code, message=self.SERVER_ERROR_MESSAGE)
                except Exception as e:
                    log.error(f"Failed to create user_auth in Maven due to {e}")
                    session.rollback()
                    abort(500, message=self.SERVER_ERROR_MESSAGE)

            session.commit()
            committed_user_id = user.id

            if temp_user_id != committed_user_id:
                # in order to track the user id mismatch issue
                stats.increment(
                    metric_name=f"{USER_METRICS_PREFIX}.user_creation_id_mismatch",
                    pod_name=stats.PodNames.CORE_SERVICES,
                    tags=["error:true"],
                )
                log.error(
                    f"The temp user id {temp_user_id} is mis-matched with committed user id {committed_user_id}"
                )
        try:
            add_profile_to_user(user, **vars(user))
            # NOTE session is not passed into add_profile_to_user
            db.session.commit()
        except IntegrityError:
            stats.increment(
                metric_name=f"{USER_METRICS_PREFIX}.add_profile_to_user",
                pod_name=stats.PodNames.CORE_SERVICES,
                tags=["error:true"],
            )
            log.error(f"Failed to add profile to user {user.id}")
            abort(409, message=self.CLIENT_ERROR_MESSAGE)

        try:
            user = self.sync_practitioner_info(user)
            # NOTE session is not passed into _sync_practitioner_info
            db.session.commit()
        except IntegrityError:
            stats.increment(
                metric_name=f"{USER_METRICS_PREFIX}.sync_practitioner_info",
                pod_name=stats.PodNames.CARE_MANAGEMENT,
                tags=["error:true"],
            )
            log.error(f"Failed to sync practitioner info to user {user.id}")
            abort(409, message=self.CLIENT_ERROR_MESSAGE)

        # Assign a benefit ID to the user
        try:
            from wallet.repository.member_benefit import MemberBenefitRepository
            from wallet.services.member_benefit import MemberBenefitService

            repo = MemberBenefitRepository(session=db.session)
            member_benefit_service = MemberBenefitService(member_benefit_repo=repo)
            member_benefit_service.add_for_user(user_id=user.id)
        except Exception as e:
            db.session.rollback()
            stats.increment(
                metric_name=f"{USER_METRICS_PREFIX}.add_benefit_id",
                pod_name=stats.PodNames.BENEFITS_EXP,
                tags=["error:true"],
            )
            log.exception(
                "Failed to generate benefit ID:", user_id=str(user.id), error=e
            )
        else:
            db.session.commit()
            log.info("Successfully generated benefit ID", user_id=str(user.id))

        log.info(f"Success created user {user.id}")

        return user

    def post_user_create_steps_v2(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, user: User, agreements_accepted=False, language=None
    ):
        db.session.flush()
        audit(ACTIONS.user_added, user.id)
        log.info("Saved new user %s", user)

        schedule = Schedule(name=f"Schedule for {user.full_name}", user=user)
        db.session.add(schedule)

        acceptances = []
        if agreements_accepted:
            acceptances = [
                AgreementAcceptance(user=user, agreement=a)
                for a in Agreement.latest_agreements(user, language=language)
                if a.accept_on_registration
            ]
            db.session.add_all(acceptances)

        update_onboarding_state(user, OnboardingState.USER_CREATED)

        AssignableAdvocate.add_care_coordinator_for_member(user)
        db.session.flush()

        service_ns_tag = "authentication"
        team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
        from tasks.users import user_post_creation

        user_post_creation.delay(
            user.id, service_ns=service_ns_tag, team_ns=team_ns_tag
        )

        for acceptance in acceptances:
            acceptance.audit_creation()

        db.session.commit()

    def validate_email(self, email: str) -> None:
        # Regex based on RFC 3696
        if not re.match(
            r"(?=^.{1,64}@)^(?P<username>[\w!#$%&'*+\/=?`{|}~^-]+(?:\.[\w!#$%&'*+\/=?`{|}~^-]+)*)(?=@.{4,255}$)@(?P<domain>(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,6})$",
            email,
        ):
            log.error("Received an invalid email from the /users endpoint.")
            abort(400, message="The email address is invalid.")

        self._validate_email_domain(email)

    def _validate_email_domain(self, email):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        email_domain = email.split("@")[-1].lower()
        deny_list = db.session.query(EmailDomainDenylist).all()
        for deny_list_item in deny_list:
            if email_domain == deny_list_item.domain.lower():
                log.info(
                    "Denying user registration due to email domain",
                    domain=deny_list_item.domain,
                )
                abort(
                    400,
                    message=f"Registering with the {deny_list_item.domain} "
                    "email domain is not permitted. Please use a different email address.",
                )

    def _exists_query(self, session: orm.scoped_session) -> orm.Query:
        # We have to bind params like this so that we get consistent SQL generation.
        #   (e.g., if we pass in a null value for `username`, we get `NULL IS NOT NULL AND user.username IS NULL`.)
        #   (That's definitely not want we want.)
        # Since we're binding params, we may as well bake (read: cache) the final query.
        #   This way, building the SQL is a one-time thing.
        # See: https://docs.sqlalchemy.org/en/13/orm/extensions/baked.html
        bakery = baked.bakery()  # type: ignore[call-arg,func-returns-value] # Missing positional argument "initial_fn" in call to "__call__" of "Bakery" #type: ignore[func-returns-value] # Function does not return a value (it only ever returns None)
        baked_sub_query = bakery(lambda sesh: sesh.query(User))
        baked_sub_query += lambda q: q.filter(
            or_(
                User.email == bindparam("email"),
                and_(
                    bindparam("username") != null(),
                    User.username == bindparam("username"),
                ),
            )
        ).exists()

        baked_query = bakery(lambda sesh: sesh.query(baked_sub_query.to_query(sesh)))
        # The bakery wants a vanilla session, but a scoped_session is actually a proxy object.
        #   So we have to call the scoped_session to get the actual Session object...
        return baked_query(session())

    def sync_practitioner_info(self, user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        invite = (
            db.session.query(PractitionerInvite)
            .filter(
                PractitionerInvite.claimed_at == None,
                (func.lower(PractitionerInvite.email) == func.lower(user.email)),
            )
            .first()
        )

        if invite:
            log.info("Claiming invite for %s", user)
            # avoid circular impoart issue
            from common.services.api import HasUserResource

            has_user_resource = HasUserResource()
            has_user_resource.audit(
                "claim_practitioner_invite", user_id=user.id, user_email=user.email
            )

            add_profile_to_user(user, ROLES.practitioner, **vars(user))

            if invite.image_id:
                user.image_id = invite.image_id
            else:
                try:
                    user.image_id = int(
                        os.environ.get("PRACTITIONER_DEFAULT_IMAGE_ID", 194)
                    )
                except ValueError as e:
                    user.image_id = None
                    log.debug(
                        "Environment variable PRACTITIONER_DEFAULT_IMAGE_ID not set! %s",
                        e,
                    )

            pp = user.practitioner_profile

            if invite.json and invite.json.get("referral_code"):
                referral_code = invite.json.get("referral_code")
                existing_code = (
                    db.session.query(ReferralCode)
                    .filter(ReferralCode.code == referral_code)
                    .first()
                )
                if existing_code:
                    err_msg = f"Code {referral_code} stored in practitioner invite already exists."
                    log.debug(err_msg)
                    alert_admin(
                        err_msg,
                        [PRACTITIONER_SUPPORT_EMAIL],
                        "Practitioner Invite Onboarding Code Error",
                    )
                    abort(400, message=err_msg)

                pp.messaging_enabled = True
                cancellation_policy_name = CancellationPolicyName.default().value
                if pp.active_contract and pp.active_contract.contract_type in [
                    ContractType.HYBRID_1_0,
                    ContractType.HYBRID_2_0,
                ]:
                    cancellation_policy_name = CancellationPolicyName.FLEXIBLE.value
                policy = (
                    db.session.query(CancellationPolicy)
                    .filter(CancellationPolicy.name == cancellation_policy_name)
                    .first()
                )
                if policy:
                    pp.default_cancellation_policy_id = policy.id

                code = ReferralCode(
                    allowed_uses=None,
                    user_id=user.id,
                    expires_at=None,
                    code=referral_code,
                    only_use_before_booking=True,
                )
                ff_code_value = ReferralCodeValue(
                    code=code, for_user_type=ReferralCodeValueTypes.free_forever
                )
                member_code_value = ReferralCodeValue(
                    code=code,
                    value=DEFAULT_MEMBER_VALUE,
                    for_user_type=ReferralCodeValueTypes.member,
                )
                db.session.add_all([code, ff_code_value, member_code_value])

            invite.claimed_at = datetime.utcnow()
            db.session.add_all([invite, pp])

            service_ns_tag = "authentication"
            team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
            from tasks.braze import sync_practitioner_with_braze

            sync_practitioner_with_braze.delay(
                user.id, service_ns=service_ns_tag, team_ns=team_ns_tag
            )

        else:
            log.debug("No practitioner invite for %s", user)

        return user

    CLIENT_ERROR_MESSAGE = (
        "There was an error creating your account, "
        "please make sure you are using a secure password "
        "and that you don't already have an account registered with the same email address or username."
    )

    SERVER_ERROR_MESSAGE = (
        "There was an error creating your account, please try again. "
        "Contact the support team if the error persists."
    )


class UserError(Exception):
    ...


class NoUserFound(UserError):
    ...
