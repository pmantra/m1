from flask import request
from flask_restful import abort
from sqlalchemy.exc import SQLAlchemyError

from common.services.api import UnauthenticatedResource
from models.advertising import ATTRIBUTION_ID_TYPES, UserInstallAttribution
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class MATPostbackResource(UnauthenticatedResource):
    # No longer used according to DataDog
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        _mat = request.args

        new_install = UserInstallAttribution(
            user_id=None,
            device_id=_mat["mat_ios_ifa"],
            id_type=ATTRIBUTION_ID_TYPES.apple_ifa,
            json=_mat,
        )
        db.session.add(new_install)

        try:
            db.session.commit()
        except SQLAlchemyError:
            log.info("Problem saving new_install for MAT!")
            log.debug("MAT data: %s", _mat)
            log.debug("Headers: %s", request.headers)
            abort(400)
        else:
            log.debug("Added %s", new_install)

        return ""
