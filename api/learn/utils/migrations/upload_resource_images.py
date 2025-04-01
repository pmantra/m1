import hashlib
import mimetypes
import time

import bs4
import contentful_management
import requests
import sqlalchemy

from app import create_app
from learn.models.migration import ContentfulMigrationStatus
from learn.utils.migrations import constants, create_article_json
from models import marketing
from utils.log import logger

log = logger(__name__)


client = contentful_management.Client(constants.CONTENTFUL_MANAGEMENT_KEY)
space = client.spaces().find(constants.CONTENTFUL_SPACE_ID)
environment = space.environments().find(constants.CONTENTFUL_ENVIRONMENT_ID)


def upload_images() -> None:
    content_types = [t.name for t in marketing.LibraryContentTypes]
    content_types.append("curriculum_step")
    resources = marketing.Resource.query.filter(
        marketing.Resource.contentful_status == ContentfulMigrationStatus.NOT_STARTED,
        marketing.Resource.webflow_url != None,
        marketing.Resource.published_at <= sqlalchemy.func.now(),
        marketing.Resource.content_type.in_(content_types),
    )
    log.info("Found resources", count=resources.count())
    for resource in resources:
        log.info("Uploading images from resource", id=resource.id)
        upload_images_from_webflow_article(resource.webflow_url)
    log.info("Done uploading images")


def upload_images_from_webflow_article(webflow_url):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    res = requests.get(webflow_url)
    soup = bs4.BeautifulSoup(res.text)
    images = soup.find_all("img")

    for image in images:
        src = image.attrs["src"]

        if create_article_json.img_is_after_article_body(image):
            log.info("Image is after article body, breaking")
            # Break bc we can ignore this image and any that come after it
            break
        try:
            upload_image_to_contentful(src=src)
        except Exception:
            # Logging happens below; let's just continue to the next image
            # --we can always rerun
            continue


def upload_admin_article_images() -> None:
    content_types = [t.name for t in marketing.LibraryContentTypes]
    content_types.append("curriculum_step")
    resources = marketing.Resource.query.filter(
        marketing.Resource.contentful_status == ContentfulMigrationStatus.NOT_STARTED,
        marketing.Resource.resource_type == marketing.ResourceTypes.ENTERPRISE,
        marketing.Resource.webflow_url == None,
        marketing.Resource.published_at <= sqlalchemy.func.now(),
        marketing.Resource.content_type.in_(content_types),
    )
    log.info("Found resources", count=resources.count())
    for resource in resources:
        log.info("Uploading images from resource", id=resource.id)
        upload_images_from_admin_article(resource)
    log.info("Done uploading images")


def upload_admin_header_images() -> None:
    content_types = [t.name for t in marketing.LibraryContentTypes]
    content_types.append("curriculum_step")
    resources = marketing.Resource.query.filter(
        marketing.Resource.resource_type == marketing.ResourceTypes.ENTERPRISE,
        marketing.Resource.webflow_url == None,
        marketing.Resource.published_at <= sqlalchemy.func.now(),
        marketing.Resource.content_type.in_(content_types),
        marketing.Resource.image_id != None,
    ).options(sqlalchemy.orm.joinedload(marketing.Resource.image, innerjoin=True))
    log.info("Found resources", count=resources.count())

    for resource in resources:
        log.info("Processing image from resource", slug=resource.slug)
        try:
            upload_header_image_from_admin_article_n_save(resource=resource)
        except Exception as e:
            log.error(
                "Error uploading image to contentful or saving article",
                slug=resource.slug,
                error=e,
            )


def upload_images_from_admin_article(resource: marketing.Resource):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    soup = bs4.BeautifulSoup(resource.body)
    images = soup.find_all("img")
    for image in images:
        src = image.attrs["src"]
        try:
            # Don't filter any out--I don't think there are any that occur
            # after the body, but we'll find out if I'm wrong
            upload_image_to_contentful(src=src)
        except Exception:
            # Logging happens below; let's just continue to the next image
            # --we can always rerun
            continue


