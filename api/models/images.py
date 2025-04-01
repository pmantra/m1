import uuid
from io import BytesIO
from urllib.request import urlopen

import magic
import requests
from sqlalchemy import Column, Integer, String, UniqueConstraint
from werkzeug.datastructures import FileStorage

import configuration
from models import base
from storage.connection import db
from utils.log import logger
from utils.storage import delete_file, upload_file
from utils.thumbor import CryptoURL

log = logger(__name__)

GOOGLE_API_AUTH_CACHE = "image_storage_bearer_token"


def image_bucket() -> str:
    config = configuration.get_api_config()
    return config.image_bucket


def thumbor_secret_key() -> str:
    config = configuration.get_api_config()
    return config.thumbor.secret_key


def thumbor_url() -> str:
    config = configuration.get_api_config()
    return config.thumbor.url


# TODO: Migrate maven-prod-images to a uniform access bucket
def image_bucket_acl_enabled() -> bool:
    # prod images is a legacy bucket with object-level access controls, while our other
    # image buckets are have uniform bucket access and will refuse uploads with ACLs
    return image_bucket() == "maven-prod-images"


def upload_image_file(name, file_body, content_type):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    upload_file(
        name,
        image_bucket(),
        file_body,
        content_type=content_type,
        auth_cache_key=GOOGLE_API_AUTH_CACHE,
        acl="publicRead" if image_bucket_acl_enabled() else None,
    )


def delete_image_file(name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    delete_file(
        name,
        image_bucket(),
        auth_cache_key=GOOGLE_API_AUTH_CACHE,
    )


def upload_and_save_image_from_url(image_url):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if image_url is None:
        return
    resp = urlopen(image_url)
    file_storage = FileStorage(BytesIO(resp.read()))
    file_storage.filename = image_url.split("/")[-1]
    return upload_and_save_image(file_storage)


def upload_and_save_image(source_file, name=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """
    Upload and save image to Google Cloud Storage
    :param source_file: werkzeug.datastructures.FileStorage object
    :param name: image file storage key
    :return: Image model object
    """

    def get_mimetype():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        mime = magic.Magic(mime=True)

        source_file.stream.seek(0)
        mimetype = mime.from_buffer(source_file.stream.read(1024))
        source_file.stream.seek(0)
        return mimetype

    def valid_image_mimetype():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        # http://stackoverflow.com/q/20272579/396300
        mimetype = get_mimetype()
        if mimetype:
            if mimetype.startswith("image"):
                return mimetype

    # check file size limit
    source_file.stream.seek(0, 2)  # seek to EOF
    filesize = source_file.stream.tell()
    if filesize > 10485760:  # 10MB (10*1024*1024)
        log.info("Exceed max image file size!")
        return

    filetype = valid_image_mimetype()
    if not filetype:
        log.info("Unknown Image File!")
        return

    # reset stream
    source_file.stream.seek(0)
    image = Image(
        storage_key=name or str(uuid.uuid4()),
        filetype=filetype,
        original_filename=source_file.filename,
    )

    upload_image_file(image.storage_key, source_file.stream, source_file.content_type)

    # This will make an HTTP request to the thumbor server, and will only
    # succeed if the upload above worked properly
    metadata = image.image_metadata()
    if metadata:
        image.height = metadata["thumbor"]["source"]["height"]
        image.width = metadata["thumbor"]["source"]["width"]

        db.session.add(image)
        db.session.commit()

        log.debug("New %s", image)
        return image
    else:
        log.debug("Got no metadata! %s", image)
        delete_file(image.storage_key, image_bucket(), GOOGLE_API_AUTH_CACHE)
        log.warning("INVALID IMAGE (%s)!", image)


class Image(base.TimeLoggedModelBase):
    __tablename__ = "image"
    constraints = (UniqueConstraint("storage_key"),)

    id: int = Column(Integer, primary_key=True)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[int]", variable has type "int")
    storage_key: str = Column(String(36))  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[Optional[str]]", variable has type "str")

    height: int = Column(Integer)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[Optional[int]]", variable has type "int")
    width: int = Column(Integer)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[Optional[int]]", variable has type "int")
    filetype: str = Column(String(5), nullable=False)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[str]", variable has type "str")
    original_filename: str = Column(String(100))  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Column[Optional[str]]", variable has type "str")

    def __repr__(self) -> str:
        return f"<Image {self.id} [{self.storage_key} ({self.filetype})]>"

    @property
    def url(self) -> str:
        return f"https://storage.googleapis.com/{self.cdn_path}"

    @property
    def cdn_path(self) -> str:
        return f"{image_bucket()}/{self.storage_key}"

    def asset_url(self, height=None, width=None, smart=True) -> str:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        crypto = CryptoURL(key=thumbor_secret_key())

        asset_url = crypto.generate(
            width=width, height=height, smart=smart, image_url=self.url
        )

        return f"{thumbor_url()}{asset_url}"

    def image_metadata(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        crypto = CryptoURL(key=thumbor_secret_key())
        metadata_url = crypto.generate(image_url=self.url, height=0, width=0, meta=True)

        metadata_url = f"{thumbor_url()}{metadata_url}"
        res = requests.get(metadata_url)
        if res.status_code == 200:
            return res.json()
