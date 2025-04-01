from os import SEEK_END
from tempfile import NamedTemporaryFile
from urllib.parse import quote

import magic

from common import stats
from models.enterprise import UserAsset, UserAssetState
from storage.connection import db
from tasks.queues import retryable_job
from utils.constants import ASSET_UPLOAD_CANCELLED_METRIC, ASSET_UPLOAD_COMPLETE_METRIC
from utils.log import logger

log = logger(__name__)


_OCTET_STREAM = "application/octet-stream"


@retryable_job("priority", retry_limit=3, traced_parameters=("asset_id",))
def complete_upload(asset_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.debug("Completing asset upload.", asset_id=str(asset_id))

    asset = UserAsset.query.filter_by(id=asset_id).one_or_none()
    if asset is None:
        log.error("Could not find asset by id.", asset_id=str(asset_id))
        return

    if asset.in_terminal_state():
        log.debug("Asset is already in a terminal state.", asset_id=asset.external_id)
        return

    try:
        blob = asset.blob
        with NamedTemporaryFile() as f:
            log.debug("Downloading asset contents to file.", asset_id=asset.external_id)
            blob.download_to_file(f)
            f.seek(0, SEEK_END)
            downloaded_content_length = f.tell()
            if asset.content_length != downloaded_content_length:
                log.error(
                    "Recorded content length differs from downloaded content length.",
                    asset_id=asset.external_id,
                    recorded_content_length=asset.content_length,
                    downloaded_content_length=downloaded_content_length,
                )
            try:
                log.debug(
                    "Parsing mime type from asset contents.", asset_id=asset.external_id
                )
                asset.content_type = magic.from_file(f.name, mime=True)
            except Exception as m_e:
                log.warn(
                    f"Could not identify mime type from asset contents, falling back to {_OCTET_STREAM}.",
                    asset_id=asset.external_id,
                    exception=m_e,
                )
                asset.content_type = _OCTET_STREAM
        asset.state = UserAssetState.COMPLETE
        log.debug("Updating blob metadata.", asset_id=asset.external_id)
        blob.content_type = asset.content_type
        blob.content_disposition = (
            f"attachment;filename*=utf-8''{quote(asset.file_name)}"
        )
        blob.patch()
        db.session.commit()
        log.info("Completed upload for asset.", asset_id=asset.external_id)
        stats.increment(
            metric_name=ASSET_UPLOAD_COMPLETE_METRIC,
            pod_name=stats.PodNames.VIRTUAL_CARE,
        )

    except Exception as e:
        stats.increment(
            metric_name=ASSET_UPLOAD_CANCELLED_METRIC,
            tags=["reason:COMPLETE_UPLOAD_FAILURE"],
            pod_name=stats.PodNames.VIRTUAL_CARE,
        )

        asset.state = UserAssetState.CANCELED
        db.session.commit()
        log.warn(
            "Could not complete upload for asset due to unhandled exception.",
            asset_id=asset.external_id,
            exception=e,
        )
