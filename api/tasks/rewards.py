import os
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional

import requests
from google.cloud import bigquery
from google.oauth2 import service_account
from requests.auth import HTTPDigestAuth
from sqlalchemy.orm.exc import NoResultFound

import eligibility
from authn.models.user import User
from eligibility.e9y import EligibilityVerification
from models.enterprise import (
    ExternalIDPNames,
    OrganizationExternalID,
    OrganizationRewardsExport,
)
from storage.connection import db
from utils.log import logger

log = logger(__name__)

from tasks.queues import job

CASTLIGHT_URL = os.environ.get("CASTLIGHT_API_URL")
CASTLIGHT_PASSWORD = os.environ.get("CASTLIGHT_API_PASSWORD")

BQ_EXPORT_PROJECT = os.environ.get("BIGQUERY_EXPORT_PROJECT", None)
BQ_CREDS_PATH = os.environ.get("BIGQUERY_CREDENTIALS_PATH", None)
BQ_CREDS = BQ_CREDS_PATH and service_account.Credentials.from_service_account_file(
    filename=BQ_CREDS_PATH
)


class CastlightActivities(Enum):
    AppDownload = "downloadComplete"
    IntroAppointment = "introComplete"
    AccountCreation = "accountComplete"
    PractitionerComplete = "practitionerComplete"


class WelltokActivities(Enum):
    AppDownload = "HARTMAVDL"
    IntroAppointment = "HARTMAVAP"
    AccountCreation = "HARTMAVAC"
    PractitionerComplete = "HARTMAVPA"


class ActivityIdPrefix(Enum):
    AppDownload = 1
    IntroAppointment = 2
    AccountCreation = 3
    PractitionerComplete = 4


class CastlightDependentTypes(Enum):
    Dependent = "OTHER"
    Self = "SELF"


def _format_castlight_activity(event):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    try:
        activity_name = CastlightActivities[event.event_type].value
        user = db.session.query(User).filter(User.id == event.user_id).one()
        if not user.is_enterprise:
            log.warning(
                "Skipping non-enterprise user reward.",
                user_id=user.id,
                activity=event.event_type,
            )
            return None

        person_identifier = _format_castlight_person_identifier(user)
        partner_activity_id_prefix = ActivityIdPrefix[event.event_type].value
        partner_activity_id = f"{partner_activity_id_prefix}{user.id}"
        date_of_activity = event.event_date
        log.info(
            "Event Prepped to Send", user_id=user.id, activity_type=event.event_type
        )

        return {
            "schemaName": "maven",
            "personIdentifier": person_identifier,
            "partnerActivityId": partner_activity_id,
            "activityData": {
                "maven": {
                    "mavenClinic": {
                        activity_name: {
                            "dateOfActivity": date_of_activity.strftime("%Y-%m-%d"),
                            "activityPerformed": True,
                        }
                    }
                }
            },
        }
    except KeyError:
        log.error(
            "Couldn't find CastlightActivity for event", event_type=event.event_type
        )
        return None
    except NoResultFound as e:
        log.error("No result found in db", err=e, user_id=event.user_id)


def _format_castlight_person_identifier(user: User) -> Dict[str, str]:
    org = user.organization_v2
    if not org:
        log.error("User not associated with an organization", user_id=user.id)
        return {}
    org_id = org.id
    external_id_instance = (
        db.session.query(OrganizationExternalID)
        .filter(
            OrganizationExternalID.organization_id == org_id,
            OrganizationExternalID.idp == ExternalIDPNames.CASTLIGHT,
        )
        .one_or_none()
    )

    unique_corp_id = None
    verification = _get_verification_for_user_and_org(
        user_id=user.id,
        organization_id=org_id,
        method="_format_castlight_person_identifier",
    )
    if verification:
        unique_corp_id = verification.unique_corp_id

    if _is_dependent(user=user, verification=verification):
        return {
            "employerKey": external_id_instance and external_id_instance.external_id,
            "subscriberEmployeeId": unique_corp_id,
            "dependentType": CastlightDependentTypes.Dependent.value,
            "firstName": user.first_name,
        }

    return {
        "employerKey": external_id_instance and external_id_instance.external_id,
        "uniqueUserId": unique_corp_id,
    }


