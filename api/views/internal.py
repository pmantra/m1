from __future__ import annotations

import os
from traceback import format_exc
from typing import Optional

from flask import Response, render_template, request
from flask_restful import abort
from marshmallow_v1 import Schema as SchemaV1
from marshmallow_v1 import fields as fields_v1
from sqlalchemy.orm import contains_eager
from sqlalchemy.orm.query import Query

import configuration
from appointments.models.appointment import Appointment
from braze import (
    BRAZE_ANDROID_API_KEY,
    BRAZE_IOS_API_KEY,
    BRAZE_IOS_MPRACTICE_API_KEY,
    BRAZE_WEB_APP_ID,
    SDK_ENDPOINT,
)
from care_advocates.models.assignable_advocates import AssignableAdvocate
from common.constants import Environment
from common.services.api import AuthenticatedResource, UnauthenticatedResource
from messaging.models.messaging import Message
from models.enterprise import BusinessLead
from models.marketing import IosNonDeeplinkUrl, LibraryContentTypes
from models.profiles import Agreement, AgreementNames
from models.tracks import TrackName
from models.verticals_and_specialties import (
    Vertical,
    VerticalGroup,
    VerticalGroupTrack,
    VerticalGroupVersion,
    vertical_grouping_versions,
)
from storage.connection import db
from utils.braze import ConnectedEvent
from utils.calendar import render_ical
from utils.log import logger
from utils.mail import send_message
from utils.marshmallow_experiment import marshmallow_experiment_enabled
from utils.recaptcha import get_recaptcha_key
from utils.rotatable_token import BRAZE_ATTACHMENT_TOKEN
from views.schemas.common import MavenSchema, V2VerticalSchema
from views.schemas.internal_v3 import AttachmentSchemaV3

log = logger(__name__)

SENTRY_IOS_DSN = os.environ.get("SENTRY_IOS_DSN")
SENTRY_MPRACTICE_IOS_DSN = os.environ.get("SENTRY_MPRACTICE_IOS_DSN")
SENTRY_ANDROID_DSN = os.environ.get("SENTRY_ANDROID_DSN")
SP_EVENTS_TRACKING_URL = os.environ.get("SP_EVENTS_TRACKING_URL")
DATADOG_RUM_APPLICATION_ID_FERTILITY_PORTAL = os.environ.get(
    "DATADOG_RUM_APPLICATION_ID_FERTILITY_PORTAL"
)
DATADOG_RUM_CLIENT_TOKEN_FERTILITY_PORTAL = os.environ.get(
    "DATADOG_RUM_CLIENT_TOKEN_FERTILITY_PORTAL"
)
DATADOG_RUM_APPLICATION_ID_MAVENCORE = os.environ.get(
    "DATADOG_RUM_APPLICATION_ID_MAVENCORE"
)
DATADOG_RUM_CLIENT_TOKEN_MAVENCORE = os.environ.get(
    "DATADOG_RUM_CLIENT_TOKEN_MAVENCORE"
)
DATADOG_RUM_APPLICATION_ID_MPRACTICE = os.environ.get(
    "DATADOG_RUM_APPLICATION_ID_MPRACTICE"
)
DATADOG_RUM_CLIENT_TOKEN_MPRACTICE = os.environ.get(
    "DATADOG_RUM_CLIENT_TOKEN_MPRACTICE"
)
DATADOG_RUM_APPLICATION_ID_MESSAGES = os.environ.get(
    "DATADOG_RUM_APPLICATION_ID_MESSAGES"
)
DATADOG_RUM_CLIENT_TOKEN_MESSAGES = os.environ.get("DATADOG_RUM_CLIENT_TOKEN_MESSAGES")


class MetadataResource(UnauthenticatedResource):
    def get(self) -> dict:
        config = configuration.get_api_config()

        try:
            cx_practitioner_id = int(os.environ.get("CS_PRACTITIONER_ID", 0))
        except (TypeError, ValueError):
            cx_practitioner = AssignableAdvocate.default_care_coordinator()
            cx_practitioner_id = cx_practitioner.id if cx_practitioner else 0

        return {
            "stripe_publishable_key": os.environ.get("STRIPE_PUBLISHABLE_KEY", ""),
            "stripe_publishable_key_reimbursements": os.environ.get(
                "STRIPE_PUBLISHABLE_KEY_REIMBURSEMENTS", ""
            ),
            "tokbox_api_key": os.environ.get("OPENTOK_API_KEY", ""),
            "ziggeo_account_id": os.environ.get(
                "ZIGGEO_API_KEY", "e7f2538976d49815ede1ac4d3c1cdfbb"
            ),
            "platform_data": {
                "ios": {
                    "practitioner": "202411.1.0",
                    "patient": "202411.1.0",
                    "version": "",
                },
                "android": {
                    "version": "40439",
                },
            },
            "sp_events_tracking_url": SP_EVENTS_TRACKING_URL or "",
            "messaging_member_character_limit": Message.MAX_CHARS,
            "default_college_vertical_group": "college",
            "cx_practitioner_id": cx_practitioner_id,
            "content_types": [
                {"name": c.name, "display_name": c.value} for c in LibraryContentTypes
            ],
            "asset_content_length_limit": config.asset_content_length_limit,
            "recaptcha_site_key": get_recaptcha_key() or "",
            "environment": Environment.current().name or "",
            "launchdarkly_mobile_key": os.environ.get("LAUNCHDARKLY_MOBILE_KEY", ""),
            "launchdarkly_client_side_id": os.environ.get(
                "LAUNCHDARKLY_CLIENT_SIDE_ID", ""
            ),
        }


