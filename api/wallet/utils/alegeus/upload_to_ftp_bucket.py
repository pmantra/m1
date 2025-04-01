import io

from utils.log import logger
from wallet.constants import (
    ALEGEUS_FTP_HOST,
    ALEGEUS_FTP_PASSWORD,
    ALEGEUS_FTP_USERNAME,
)
from wallet.utils.alegeus.edi_processing.common import ssh_connect

log = logger(__name__)


def upload_blob(csv_contents, destination_blob_name, client=None, sftp=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    """Uploads a file to the bucket."""
    try:
        if client is None:
            client = ssh_connect(
                ALEGEUS_FTP_HOST,
                username=ALEGEUS_FTP_USERNAME,
                password=ALEGEUS_FTP_PASSWORD,
            )
            sftp = client.open_sftp()
        sftp.putfo(io.StringIO(csv_contents), destination_blob_name)
    except Exception as e:
        if sftp:
            sftp.close()
        if client:
            client.close()
        raise e
