from traceback import format_exc

from flask import request
from flask_restful import abort
from marshmallow_v1 import Schema, fields

from common.services import ratelimiting
from common.services.api import AuthenticatedResource
from models.images import Image, delete_image_file, upload_and_save_image
from storage.connection import db
from utils.log import logger
from utils.marshmallow_experiment import marshmallow_experiment_enabled
from views.schemas.common import WithDefaultsSchema
from views.schemas.images_v3 import AssetSchemaV3, ImageGetSchemaV3, ImageSchemaV3

log = logger(__name__)


class ImageSchema(Schema):
    id = fields.Integer()
    height = fields.Integer()
    width = fields.Integer()
    filetype = fields.String()
    url = fields.String()


def get_image_response(image: Image) -> dict:
    return {
        "id": image.id,
        "height": image.height,
        "width": image.width,
        "filetype": image.filetype,
        "url": image.url,
    }
    # https://mavenclinic.atlassian.net/browse/SEC-241
    # original_filename has been removed because it allowed other users to see
    # the plain text filename of an asset uploaded by another user. This is a
    # security risk because that file name is not controlled by us and could
    # contain sensitive information like an email address.


class AssetSchema(Schema):
    url = fields.String()


class ImagesResource(AuthenticatedResource):
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        if "image" not in request.files:
            abort(400)

        image = upload_and_save_image(request.files["image"])

        if image:
            return get_image_response(image), 201
        else:
            abort(400, message="Bad Image, Please Try Again!")


class ImageResource(AuthenticatedResource):
    # https://mavenclinic.atlassian.net/browse/SEC-241
    # This rate limit is only to guard abuse by enumeration. It should be high
    # enough to never be hit by a normal user. 50 hits per 5 sec should be
    # sufficient to accommodate bursts when loading a list of user avatars.
    @ratelimiting.ratelimited(attempts=50, cooldown=5)
    def get(self, image_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        experiment_enabled = marshmallow_experiment_enabled(
            flag_key="experiment-marshmallow-images-upgrade",
            user_esp_id=self.user.esp_id,
            user_email=self.user.email,
            default=False,
        )
        schema = ImageSchema() if not experiment_enabled else ImageSchemaV3()

        image = Image.query.get_or_404(image_id)
        marshmallow_result = (
            schema.dump(image).data if not experiment_enabled else schema.dump(image)  # type: ignore[attr-defined] # "object" has no attribute "dump"
        )
        try:
            python_result = get_image_response(image)
            if python_result == marshmallow_result:
                log.info("FM - ImagesResource 2 identical")
            else:
                log.info("FM - ImagesResource 2 diff")
        except Exception:
            log.info("FM - ImagesResource 2 exception", traces=format_exc())
        return marshmallow_result

    def delete(self, image_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        image = Image.query.get_or_404(image_id)
        if self.user.image != image:
            abort(401, message="Authenticated user can only delete their own image.")
        try:
            delete_image_file(image.storage_key)
        except Exception as e:
            log.warn("Could not delete image_id=%s from GCS", image_id, exception=e)
        self.user.image = None
        db.session.delete(image)
        db.session.commit()
        return "", 204


class ImageGetSchema(WithDefaultsSchema):
    smart = fields.Boolean(default=True)


class ImageAssetURLResource(AuthenticatedResource):
    def get(self, image_id, size):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            height, width = size.split("x")
            height, width = int(height), int(width)
            assert height and width
        except (ValueError, AssertionError):
            abort(400, message="Please provide a valid heightxwidth as a size!")

        experiment_enabled = marshmallow_experiment_enabled(
            flag_key="experiment-marshmallow-images-upgrade",
            user_esp_id=self.user.esp_id,
            user_email=self.user.email,
            default=False,
        )

        image = Image.query.get_or_404(image_id)
        args = (
            ImageGetSchema().load(request.args).data
            if not experiment_enabled
            else ImageGetSchemaV3().load(request.args)
        )

        schema = AssetSchema() if not experiment_enabled else AssetSchemaV3()
        response = {"url": image.asset_url(height, width, smart=args["smart"])}
        marsh_response = (
            schema.dump(response).data  # type: ignore[attr-defined] # "object" has no attribute "dump"
            if not experiment_enabled
            else schema.dump(response)  # type: ignore[attr-defined] # "object" has no attribute "dump"
        )
        if response == marsh_response:
            log.info("FM - AssetSchema iden")
        else:
            log.info(
                "FM - AssetSchema diff",
                marsh=str(marsh_response),
                py_response=str(response),
            )
        return marsh_response
