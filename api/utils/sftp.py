"""
A module provide util functions for interacting with sftp server
"""
from __future__ import annotations

import json
from typing import Any, Optional, Tuple

import paramiko
import tenacity
from paramiko import SFTPClient, SSHClient
from tenacity import stop_after_attempt

from utils.log import logger

log = logger(__name__)


class SSHError(Exception):
    def __init__(self, message: str, *args: Any):
        self.message = message
        super().__init__(self.message, *args)


def ssh_connect(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    hostname: str,
    port: int = 22,
    username: str | None = None,
    password: str | None = None,
    max_attempts: int = 1,
):
    """A wrapper for paramiko, returns a SSHClient after it connects."""
    client = paramiko.SSHClient()
    try:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        return ssh_connect_retry(
            client,
            hostname,
            port=port,
            username=username,
            password=password,
            max_attempts=max_attempts,
        )
    except SSHError:
        log.error(f"Failed to connect to {hostname}", exc_info=True)
        client.close()


def ssh_connect_retry(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    client: paramiko.SSHClient,
    hostname: str,
    port: int = 22,
    username: str | None = None,
    password: str | None = None,
    max_attempts: int = 1,
):
    try:
        for attempt in tenacity.Retrying(
            stop=stop_after_attempt(max_attempts),
            retry=(
                tenacity.retry_if_exception_type(paramiko.SSHException)
                | (tenacity.retry_if_exception_type(OSError))
            ),
        ):
            with attempt:
                client.connect(
                    hostname, port=port, username=username, password=password
                )
                return client
    except tenacity.RetryError as e:
        raise SSHError(
            f"Failed to establish SSH connection after {max_attempts} attempts: {e}"
        )
    except Exception as e:
        raise SSHError(f"Unexpected error during SSH connection: {e}")


def get_client_sftp(  # type: ignore[return] # Missing return statement
    hostname: str, username: str, password: str, max_attempts: int = 2
) -> Tuple[Optional[SSHClient], Optional[SFTPClient]]:
    try:
        client = ssh_connect(
            hostname,
            username=username,
            password=password,
            max_attempts=max_attempts,
        )
        sftp = client.open_sftp()
        return client, sftp
    except SSHError:
        log.error(f"Failed to get sftp client for: {hostname}", exc_info=True)


def _get_sftp_credentials(credential_str: str) -> Tuple[str, str, str]:
    credential_dict = json.loads(credential_str)
    return (
        credential_dict.get("url"),
        credential_dict.get("username"),
        credential_dict.get("password"),
    )


def get_sftp_from_secret(  # type: ignore[return] # Missing return statement
    client_secret: str, port: int = 22
) -> Optional[paramiko.SFTPClient]:
    host, username, password = _get_sftp_credentials(client_secret)
    log.info("Got credentials from secret.", hostname=host)
    try:
        client = ssh_connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            max_attempts=2,
        )
        if not client:
            raise SSHError(message=f"Failed to get sftp client for: {host}")
        sftp = client.open_sftp()
        log.info("Got SFTP connection.", hostname=host)
        return sftp
    except Exception as e:
        raise SSHError(f"Unexpected error during SSH connection: {e}")
