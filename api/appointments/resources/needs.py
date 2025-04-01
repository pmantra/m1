from dataclasses import asdict

from ddtrace import tracer
from flask import request
from flask_restful import abort
from maven import feature_flags
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.exc import NoResultFound

from appointments.models.needs_and_categories import (
    Need,
    NeedTrack,
    NeedVertical,
    need_specialty,
)
from appointments.schemas.needs import NeedsGetResultStruct, NeedsGetSchema
from common.services.api import AuthenticatedResource
from l10n.db_strings.translate import TranslateDBFields
from models.profiles import PractitionerProfile
from storage.connection import db
from utils import launchdarkly
from utils.log import logger

log = logger(__name__)


class NeedsResource(AuthenticatedResource):
    @tracer.wrap()
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Finds needs with matching id, name, or provider in the user's track.
        Returns all of a user's needs if no parameters are given

        Accepts only 1 of the following parameters:
            :param id: the id of a need you are searching for
            :param name: the name of a need you are searching for
            :param provider_id: the id of a provider to find all needs associated with

        :param track_name: filter by this track instead of the user's active track
        """
        args_schema = NeedsGetSchema()
        request_params = args_schema.load(request.args)

        filter_params = list(
            filter(
                None,
                [
                    request_params.get("id"),
                    request_params.get("name"),
                    request_params.get("provider_id"),
                ],
            )
        )
        if len(filter_params) > 1:
            abort(
                400,
                message="Please send only one parameter of the following: id, name, provider_id",
            )

        if "track_name" in request_params:
            track_names = [request_params["track_name"]]
        else:
            track_names = [at.name for at in self.user.active_tracks]

        base_query = (
            db.session.query(Need.id, Need.name, Need.description, Need.slug)
            .join(NeedTrack)
            .filter(
                NeedTrack.track_name.in_(track_names),
            )
            .order_by(
                Need.display_order.is_(None).asc(),
                Need.display_order.asc(),
            )
        )

        if len(request_params) == 0:
            needs = base_query.all()
        elif id := request_params.get("id"):
            needs = base_query.filter(Need.id == id).all()
        elif name := request_params.get("name"):
            needs = base_query.filter(Need.name == name).all()
        elif provider_id := request_params.get("provider_id"):
            try:
                provider = (
                    db.session.query(PractitionerProfile)
                    .filter(PractitionerProfile.user_id == provider_id)
                    .options(
                        joinedload(PractitionerProfile.specialties),
                        joinedload(PractitionerProfile.verticals),
                    )
                    .one()
                )
            except NoResultFound:
                abort(404, "Could not find provider with id {provider_id}")
                return

            provider_specialty_ids = [s.id for s in provider.specialties]
            provider_vertical_ids = [v.id for v in provider.verticals]

            needs = (
                base_query.outerjoin(need_specialty)
                .outerjoin(NeedVertical, Need.id == NeedVertical.need_id)
                .group_by(Need.id)
                .filter(
                    or_(
                        NeedVertical.vertical_id.in_(provider_vertical_ids),
                        NeedVertical.vertical_id == None,
                    ),
                    or_(
                        need_specialty.c.specialty_id.in_(provider_specialty_ids),
                        need_specialty.c.specialty_id == None,
                    ),
                )
                .order_by(Need.name)
                .all()
            )
        # -- End SQL --

        l10n_flag = feature_flags.bool_variation(
            "release-disco-be-localization",
            launchdarkly.user_context(self.user),
            default=False,
        )
        needs_data = []
        for need in needs:
            name = need.name
            description = need.description

            if l10n_flag:
                name = TranslateDBFields().get_translated_need(
                    need.slug, "name", need.name
                )
                description = TranslateDBFields().get_translated_need(
                    need.slug, "description", need.description
                )

            needs_data.append(
                asdict(
                    NeedsGetResultStruct(
                        id=need.id,
                        name=name,
                        description=description,
                    )
                )
            )

        log.info(
            f"{len(needs_data)} need(s) found",
            id=request_params.get("id"),
            name=request_params.get("name"),
            provider_id=request_params.get("provider_id"),
        )
        return {"data": needs_data}
