import os
import time
from typing import List

from maven import feature_flags
from structlog.stdlib import BoundLogger

from authn.domain.model import OrganizationAuth
from authn.domain.service import MFAService
from authn.util.constants import (
    COMPANY_MFA_SYNC_LAUNCH_DARKLY_CONTEXT_NAME,
    COMPANY_MFA_SYNC_LAUNCH_DARKLY_KEY,
)
from messaging.services.zendesk import EnterpriseValidationZendeskTicket
from storage.connection import db
from tasks.helpers import get_user
from tasks.queues import job
from utils import braze
from utils.log import logger

log: BoundLogger = logger(__name__)


CENSUS_FILE_KEK = os.environ.get("CENSUS_FILE_KEK")
CENSUS_FILE_SIG_KEY = os.environ.get("CENSUS_FILE_SIG_KEY")


@job(team_ns="enrollments")
def enterprise_user_post_setup(user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.info("Initiating enterprise_user_post_setup", user_id=user_id)
    user = get_user(user_id)
    if user:
        braze.track_user(user)
        if user.organization:
            braze.send_incentives_allowed(
                external_id=user.esp_id,
                welcome_box_allowed=user.organization.welcome_box_allowed,
                gift_card_allowed=user.organization.gift_card_allowed,
            )
        # TODO: [multitrack]: Figure out a different message here that doesn't use
        #  current_member_track
        message = "User was successfully associated to an organization."
        if user.member_tracks:
            message += " User was successfully enrolled in a track."
        EnterpriseValidationZendeskTicket.solve(
            user,
            message,
        )
        db.session.commit()


def update_organization_all_users_company_mfa(
    org_id: int, mfa_required: bool, chunk_size: int = 400
) -> None:
    log.info("Initiating update company user MFA data")
    is_company_mfa_lts = feature_flags.bool_variation(
        COMPANY_MFA_SYNC_LAUNCH_DARKLY_KEY,
        feature_flags.Context.create(COMPANY_MFA_SYNC_LAUNCH_DARKLY_CONTEXT_NAME),
        default=False,
    )
    if not is_company_mfa_lts:
        log.info(f"Feature flag is not enabled for org {org_id}")
        return

    log.info(f"Org Id is {org_id} and mfa require status is {mfa_required}")
    # scan member track table
    # for each record, check the org id. If it is matched, update the member mfa status
    from tracks import TrackSelectionService

    member_track_svc = TrackSelectionService()

    to_be_updated_users = member_track_svc.get_users_by_org_id(org_id=org_id)
    if not to_be_updated_users:
        log.error(f"to_be_updated_users is None for org {org_id}")
        return
    log.info(
        f"Will sync {len(to_be_updated_users)} user mfa data due to company mfa change"
    )

    for i in range(0, len(to_be_updated_users), chunk_size):
        log.info(f"Processing the elements in the list from {i} to {i + chunk_size}")
        sliced_users = [to_be_updated_users[i : i + chunk_size]]
        update_organization_all_users_company_mfa_job.delay(sliced_users, mfa_required)


@job(team_ns="authentication")
def update_organization_all_users_company_mfa_job(
    to_be_updated_users: List[tuple], mfa_required: bool
) -> None:
    for target_user in to_be_updated_users:
        user_id = target_user[0]
        log.info(f"user id is [{user_id}], mfa required is [{mfa_required}]")
        mfa_service = MFAService()
        idp_sms_phone_number = mfa_service.update_user_company_mfa_to_auth0(
            user_id=user_id, is_company_mfa_required=mfa_required
        )
        if mfa_required:
            # Sync data to Maven DB only when org mfa is required
            if user_id and idp_sms_phone_number:
                try:
                    mfa_service.update_mfa_status_and_sms_phone_number(
                        user_id=user_id,
                        sms_phone_number=idp_sms_phone_number,
                        is_enable=True,
                    )
                    log.info(
                        f"Successfully enable MFA in Maven DB for user {user_id} due to company mfa required"
                    )
                except Exception as e:
                    log.error(
                        f"Failed update the user's MFA status and sms_phone_number due to error in maven db update: {e}"
                    )
            else:
                log.error(
                    f"Failed update the user MFA status and sms phone number due to failed fetch sms phone "
                    f"number for user {user_id} from idp"
                )
        else:
            # We don't update DB at this moment. Because when the user is MFA enabled, the DB will set to true. And it also impacts the user MFA level.
            # We need user to manually disable the MFA from account settings.
            log.info("company is not mfa required")
        # sleep to avoid throttling
        time.sleep(1)


@job(team_ns="authentication")
def update_single_user_company_mfa(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    user_id: int, org_id: int = None, is_terminate: bool = False  # type: ignore[assignment] # Incompatible default for argument "org_id" (default has type "None", argument has type "int")
):
    mfa_service = MFAService()

    if is_terminate:
        log.info(
            f"{user_id} is terminating the member track. Change company mfa required to False"
        )
        mfa_service.update_user_company_mfa_to_auth0(
            user_id=user_id, is_company_mfa_required=False
        )
    else:
        log.info(
            f"{user_id} is initializing the member track for org {org_id}. Update the company mfa required based on the organization requirement"
        )
        is_org_mfa_required = False
        org_auth: OrganizationAuth = (
            mfa_service.organization_auth.get_by_organization_id(organization_id=org_id)
        )
        if org_auth:
            is_org_mfa_required = org_auth.mfa_required

        idp_sms_phone_number = mfa_service.update_user_company_mfa_to_auth0(
            user_id=user_id, is_company_mfa_required=is_org_mfa_required
        )
        if is_org_mfa_required:
            # Sync data to Maven DB only when org mfa is required
            if user_id and idp_sms_phone_number:
                try:
                    mfa_service.update_mfa_status_and_sms_phone_number(
                        user_id=user_id,
                        sms_phone_number=idp_sms_phone_number,
                        is_enable=True,
                    )
                    log.info(
                        f"Successfully enable MFA in Maven DB for user {user_id} due to company mfa required"
                    )
                except Exception as e:
                    log.error(
                        f"Failed update the user's MFA status and sms_phone_number due to error in maven db update: {e}"
                    )
            else:
                log.error(
                    f"Failed update the user MFA status and sms phone number due to failed fetch sms phone "
                    f"number for user {user_id} from idp"
                )
        else:
            # It is in the initializing, if the user is not company MFA required, we do nothing
            log.info(f"User {user_id} in organization {org_id} is not mfa required")
