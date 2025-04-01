from dataclasses import dataclass
from datetime import datetime
from hashlib import sha1
from os import getenv
from os.path import abspath, dirname, sep
from typing import List, NamedTuple

from google.cloud import storage
from jinja2 import Environment, FileSystemLoader
from lxml import etree

from utils.log import logger

log = logger(__name__)


class __Url(NamedTuple):
    loc: str
    priority: str


@dataclass
class __SitemapBlob:
    __slots__ = ("name", "contents")
    name: str
    contents: bytes


__STATIC_PAGES_URLS: List[__Url] = [
    ("https://www.mavenclinic.com/", "0.9"),  # type: ignore[list-item] # List item 0 has incompatible type "Tuple[str, str]"; expected "__Url"
    ("https://www.mavenclinic.com/about", "0.8"),  # type: ignore[list-item] # List item 1 has incompatible type "Tuple[str, str]"; expected "__Url"
    ("https://www.mavenclinic.com/practitioners", "0.8"),  # type: ignore[list-item] # List item 2 has incompatible type "Tuple[str, str]"; expected "__Url"
    ("https://www.mavenclinic.com/for-health-plans", "0.8"),  # type: ignore[list-item] # List item 3 has incompatible type "Tuple[str, str]"; expected "__Url"
    ("https://www.mavenclinic.com/for-individuals", "0.8"),  # type: ignore[list-item] # List item 4 has incompatible type "Tuple[str, str]"; expected "__Url"
    ("https://www.mavenclinic.com/contact", "0.8"),  # type: ignore[list-item] # List item 5 has incompatible type "Tuple[str, str]"; expected "__Url"
    ("https://www.mavenclinic.com/press", "0.9"),  # type: ignore[list-item] # List item 6 has incompatible type "Tuple[str, str]"; expected "__Url"
    ("https://www.mavenclinic.com/download-the-app", "0.8"),  # type: ignore[list-item] # List item 7 has incompatible type "Tuple[str, str]"; expected "__Url"
    ("https://www.mavenclinic.com/mental-health-packages", "0.8"),  # type: ignore[list-item] # List item 8 has incompatible type "Tuple[str, str]"; expected "__Url"
    ("https://www.mavenclinic.com/for-business", "0.8"),  # type: ignore[list-item] # List item 9 has incompatible type "Tuple[str, str]"; expected "__Url"
    ("https://www.mavenclinic.com/forgot-password", "0.7"),  # type: ignore[list-item] # List item 10 has incompatible type "Tuple[str, str]"; expected "__Url"
    ("https://www.mavenclinic.com/login", "0.8"),  # type: ignore[list-item] # List item 11 has incompatible type "Tuple[str, str]"; expected "__Url"
    ("https://www.mavenclinic.com/practitioners", "0.8"),  # type: ignore[list-item] # List item 12 has incompatible type "Tuple[str, str]"; expected "__Url"
    ("https://www.mavenclinic.com/app/privacy", "0.8"),  # type: ignore[list-item] # List item 13 has incompatible type "Tuple[str, str]"; expected "__Url"
    ("https://www.mavenclinic.com/register", "0.8"),  # type: ignore[list-item] # List item 14 has incompatible type "Tuple[str, str]"; expected "__Url"
    ("https://www.mavenclinic.com/app/terms", "0.8"),  # type: ignore[list-item] # List item 15 has incompatible type "Tuple[str, str]"; expected "__Url"
]
__THIS_DIR = dirname(abspath(__file__))
__JINJA = Environment(loader=FileSystemLoader(__THIS_DIR), trim_blocks=True)
__SCHEMAS = {}


def update() -> None:
    """update generates sitemap files and uploads them to a publicly served storage bucket."""
    lastmod = datetime.utcnow().isoformat(timespec="seconds")
    log.info("Updating sitemaps.")
    urls = __STATIC_PAGES_URLS
    log.info(f"Found {len(urls)} urls to publish.")
    sitemap = _sitemap(urls)
    index = _index(sitemap, lastmod)
    # Uploading the index last allows us to atomically switch over to the new sitemap while
    # gracefully handling exceptions during upload. If anything fails leading up to the upload
    # of the new sitemap index, the old sitemap index / map files will continue to be served.
    blobs = [sitemap, index]
    log.info("Uploading sitemap index and sitemap file.")
    _upload(blobs)
    log.info(f"Updated sitemaps at lastmod: {lastmod}.")


def _sitemap(urls: List[__Url]) -> __SitemapBlob:
    """_sitemap renders a sitemap for the given urls."""
    template = __JINJA.get_template("sitemap.j2")
    contents = template.render(urls=urls).encode("utf-8")
    _assert_valid("map", contents)
    return __SitemapBlob(f"sitemap/{sha1(contents).hexdigest()}.xml", contents)


def _index(sitemap: __SitemapBlob, lastmod: str) -> __SitemapBlob:
    """_index renders a sitemap index pointing to the given sitemaps."""
    sitemap_url = f"https://www.mavenclinic.com/{sitemap.name}"
    template = __JINJA.get_template("siteindex.j2")
    text = template.render(loc=sitemap_url, lastmod=lastmod).encode("utf-8")
    _assert_valid("index", text)
    return __SitemapBlob("sitemap.xml", text)


def _assert_valid(kind, text):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """_assert_valid raises an error if text fails to validate against the given schema kind."""
    assert kind in ("index", "map")
    if kind not in __SCHEMAS:
        schema_tree = etree.parse(f"{__THIS_DIR}{sep}site{kind}.xsd")
        __SCHEMAS[kind] = etree.XMLSchema(schema_tree)
    schema = __SCHEMAS[kind]
    document = etree.fromstring(text)
    return schema.assertValid(document)


def _upload(sitemap_blobs: List[__SitemapBlob]):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    client = storage.Client()
    bucket = client.get_bucket(getenv("SITEMAP_BUCKET"))
    for sitemap_blob in sitemap_blobs:
        blob = bucket.blob(sitemap_blob.name)
        blob.upload_from_string(sitemap_blob.contents, content_type="text/xml")
