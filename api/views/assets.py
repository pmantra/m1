import os
from collections import namedtuple
from urllib.parse import urljoin

import ddtrace
from flask import Request, current_app, request
from flask_restful import abort
from marshmallow_v1.exceptions import UnmarshallingError
from marshmallow_v1.fields import Enum, Integer, String
from marshmallow_v1.validate import Length, Range
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import load_only
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.exceptions import RequestEntityTooLarge

import configuration
from authn.models.user import User
from common import stats
from common.services.api import AuthenticatedResource, UnauthenticatedResource
from models.enterprise import UserAsset, UserAssetState
from storage.connection import db
from tasks.assets import complete_upload
from utils.constants import (
    ASSET_CREATION_COMPLETE_METRIC,
    ASSET_CREATION_ERROR_METRIC,
    ASSET_GET_ERROR_METRIC,
    ASSET_UPLOAD_CANCELLED_METRIC,
)
from utils.error_handler import retry_action
from utils.log import LogLevel, generate_user_trace_log, logger
from utils.service_owner_mapper import service_ns_team_mapper
from views.schemas.common import (
    MavenSchema,
    WithDefaultsSchema,
    format_json_as_error,
    from_unmarshalling_error,
)

log = logger(__name__)


class AssetsResource(AuthenticatedResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """Creates an asset entity that's ready to accept an upload."""
        schema = AssetPostSchema()
        try:
            args = schema.load(request.json if request.is_json else {}).data

            asset = UserAsset(
                state=UserAssetState.UPLOADING,
                file_name=args["file_name"],
                content_type="application/octet-stream",
                content_length=args["content_length"],
                user_id=self.user.id,
            )
            db.session.add(asset)
            db.session.commit()
        except UnmarshallingError as e:
            generate_user_trace_log(
                log,
                LogLevel.WARNING,
                self.user.id,
                f"{AssetPostSchema.__name__} failed validation",
                exception_type=e.__class__.__name__,
                exception_message=str(e),
            )

            stats.increment(
                metric_name=ASSET_CREATION_ERROR_METRIC,
                tags=["reason:UnmarshallingError"],
                pod_name=stats.PodNames.VIRTUAL_CARE,
            )

            return from_unmarshalling_error(e)
        except SQLAlchemyError as e:
            generate_user_trace_log(
                log,
                LogLevel.WARNING,
                self.user.id,
                "DB operation error at AssetsResource.post",
                exception_type=e.__class__.__name__,
                exception_message=str(e),
            )
            stats.increment(
                metric_name=ASSET_CREATION_ERROR_METRIC,
                tags=["reason:DBError"],
                pod_name=stats.PodNames.VIRTUAL_CARE,
            )
            return _db_error()

        generate_user_trace_log(
            log,
            LogLevel.INFO,
            self.user.id,
            "Created user asset",
            asset_id=asset.external_id,
        )

        stats.increment(
            metric_name=ASSET_CREATION_COMPLETE_METRIC,
            pod_name=stats.PodNames.VIRTUAL_CARE,
        )

        return _uploading_data(asset)


class AssetResource(AuthenticatedResource):
    def get(self, asset_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            """Fetches the state of a given asset."""
            asset = (
                UserAsset.query.options(load_only("user_id", "state"))
                .filter_by(id=asset_id)
                .one_or_none()
            )

            if asset is None:
                generate_user_trace_log(
                    log,
                    LogLevel.WARNING,
                    self.user.id,
                    "Could not find asset by id",
                    asset_id=str(asset_id),
                )

                stats.increment(
                    metric_name=ASSET_GET_ERROR_METRIC,
                    tags=["reason:NotFound"],
                    pod_name=stats.PodNames.VIRTUAL_CARE,
                )
                return _not_found(asset_id)

            if not (asset.user_id == self.user.id):
                generate_user_trace_log(
                    log,
                    LogLevel.WARNING,
                    self.user.id,
                    "Cannot poll asset state owned by another user",
                    asset_id=asset.external_id,
                    asset_user_id=asset.user_id,
                )

                stats.increment(
                    metric_name=ASSET_GET_ERROR_METRIC,
                    tags=["reason:OwnedByAnotherUser"],
                    pod_name=stats.PodNames.VIRTUAL_CARE,
                )
                return _get_state_forbidden()

            log.debug(
                "Polling asset state.", user_id=self.user.id, asset_id=asset.external_id
            )
            return _asset_state(asset)

        except SQLAlchemyError as e:
            generate_user_trace_log(
                log,
                LogLevel.WARNING,
                self.user.id,
                "DB operation error at AssetResource.get",
                exception_type=e.__class__.__name__,
                exception_message=str(e),
            )
            stats.increment(
                metric_name=ASSET_GET_ERROR_METRIC,
                tags=["reason:DBError"],
                pod_name=stats.PodNames.VIRTUAL_CARE,
            )
            return _db_error()


class AssetUploadResource(AuthenticatedResource):
    FileRetrievalResult = namedtuple("FileRetrievalResult", ["is_successful", "result"])

    @ddtrace.tracer.wrap()
    def _get_invalid_asset_result(self, asset, asset_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if asset is None:
            generate_user_trace_log(
                log,
                LogLevel.WARNING,
                self.user.id,
                "Could not find asset by id",
                asset_id=str(asset_id),
            )
            return _not_found(asset_id)

        if not (asset.user_id == self.user.id):
            generate_user_trace_log(
                log,
                LogLevel.WARNING,
                self.user.id,
                "Cannot upload contents for asset owned by another user",
                asset_id=asset.external_id,
                asset_user_id=asset.user_id,
            )
            return _upload_forbidden()

        if asset.in_terminal_state():
            generate_user_trace_log(
                log,
                LogLevel.WARNING,
                self.user.id,
                "Cannot upload contents for asset in terminal state",
                asset_id=asset.external_id,
                asset_state=asset.state.value,
            )
            return _upload_state_conflict()

    @ddtrace.tracer.wrap()
    def _get_files_from_request(self, request: Request) -> dict:
        files = request.files
        return files

    @ddtrace.tracer.wrap()
    def _get_file_from_request(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, asset_external_id, asset_upload_request
    ) -> FileRetrievalResult:
        try:
            files = self._get_files_from_request(asset_upload_request)
        except RequestEntityTooLarge as e:
            generate_user_trace_log(
                log,
                LogLevel.WARNING,
                self.user.id,
                "Asset contents upload exceeded request size limit",
                asset_id=asset_external_id,
                exception=e,
            )
            return AssetUploadResource.FileRetrievalResult(
                False, _upload_entity_too_large()
            )

        if "file" in asset_upload_request.form:
            generate_user_trace_log(
                log,
                LogLevel.WARNING,
                self.user.id,
                "Contents uploaded without Content-Disposition filename",
                asset_id=asset_external_id,
            )
            return AssetUploadResource.FileRetrievalResult(
                False, _upload_missing_filename()
            )

        n_files = len(files)
        if n_files != 1:
            generate_user_trace_log(
                log,
                LogLevel.WARNING,
                self.user.id,
                "Expected exactly one file to be uploaded",
                asset_id=asset_external_id,
                number_of_files=n_files,
            )
            return AssetUploadResource.FileRetrievalResult(False, _upload_bad_files())

        if "file" not in files:
            bad_field = next(iter(files.keys()))
            generate_user_trace_log(
                log,
                LogLevel.WARNING,
                self.user.id,
                'Expected file upload field to be named, "file"',
                asset_id=asset_external_id,
                bad_field=bad_field,
            )

            return AssetUploadResource.FileRetrievalResult(
                False, _upload_bad_form_data_name(bad_field)
            )

        return AssetUploadResource.FileRetrievalResult(True, files["file"])

    @ddtrace.tracer.wrap()
    def _get_invalid_file_result(self, asset, file):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if asset.file_name != file.filename:
            generate_user_trace_log(
                log,
                LogLevel.WARNING,
                self.user.id,
                "Cannot upload contents with filename not matching recorded file_name",
                asset_id=asset.external_id,
                asset_file_name=asset.file_name,
                uploaded_file_name=file.filename,
            )
            return _upload_file_name_mismatch(asset.file_name, file.filename)

        file.seek(0, os.SEEK_END)
        uploaded_content_length = file.tell()
        asset_content_length = asset.content_length
        if uploaded_content_length != asset_content_length:
            generate_user_trace_log(
                log,
                LogLevel.WARNING,
                self.user.id,
                "Cannot upload contents with length not matching recorded content_length",
                asset_id=asset.external_id,
                asset_content_length=asset_content_length,
                uploaded_content_length=uploaded_content_length,
            )

            return _upload_content_length_mismatch(
                asset_content_length, uploaded_content_length
            )
        file.seek(0, os.SEEK_SET)

    @ddtrace.tracer.wrap()
    def _get_asset(self, asset_id: int) -> UserAsset:
        asset: UserAsset = (
            UserAsset.query.options(
                load_only("user_id", "state", "file_name", "content_length")
            )
            .filter_by(id=asset_id)
            .one_or_none()
        )
        return asset

    def post(self, asset_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """Uploads the contents of an asset to cloud storage."""

        get_file_result = self._get_file_from_request(asset_id, request)
        if not get_file_result.is_successful:
            stats.increment(
                metric_name=ASSET_UPLOAD_CANCELLED_METRIC,
                tags=["reason:FILE_RETRIEVAL_FAILURE"],
                pod_name=stats.PodNames.VIRTUAL_CARE,
            )

            # retrieve the asset only to update its state after file retrieval fails
            asset = self._get_asset(asset_id)
            _update_asset_with_new_state(asset, UserAssetState.CANCELED)
            return get_file_result.result

        file = get_file_result.result
        asset = self._get_asset(asset_id)

        invalid_asset_result = self._get_invalid_asset_result(asset, asset_id)
        if invalid_asset_result:
            # Not set the asset to CANCELED state (as of 8/29/2023)
            # 1) If it is due to asset unavailable, no need to set state
            # 2) If it is due to asset in terminal state, also we should not set state to CANCELED because
            #    the asset may be in COMPLETE state
            # 3) If it is due to unmatched user id, we should allow a retry with a correct user id
            return invalid_asset_result

        invalid_file_result = self._get_invalid_file_result(asset, file)
        if invalid_file_result:
            stats.increment(
                metric_name=ASSET_UPLOAD_CANCELLED_METRIC,
                tags=["reason:INVALID_FILE"],
                pod_name=stats.PodNames.VIRTUAL_CARE,
            )

            _update_asset_with_new_state(asset, UserAssetState.CANCELED)
            return invalid_file_result

        try:
            _asset_upload_from_file(asset, file)

            service_ns_tag = "assets"
            team_ns_tag = service_ns_team_mapper.get(service_ns_tag)
            complete_upload.delay(
                asset.id, service_ns=service_ns_tag, team_ns=team_ns_tag
            )

            generate_user_trace_log(
                log,
                LogLevel.INFO,
                self.user.id,
                "Uploaded asset contents",
                asset_id=asset.external_id,
            )
            return {}, 200
        except Exception as e:
            stats.increment(
                metric_name=ASSET_UPLOAD_CANCELLED_METRIC,
                tags=["reason:UPLOAD_FAILURE"],
                pod_name=stats.PodNames.VIRTUAL_CARE,
            )

            _update_asset_with_new_state(asset, UserAssetState.CANCELED)
            generate_user_trace_log(
                log,
                LogLevel.ERROR,
                self.user.id,
                "Could not upload asset contents after multiple retries",
                asset_id=asset.external_id,
                exception=e,
            )
            return _upload_error()


class _AssetAccessResource(AuthenticatedResource):
    def _common(self, asset_id, continuation):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        asset = UserAsset.query.filter_by(id=asset_id).one_or_none()

        if asset is None:
            log.warning(
                "Could not find asset by id.",
                user_id=self.user.id,
                asset_id=str(asset_id),
            )
            return _not_found(asset_id)

        if not asset.can_be_read_by(self.user):
            log.warning(
                "User cannot access asset contents.",
                user_id=self.user.id,
                asset_id=asset.external_id,
            )
            return _download_forbidden()

        if not (asset.state == UserAssetState.COMPLETE):
            log.warning(
                f"Cannot access state in non-{UserAssetState.COMPLETE.value} state.",
                user_id=self.user.id,
                asset_id=asset.external_id,
                asset_state=asset.state.value,
            )
            return _download_state_conflict()

        return continuation(asset)

    @classmethod
    def _redirect(cls, location):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        res = current_app.response_class(response="", status=302, mimetype="text/plain")
        res.headers["Location"] = location
        return res


class AssetDownloadResource(UnauthenticatedResource):
    def get(self, asset_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """Provides temporary signed access to the original asset contents.

        This should be deprecated in favor of the GET /assets/<asset_id>/url endpoint.
        That allows fetching the asset url rather than relying on this endpoint redirecting.
        """
        # Some of this contains duplicated auth logic out of our AuthenticatedResource
        # to handle a specific case where a user tries to access this route from Zendesk
        # The Zendesk request doesn't carry our auth header, so we have to reroute to
        # the web app and let the user log in first
        user_id = request.headers.get("X-Maven-User-ID")
        if user_id:
            try:
                user = db.session.query(User).filter(User.id == user_id).one()
                self._user = user
            except NoResultFound:
                abort(401, message="Unauthorized")

        # User is not authenticated, so try sending them to the web app
        # Other clients (mobile/web) also use this endpoint, so if authentication succeeds we
        # will preserve the remaining functionaliy below rather than redirecting here
        if not (user_id and user):
            config = configuration.get_api_config()
            location = f"{config.common.base_url}/app/assets/{asset_id}/view"
            res = current_app.response_class(
                response="",
                status=302,
                mimetype="application/json",
            )
            res.headers["Location"] = location
            return res

        schema = AssetDownloadSchema()
        try:
            args = schema.load(request.args).data
        except UnmarshallingError as e:
            log.warning(
                f"{AssetDownloadSchema.__name__} failed validation.",
                user_id=self.user.id,
                exception=e,
            )
            return from_unmarshalling_error(e)

        # Below logic is duplicated from _AssetAccessResource._common which is an AuthenticatedResource
        # Since we are handling this resource's authentication separately above, we pull
        # some of this logic out as well here rather than leaving it in the mixin.
        asset = UserAsset.query.filter_by(id=asset_id).one_or_none()

        if asset is None:
            log.warning(
                "Could not find asset by id.",
                user_id=self.user.id,
                asset_id=str(asset_id),
            )
            return _not_found(asset_id)

        if not asset.can_be_read_by(self.user):
            log.warning(
                "User cannot access asset contents.",
                user_id=self.user.id,
                asset_id=asset.external_id,
            )
            return _download_forbidden()

        if not (asset.state == UserAssetState.COMPLETE):
            log.warning(
                f"Cannot access state in non-{UserAssetState.COMPLETE.value} state.",
                user_id=self.user.id,
                asset_id=asset.external_id,
                asset_state=asset.state.value,
            )
            return _download_state_conflict()

        location = asset.direct_download_url(inline=(args["disposition"] == "inline"))
        res = current_app.response_class(
            response="",
            status=302,
            mimetype="application/json",
        )
        res.headers["Location"] = location
        return res


class AssetDownloadUrlResource(_AssetAccessResource):
    def get(self, asset_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """Provides a link to the asset."""
        schema = AssetDownloadSchema()
        try:
            args = schema.load(request.args).data
        except UnmarshallingError as e:
            log.warning(
                f"{AssetDownloadSchema.__name__} failed validation.",
                user_id=self.user.id,
                exception=e,
            )
            return from_unmarshalling_error(e)

        return self._common(
            asset_id, continuation=self.get_download_url(args["disposition"])
        )

    def get_download_url(self, disposition):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        def fn(asset):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            log.debug(
                "Getting direct download url.",
                user_id=self.user.id,
                asset_id=asset.external_id,
                disposition=disposition,
            )
            return {
                "download_url": asset.direct_download_url(
                    inline=(disposition == "inline")
                ),
                "content_type": asset.content_type,
            }

        return fn


class AssetThumbnailResource(_AssetAccessResource):
    def get(self, asset_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """Provides temporary signed access to a thumbnail representing the asset."""
        return self._common(asset_id, continuation=self.redirect_thumbnail)

    def redirect_thumbnail(self, asset):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not asset.content_type.startswith(("image/", "application/pdf")):
            log.warning(
                "Cannot generate thumbnail for non-image or pdf asset.",
                user_id=self.user.id,
                asset_id=asset.external_id,
            )
            return _thumbnail_not_found(asset)

        log.debug(
            "Redirecting user to direct thumbnail url.",
            user_id=self.user.id,
            asset_id=asset.external_id,
        )
        return self._redirect(asset.direct_thumbnail_url())


def validate_asset_length(value: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    config = configuration.get_api_config()
    limit = config.asset_content_length_limit
    range = Range(
        min=0,
        max=limit,
        error=f"Cannot create asset with contents exceeding {limit} bytes.",
    )
    return range(value)


class AssetPostSchema(MavenSchema):
    file_name = String(
        validate=Length(max=UserAsset.file_name.type.length), required=True
    )
    content_length = Integer(
        validate=validate_asset_length,
        required=True,
    )


class AssetDownloadSchema(WithDefaultsSchema):
    disposition = Enum(choices=("inline", "attachment"), default="attachment")


def _uploading_data(asset):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    config = configuration.get_api_config()
    return (
        {
            "data": {
                "id": asset.external_id,
                "upload_url": urljoin(
                    config.common.base_url, f"/api/v1/assets/{asset.id}/upload"
                ),
                "upload_form_data": {},
            },
            "errors": [],
        },
        200,
    )


@ddtrace.tracer.wrap()
def _not_found(asset_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    status = 404
    code = "NOT_FOUND"
    message = f"Could not find asset matching requested identifier, {asset_id}."
    field = "asset_id"
    return format_json_as_error(status=status, code=code, message=message, field=field)


def _get_state_forbidden():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    status = 403
    code = "FORBIDDEN"
    message = "Cannot access asset state belonging to another user."
    return format_json_as_error(status=status, code=code, message=message)


def _asset_state(asset):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return (
        {"data": {"id": asset.external_id, "state": asset.state.value}, "errors": []},
        200,
    )


def _db_error():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    status = 500
    code = "INTERVAL_SERVER_ERROR"
    message = "DB operation failed"
    return format_json_as_error(status=status, code=code, message=message)


@ddtrace.tracer.wrap()
def _upload_forbidden():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    status = 403
    code = "FORBIDDEN"
    message = "Cannot upload asset belonging to another user."
    return format_json_as_error(status=status, code=code, message=message)


@ddtrace.tracer.wrap()
def _upload_state_conflict():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    status = 409
    code = "ASSET_STATE_CONFLICT"
    message = (
        "Cannot upload contents for asset that is no longer in the UPLOADING state."
    )
    return format_json_as_error(status=status, code=code, message=message)


@ddtrace.tracer.wrap()
def _upload_entity_too_large():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    config = configuration.get_api_config()
    status = 413
    code = "ENTITY_TOO_LARGE"
    message = (
        f"Cannot upload contents exceeding {config.asset_content_length_limit} bytes."
    )
    field = "file"
    return format_json_as_error(status=status, code=code, message=message, field=field)


@ddtrace.tracer.wrap()
def _upload_missing_filename():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    status = 400
    code = "MISSING_DISPOSITION_FILENAME"
    message = "Asset upload endpoint expected file form data to include a Content-Disposition with a filename."
    field = "file"
    return format_json_as_error(status=status, code=code, message=message, field=field)


@ddtrace.tracer.wrap()
def _upload_bad_files():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    status = 400
    code = "NUMBER_OF_FILES"
    message = (
        "Asset upload endpoint expected exactly one multipart/form-data file upload."
    )
    return format_json_as_error(status=status, code=code, message=message)


@ddtrace.tracer.wrap()
def _upload_bad_form_data_name(bad_field):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    status = 400
    code = "BAD_NAME"
    message = 'Asset upload endpoint expected contents to be uploaded as an input named "file".'
    field = bad_field
    return format_json_as_error(status=status, code=code, message=message, field=field)


@ddtrace.tracer.wrap()
def _upload_file_name_mismatch(asset_file_name, uploaded_file_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    status = 400
    code = "FILE_NAME_MISMATCH"
    message = (
        f'Cannot upload contents with Content-Disposition filename "{uploaded_file_name}" not matching '
        f'expected file name "{asset_file_name}".'
    )
    field = "file"
    return format_json_as_error(status=status, code=code, message=message, field=field)


@ddtrace.tracer.wrap()
def _upload_content_length_mismatch(asset_content_length, uploaded_content_length):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    status = 400
    code = "CONTENT_LENGTH_MISMATCH"
    message = (
        f"Cannot upload contents with length {uploaded_content_length} not matching expected length"
        f" {asset_content_length}."
    )
    field = "file"
    return format_json_as_error(status=status, code=code, message=message, field=field)


@ddtrace.tracer.wrap()
def _upload_error():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    status = 500
    code = "UPLOAD_FAILED"
    message = "Our storage server is down."
    return format_json_as_error(status=status, code=code, message=message)


@ddtrace.tracer.wrap()
def _download_forbidden():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    status = 403
    code = "FORBIDDEN"
    message = "Cannot access asset contents."
    return format_json_as_error(status=status, code=code, message=message)


@ddtrace.tracer.wrap()
def _download_state_conflict():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    status = 409
    code = "ASSET_STATE_CONFLICT"
    message = "Asset contents cannot be accessed until upload is complete."
    return format_json_as_error(status=status, code=code, message=message)


@ddtrace.tracer.wrap()
def _thumbnail_not_found(asset):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    status = 404
    code = "NOT_FOUND"
    message = f"Asset with content type {asset.content_type} does not have a thumbnail."
    return format_json_as_error(status=status, code=code, message=message)


@ddtrace.tracer.wrap()
def _update_asset_with_new_state(asset: UserAsset, new_state: UserAssetState):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if asset and asset.state:
        asset.state = new_state  # type: ignore[assignment] # Incompatible types in assignment (expression has type "UserAssetState", variable has type "str")
        db.session.commit()


@ddtrace.tracer.wrap()
@retry_action(exceptions=(Exception,))
def _asset_upload_from_file(asset: UserAsset, file):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    asset.blob.upload_from_file(file.stream)
