import os

from common.constants import current_web_origin
from common.document_mapper.client import DocumentMapperClient


def get_client(base_url: str = "") -> DocumentMapperClient:
    if not base_url:
        if not os.environ.get("ENVIRONMENT"):
            base_url = "http://host.docker.internal:8888/v1/"
        else:
            base_url = current_web_origin() + "/api/v1/document-mapper/"

    return DocumentMapperClient(base_url=base_url)
