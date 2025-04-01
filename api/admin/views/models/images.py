from flask_admin.form import upload
from wtforms import validators

from models.images import Image, upload_and_save_image
from storage.connection import db


class ImageUploadInput(upload.ImageUploadInput):
    def __call__(self, field, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if isinstance(field.data, int):
            field.data = str(field.data)
        return super().__call__(field, **kwargs)

    def get_url(self, field):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return db.session.query(Image).get(field.data).url


class ImageUploadField(upload.FileUploadField):

    widget = ImageUploadInput()

    def __init__(self, field_name="image_id", **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.field_name = field_name
        super().__init__(**kwargs)

    def populate_obj(self, obj, name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if self._should_delete:
            setattr(obj, self.field_name, None)
        if self.data and not isinstance(self.data, int):
            image = upload_and_save_image(self.data)
            if image:
                setattr(obj, self.field_name, image.id)
            else:
                raise validators.ValidationError("Could not save image...")