def _get_verification_for_user_and_org(
    user_id: int, organization_id: int, method: str
) -> Optional[EligibilityVerification]:
    svc = eligibility.EnterpriseVerificationService()
    verification = svc.get_verification_for_user_and_org(
        user_id=user_id, organization_id=organization_id
    )
    if verification is None:
        log.warning(
            "No verification found for user and org",
            user_id=user_id,
            org_id=organization_id,
            method=method,
        )
    return verification


def _is_dependent(user: User, verification: Optional[EligibilityVerification]) -> bool:
    """We have to check both the member_track.is_employee field and the
    verification.dependent_id, as both fields are unreliable. If either
    field denotes a dependent status, then we assume that the user is a dependent.
    """
    newest_user_track = user.active_tracks[-1]
    track_is_dependent = not newest_user_track.is_employee
    verification_dependent_id = (
        verification.dependent_id.strip()
        if verification and verification.dependent_id
        else None
    )
    return bool(track_is_dependent or verification_dependent_id)


def _format_castlight_payload(events):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    activities = [_format_castlight_activity(e) for e in events]
    activities = [a for a in activities if a is not None]
    return {"partnerId": "Maven", "activities": activities}


def _build_query(org_id, last_report):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return f"""
    WITH cast_light_latest_snapshot AS (
        SELECT 
            user_id,
            event_type,
            event_date
        FROM  `{BQ_EXPORT_PROJECT}.dbt_levels_tainted.castlight_incentives_snapshot`
        WHERE organization_id = {org_id} 
        )
    SELECT 
        user_id,
        event_type,
        MIN(event_date) AS event_date
    FROM cast_light_latest_snapshot
    WHERE event_date >= "{last_report.strftime("%Y-%m-%d")}"
    GROUP BY 1, 2
    ORDER BY event_type
    """


def load_events_from_big_query(org_id, last_report):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    client = bigquery.Client(project=BQ_EXPORT_PROJECT, credentials=BQ_CREDS)
    query_job = client.query(_build_query(org_id, last_report.date()))

    return query_job.result()


def send_events_to_castlight(events, org_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if not CASTLIGHT_URL or not CASTLIGHT_PASSWORD:
        log.warning("No Castlight URL or Password Provided, skipping sending rewards")
        return False

    body = _format_castlight_payload(events)
    log.info(f"{len(body['activities'])} records ready to send Castlight")
    auth = HTTPDigestAuth("maven", CASTLIGHT_PASSWORD)

    res = requests.post(
        CASTLIGHT_URL,
        json=body,
        auth=auth,
        headers={"x-partner-id": os.environ.get("CASTLIGHT_PARTNER_ID", None)},
    )
    log.info(
        "Records sent to Castlight", org_id=org_id, num_records=len(body["activities"])
    )
    return res


@job(traced_parameters=("ext_id",))
def send_rewards_to_castlight_for_org(ext_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    org_id = (
        db.session.query(OrganizationExternalID.organization_id)
        .filter(OrganizationExternalID.id == ext_id)
        .scalar()
    )
    last_reward_timestamp = (
        db.session.query(OrganizationRewardsExport.created_at)
        .filter(OrganizationExternalID.id == ext_id)
        .order_by(OrganizationRewardsExport.created_at.desc())
        .limit(1)
        .scalar()
    ) or datetime(2000, 1, 1)
    events = load_events_from_big_query(
        org_id, last_reward_timestamp - timedelta(days=1)
    )
    if events.total_rows < 1:
        return

    log.info(
        "Got events for submission to castlight",
        event_count=events.total_rows,
        org_id=org_id,
    )
    result = send_events_to_castlight(events, org_id)
    if result.status_code == 202:
        log.info("Full Submission Complete", org_id=org_id)
        db.session.add(OrganizationRewardsExport(organization_external_id_id=ext_id))
        db.session.commit()

    else:
        failed_records = result.json()["failedRecords"]
        log.warning(
            "Castlight Rewards Submission Had Errors",
            count_submitted=events.total_rows,
            count_error=len(failed_records),
            org_id=org_id,
        )
        for record in failed_records:
            log.warning("Castlight Reward Error", failed_record=record, org_id=org_id)


@job
def send_rewards_to_castlight():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # Org External IDs (to opt into Castlight
    arc_best = 25
    warner_brothers = 156
    loreal_usa = 5
    sal_loreal = 2248
    tra_loreal = 2247
    castlight_external_ids = [
        arc_best,
        warner_brothers,
        loreal_usa,
        sal_loreal,
        tra_loreal,
    ]
    for external_id in castlight_external_ids:
        send_rewards_to_castlight_for_org.delay(external_id, team_ns="data")