class VendorMetadataResource(UnauthenticatedResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return {
            "braze": {
                "android_api_key": BRAZE_ANDROID_API_KEY,
                "ios_api_key": BRAZE_IOS_API_KEY,
                "ios_mpractice_api_key": BRAZE_IOS_MPRACTICE_API_KEY,
                "web_api_key": BRAZE_WEB_APP_ID,
                "sdk_url": SDK_ENDPOINT,
                "ios_sdk_url": SDK_ENDPOINT,
                "web_sdk_url": SDK_ENDPOINT,
            },
            "sentry": {
                "ios_dsn": SENTRY_IOS_DSN,
                "ios_mpractice_dsn": SENTRY_MPRACTICE_IOS_DSN,
                "android_dsn": SENTRY_ANDROID_DSN,
            },
            "datadog_rum": {
                "fertility_portal_application_id": DATADOG_RUM_APPLICATION_ID_FERTILITY_PORTAL,
                "fertility_portal_client_token": DATADOG_RUM_CLIENT_TOKEN_FERTILITY_PORTAL,
                "mavencore_application_id": DATADOG_RUM_APPLICATION_ID_MAVENCORE,
                "mavencore_client_token": DATADOG_RUM_CLIENT_TOKEN_MAVENCORE,
                "mpractice_application_id": DATADOG_RUM_APPLICATION_ID_MPRACTICE,
                "mpractice_client_token": DATADOG_RUM_CLIENT_TOKEN_MPRACTICE,
                "messages_application_id": DATADOG_RUM_APPLICATION_ID_MESSAGES,
                "messages_client_token": DATADOG_RUM_CLIENT_TOKEN_MESSAGES,
            },
        }


class PractitionerServiceAgreementResource(AuthenticatedResource):
    def get(self, version_number):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        agreement = self._get_agreement(version_number)
        if not agreement:
            abort(404, message="Agreement Not Found")
        return {"agreement": agreement.html}

    def _get_agreement(self, version_number=1):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if version_number == 0:
            return (
                db.session.query(Agreement)
                .filter(Agreement.name == AgreementNames.SERVICE)
                .order_by(Agreement.version.desc())
                .first()
            )
        else:
            return (
                db.session.query(Agreement)
                .filter(
                    Agreement.name == AgreementNames.SERVICE,
                    Agreement.version == version_number,
                )
                .first()
            )


class VerticalSchema(SchemaV1):
    name = fields_v1.String()
    pluralized_display_name = fields_v1.String()
    id = fields_v1.Integer()


class SpecialtySchema(SchemaV1):
    id = fields_v1.Integer()
    name = fields_v1.String()
    image_url = fields_v1.Method("get_image_url")

    def get_image_url(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return obj.image_url()


class VerticalGroupingsResource(AuthenticatedResource):
    def get_vertical_response(self, verticals: list[Vertical]) -> dict:
        return [  # type: ignore[return-value] # Incompatible return value type (got "List[Dict[str, object]]", expected "Dict[Any, Any]")
            {
                "name": vertical.name,
                "pluralized_display_name": vertical.pluralized_display_name,
                "id": vertical.id,
            }
            for vertical in verticals
        ]

    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        groups = (
            db.s_replica1.query(VerticalGroup)
            .join(vertical_grouping_versions)
            .join(VerticalGroupVersion)
            .filter(VerticalGroupVersion.name == "v1")
            .all()
        )

        schema = VerticalSchema()
        verticals = {}
        for group in groups:
            verticals[group.name] = schema.dump(group.verticals, many=True).data
        try:
            python_response = {
                group.name: self.get_vertical_response(group.verticals)
                for group in groups
            }
            if python_response == verticals:
                log.info("FM - VerticalGroupingsResource identical")
            else:
                log.info(
                    "FM - VerticalGroupingsResource diff",
                    python_response=str(python_response),
                    marshmallow_response=str(verticals),
                )
        except Exception:
            log.info("FM - VerticalGroupingsResource error", traces=format_exc())
        return verticals


class V2VerticalGroupSchema(SchemaV1):
    name = fields_v1.String()
    title = fields_v1.String()
    description = fields_v1.String()
    image_url = fields_v1.Method("get_image_url")
    hero_image_url = fields_v1.Method("get_hero_image_url")
    verticals = fields_v1.Method("get_verticals")
    specialties = fields_v1.Nested(SpecialtySchema, many=True)

    def get_image_url(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return obj.image_url()

    def get_hero_image_url(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return obj.hero_image and obj.hero_image.asset_url()

    def get_verticals(self, obj, context):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            V2VerticalSchema()
            .dump([v for v in obj.verticals if v.practitioners], many=True)
            .data
        )


class V2VerticalGroupingsResource(AuthenticatedResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        schema = V2VerticalGroupSchema()
        if request.args.get("version"):
            groups = vertical_groups_by_version(request.args["version"])
        else:
            # TODO: [multitrack] Combine all vertical groups for all of
            #  user.active_tracks?
            groups = vertical_groups_by_track(
                self.user.current_member_track and self.user.current_member_track.name
            )

        return schema.dump(groups, many=True).data


class EmailBizLeadsEndpoint(UnauthenticatedResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        request_json = request.json if request.is_json else None
        if request_json.get("email"):
            lead = BusinessLead(json=request_json)
            db.session.add(lead)
            db.session.commit()

        try:
            send_message(
                "mavenforbusiness@mavenclinic.com",
                "New Lead via Website!",
                text=str(request_json),
                internal_alert=True,
            )
        except Exception as e:
            log.info("Could not send lead - info is: %s", request_json, exception=e)


def vertical_groups_by_track(
    track_name: Optional[TrackName], eager_load_data: bool = True
) -> Query[VerticalGroup]:
    if track_name is None:
        return vertical_groups_by_version("v2", eager_load_data)
    return (
        _user_vertical_groups_base_query(eager_load_data)
        .join(VerticalGroupTrack)
        .filter(VerticalGroupTrack.track_name == track_name)
    )


def vertical_groups_by_version(version, eager_load_data=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return _user_vertical_groups_base_query(eager_load_data).filter(
        VerticalGroupVersion.name == version
    )


def _user_vertical_groups_base_query(eager_load_data):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    query = db.s_replica1.query(VerticalGroup).outerjoin(VerticalGroup.versions)
    if eager_load_data:
        query = (
            query.outerjoin(VerticalGroup.verticals, Vertical.practitioners)
            .filter(Vertical.deleted_at == None)
            .options(
                contains_eager(VerticalGroup.verticals).contains_eager(
                    Vertical.practitioners
                )
            )
            # the previous implementation of
            # "-VerticalGroup.ordering_weight.desc()"
            # caused sql syntax errors when others leveraged eager joins.
            # The query goal is to have the ordering_weight smallest to largest
            # with nulls last.
            .order_by(
                VerticalGroup.ordering_weight.is_(None),
                VerticalGroup.ordering_weight.asc(),
            )
        )
    return query


class AttachmentSchema(MavenSchema):
    token = fields_v1.String(required=True)


class BrazeAttachmentResource(UnauthenticatedResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        experiment_enabled = marshmallow_experiment_enabled(
            "experiment-marshmallow-braze-attachment-upgrade",
            self.user.esp_id if self.user else None,
            self.user.email if self.user else None,
            default=False,
        )

        data = (
            AttachmentSchemaV3().load(request.args)
            if experiment_enabled
            else AttachmentSchema().load(request.args).data
        )
        token = data["token"]

        result = BRAZE_ATTACHMENT_TOKEN.decode(token)
        if not result or "appointment_id" not in result:
            return "Invalid token", 400

        appointment = Appointment.query.get(result["appointment_id"])

        description = render_template(
            "ics/member_appointment_description.j2",
            practitioner_name=appointment.practitioner.full_name,
        )

        ical = render_ical(
            appointment.id,
            appointment.practitioner.full_name,
            appointment.scheduled_start,
            appointment.scheduled_end,
            description,
        )

        return Response(
            ical,
            mimetype="text/calendar",
            headers={
                "Content-disposition": "attachment; filename=maven_appointment.ics"
            },
        )


class BrazeConnectedEventPropertiesResource(UnauthenticatedResource):
    @classmethod
    def get(cls, connected_event_token):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return ConnectedEvent.event_properties_from_token(connected_event_token)


class IosNonDeeplinkUrlsResource(UnauthenticatedResource):
    """
    Get the list of urls which the iOS app should not try to open as a deeplink.
    """

    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        return IosNonDeeplinkUrl.all()
