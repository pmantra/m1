from __future__ import annotations

import tempfile
from typing import Any, Optional

import paramiko
from paramiko import SFTPError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from common import stats
from utils.log import logger

log = logger(__name__)


class FileIngestionJob:
    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_random_exponential(multiplier=1, max=60),
        retry=(retry_if_exception_type(IOError) | retry_if_exception_type(SFTPError)),
    )
    def _download(
        self, file: str, temp_file_name: str, sftp: paramiko.SFTPClient
    ) -> str:
        log.info(f"Downloading {file} from sftp")
        sftp.get(file, temp_file_name)
        log.info(f"Finished downloading {file}")
        return temp_file_name

    def find_files_to_process(
        self,
        files: list[str],
        filename_pattern: Any,
        target_date: int,
        date_index: int,
    ) -> list[str]:
        result = []
        log.info("Found files on SFTP server", num_files=len(files))
        for file in files:
            match = filename_pattern.match(file)
            if match:
                date = int(match.group(date_index))
                if date == target_date:
                    result.append((file, date))
        log.info(
            "Found files matching target_date and filename_pattern on SFTP server",
            num_files={len(files)},
            target_date=target_date,
            filename_pattern=filename_pattern,
        )
        return [
            file for file, date in sorted(result, key=lambda x: x[1], reverse=False)
        ]

    def download_file(
        self,
        file_name: str,
        directory: str,
        sftp_client: paramiko.SFTPClient,
        metric_name: str,
    ) -> Optional[str]:
        with tempfile.NamedTemporaryFile() as temp:
            try:
                self._download(f"{directory}/{file_name}", temp.name, sftp_client)
                with open(temp.name, "r") as file:
                    content = file.read()
                    return content
            except (IOError, SFTPError):
                stats.increment(
                    metric_name=metric_name,
                    tags=["reason:DOWNLOAD_FAILURE"],
                    pod_name=stats.PodNames.PAYMENTS_PLATFORM,
                )
                return ""
