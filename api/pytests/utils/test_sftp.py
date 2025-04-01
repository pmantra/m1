from unittest.mock import Mock, patch

import paramiko
import pytest

from utils.sftp import SSHError, ssh_connect, ssh_connect_retry


@pytest.fixture
def mock_ssh_client():
    client = Mock()
    yield client
    client.close.assert_called()


@patch("utils.sftp.ssh_connect_retry")
@patch("paramiko.SSHClient")
def test_connect_success(mock_ssh_client, mock_ssh_retry):
    mock_ssh_retry.return_value = mock_ssh_client
    ssh_connect("test")
    mock_ssh_retry.assert_called()


@patch("utils.sftp.ssh_connect_retry", side_effect=paramiko.AuthenticationException)
@patch("paramiko.SSHClient")
def test_ssh_connect_auth_exception(mock_ssh_client, mock_ssh_retry):
    with pytest.raises(paramiko.AuthenticationException):
        ssh_connect("test")
    mock_ssh_retry.assert_called()
    assert mock_ssh_retry.call_count == 1


@patch("paramiko.SSHClient")
def test_ssh_connect_retry_exception(mock_ssh_client):
    mock_ssh_client.return_value.connect.side_effect = paramiko.SSHException
    with pytest.raises(SSHError):
        ssh_connect_retry(
            client=mock_ssh_client.return_value, hostname="test", max_attempts=3
        )
    assert mock_ssh_client.return_value.connect.call_count == 3


@patch("paramiko.SSHClient")
def test_ssh_connect_retry_succeed(mock_ssh_client):
    mock_ssh_client.return_value.connect.side_effect = [paramiko.SSHException, None]
    result = ssh_connect_retry(
        client=mock_ssh_client.return_value, hostname="test", max_attempts=3
    )
    assert mock_ssh_client.return_value.connect.call_count == 2
    assert result == mock_ssh_client.return_value


@patch("paramiko.SSHClient")
def test_ssh_connect_retry_succeed_happy(mock_ssh_client):
    result = ssh_connect_retry(client=mock_ssh_client.return_value, hostname="test")
    assert mock_ssh_client.return_value.connect.called
    assert result == mock_ssh_client.return_value
