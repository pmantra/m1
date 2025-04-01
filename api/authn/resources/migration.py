import json
from datetime import datetime
from typing import Any

from flask import make_response, request
from flask_restful import abort

from authn.domain.service import get_auth_service, get_sso_service, get_user_service
from authn.util.constants import DATE_FORMAT
from common.services import ratelimiting
from common.services.api import InternalServiceResource
from storage.connection import db
from utils.log import logger
from views.schemas.base import StringWithDefaultV3
from views.schemas.common import MavenSchema
from wheelhouse.marshmallow_v1.marshmallow_v1.exceptions import ValidationError

log = logger(__name__)


class RetrievalAuthnDataSchema(MavenSchema):
    end_time = StringWithDefaultV3(required=True)
    start_time = StringWithDefaultV3(required=False)


class UpsertAuthnDataSchema(MavenSchema):
    table_name = StringWithDefaultV3(required=True)
    operation = StringWithDefaultV3(required=True)
    src_data = StringWithDefaultV3(
        required=True
    )  # The data should be in json string format


class RetrievalAuthnDataResource(InternalServiceResource):
    @ratelimiting.ratelimited(attempts=30, cooldown=(60 * 10), reset_on_success=True)
    def get(self, name):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        end_time = datetime.strptime(str(request.args.get("end_time")), DATE_FORMAT)
        start_time = (
            datetime.strptime(str(request.args.get("start_time")), DATE_FORMAT)
            if request.args.get("start_time")
            else None
        )
        data: list[Any] = []
        session = db.session
        user_svc = get_user_service(session=session)
        auth_svc = get_auth_service()
        sso_svc = get_sso_service(session=session)
        if name == "user":
            data = user_svc.get_all_by_time_range(end=end_time, start=start_time)
        elif name == "user_auth":
            data = auth_svc.get_user_auth_by_time_range(end=end_time, start=start_time)
        elif name == "uei":
            data = sso_svc.get_identities_by_time_range(start=start_time, end=end_time)
        elif name == "org_auth":
            data = auth_svc.get_org_auth_by_time_range(end=end_time, start=start_time)
        elif name == "identity_provider":
            data = sso_svc.get_idps_by_time_range(end=end_time, start=start_time)
        else:
            log.warning(f"Unsupported table {name}", table_name=name)

        if data:
            log.info(
                f"The size of the authn data for {name} is {len(data)}", table_name=name
            )
        else:
            log.info("data is None", table_name=name)

        return make_response({"data": data}, 200)


class UpsertAuthnDataResource(InternalServiceResource):
    @ratelimiting.ratelimited(attempts=30, cooldown=(60 * 10), reset_on_success=True)
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        request_json = request.json if request.is_json else None
        if not request_json:
            abort(400, message="Missing payload")
        args_schema = UpsertAuthnDataSchema()
        try:
            args: dict = args_schema.load(request_json)
        except ValidationError as e:
            return {"message": e.messages}, 400
        table_name: str = args.get("table_name", "")
        operation: str = args.get("operation", "")
        src_data: str = args.get("src_data", "")  # it is json string
        data: dict = json.loads(src_data)

        session = db.session
        user_svc = get_user_service(session=session)
        auth_svc = get_auth_service()
        sso_svc = get_sso_service(session=session)

        if table_name == "user":
            if operation == "create":
                # create the record
                log.info(f"create record for table {table_name}")
                user_svc.insert_user_data_from_authn_api(data=data)
            elif operation == "update":
                # update the record
                log.info(f"update record for table {table_name}")
                user_svc.update_user_data_from_authn_api(data=data)
            else:
                log.warning("Unsupported operation")
        elif table_name == "user_auth":
            if operation == "create":
                # create the record
                log.info(f"create record for table {table_name}")
                auth_svc.insert_user_auth_data_from_authn_api(data=data)
            elif operation == "update":
                # update the record
                log.info(f"update record for table {table_name}")
                auth_svc.update_user_auth_data_from_authn_api(data=data)
            else:
                log.warning("Unsupported operation")
        elif table_name == "uei":
            if operation == "create":
                # create the record
                log.info(f"create record for table {table_name}")
                sso_svc.insert_uei_data_from_authn_api(data=data)
            elif operation == "update":
                # update the record
                log.info(f"update record for table {table_name}")
                sso_svc.update_uei_data_from_authn_api(data=data)
            else:
                log.warning("Unsupported operation")
        elif table_name == "org_auth":
            if operation == "create":
                # create the record
                log.info(f"create record for table {table_name}")
                auth_svc.insert_org_auth_data_from_authn_api(data=data)
            elif operation == "update":
                # update the record
                log.info(f"update record for table {table_name}")
                auth_svc.update_org_auth_data_from_authn_api(data=data)
            else:
                log.warning("Unsupported operation")
        elif table_name == "identity_provider":
            if operation == "create":
                # create the record
                log.info(f"create record for table {table_name}")
                sso_svc.insert_identity_provider_data_from_authn_api(data=data)
            elif operation == "update":
                # update the record
                log.info(f"update record for table {table_name}")
                sso_svc.update_identity_provider_data_from_authn_api(data=data)
            else:
                log.warning("Unsupported operation")
        else:
            log.warning(f"Unsupported table {table_name}")

        if data:
            log.info(f"The size of the authn data for {table_name} is {len(data)}")
        else:
            log.info("data is None")

        return make_response({"data": data}, 200)