def upload_header_image_from_admin_article_n_save(resource: marketing.Resource):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    entry_id = hashlib.md5(resource.slug.encode()).hexdigest()
    # Every article should be in Contentful already at the time we run this
    if entry := environment.entries().find(entry_id):
        if img := entry.fields().get("hero_image"):
            # ID of the placeholder image across platforms
            if img.id == "be3456dd7bce035dbd113f8265d521a9":
                # If we're using the placeholder even though this resource has
                # a saved image in the db, use the saved image instead
                log.info(
                    "Attempting to replace placeholder image with saved image",
                    slug=resource.slug,
                )
                url = resource.image.url
                url_hash = hashlib.md5(url.encode()).hexdigest()
                try:
                    asset = environment.assets().find(url_hash)
                except Exception:
                    asset = upload_image_to_contentful(url)
                if asset:
                    entry.hero_image = asset
                    entry.save()
                    entry.publish()
                    log.info("Placeholder image replaced!", slug=resource.slug)
                else:
                    log.error(
                        "Could neither fetch existing nor upload image",
                        slug=resource.slug,
                    )
        else:
            log.warn("No hero image found on entry at all", slug=resource.slug)
    else:
        log.warn("Contentful entry not found", slug=resource.slug)


def upload_image_to_contentful(src: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    src_hash = hashlib.md5(src.encode()).hexdigest()
    if img_already_uploaded(src_hash):
        log.info("Image has already been uploaded", src=src)
        return
    try:
        res = requests.get(src)
        if not res.ok:
            log.error(
                "Received non-2xx status fetching image",
                src=src,
                status=res.status_code,
            )
            return
        image_content = res.content
    except requests.exceptions.RequestException as e:
        log.error("Received error fetching image", src=src, error=e)
        return

    # Cannot use contentful management client for this, bc it requires
    # a file object or filepath rather than raw data
    try:
        res = requests.post(
            f"https://upload.contentful.com/spaces/{constants.CONTENTFUL_SPACE_ID}/uploads",
            headers={
                "Content-Type": "application/octet-stream",
                "Authorization": f"Bearer {constants.CONTENTFUL_MANAGEMENT_KEY}",
            },
            data=image_content,
        )
        if not res.ok:
            log.error(
                "Received non-2xx status uploading image",
                src=src,
                status=res.status_code,
            )
            return
    except requests.exceptions.RequestException as e:
        log.error("Received error uploading image to Contentful", src=src, error=e)
        return
    upload_id = res.json()["sys"]["id"]

    # Determine value for contentType, e.g. "image/jpeg"
    filename = src.split("/")[-1]
    mimetype = mimetypes.guess_type(filename)[0]
    if not mimetype:
        # Default to jpeg--google bucket urls lack file extensions but jpeg works
        mimetype = "image/jpeg"

    # Create an asset to associate with the upload created earlier
    try:
        asset = environment.assets().create(
            resource_id=src_hash,
            attributes={
                "fields": {
                    "title": {"en-US": filename.split(".")[0]},
                    "file": {
                        "en-US": {
                            "contentType": mimetype,
                            "fileName": filename,
                            "uploadFrom": {
                                "sys": {
                                    "type": "Link",
                                    "linkType": "Upload",
                                    "id": upload_id,
                                }
                            },
                        }
                    },
                }
            },
        )
    except contentful_management.errors.HTTPError as e:
        log.error("Error creating asset", status=e.status_code, src=src)
        return

    # Process the asset--it cannot be published until this is done
    try:
        asset.process()
    except contentful_management.errors.HTTPError as e:
        log.error("Error processing asset", status=e.status_code, src=src)
        return

    published = None
    # Attempt to publish asset, trying three times in case processing
    # is not done yet
    for _ in range(2):
        time.sleep(1)
        if published := refetch_asset_and_publish(environment, asset.id):
            break
    if published:
        log.info("Published asset", asset_id=asset.id, src=src)
        return published
    else:
        log.error("Failed to publish asset", asset_id=asset.id, src=src)


def img_already_uploaded(src_hash):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    try:
        if environment.assets().find(src_hash):
            return True
    except contentful_management.errors.NotFoundError:
        return False
    except contentful_management.errors.HTTPError:
        log.error("Error checking Contentful for existing upload", asset_id=src_hash)
        return False


def refetch_asset_and_publish(environment, asset_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    reloaded_asset = environment.assets().find(asset_id)
    if reloaded_asset.url():
        try:
            reloaded_asset.publish()
            return reloaded_asset
        except contentful_management.errors.HTTPError as e:
            log.error("Error publishing asset", asset_id=asset_id, status=e.status_code)


if __name__ == "__main__":
    with create_app().app_context():
        upload_admin_header_images()
