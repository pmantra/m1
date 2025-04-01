import json
from datetime import date, datetime
from unittest.mock import patch

import pytest

from authn.errors.idp.client_error import IdentityClientError
from utils.gdpr_backup_data import GDPRBackUpDataException, GDPRDataDelete


def serialize_data(data: list) -> str:
    return json.dumps(
        data,
        default=lambda x: x.isoformat() if isinstance(x, (datetime, date)) else None,
    )


@pytest.fixture
def gdpr_data_delete(db, mock_idp_management_client):
    return GDPRDataDelete(db.session, mock_idp_management_client)


def test_validate_user_id(gdpr_data_delete):
    with pytest.raises(ValueError):
        gdpr_data_delete._validate_user_id(None)


@patch("utils.gdpr_backup_data.GDPRDataRestore")
def test_get_external_ids(mock_restore, gdpr_data_delete):
    mock_restore_instance = mock_restore.return_value
    mock_restore_instance.get_data_from_deletion_backup.return_value = [
        {"data": {"external_id": "test_id"}, "table": "user_auth"}
    ]
    assert gdpr_data_delete._get_external_ids(1) == ["test_id"]


def test_delete_auth0_user_success(mock_idp_management_client, gdpr_data_delete):
    mock_idp_management_client.get_user.return_value = True
    assert gdpr_data_delete._delete_auth0_user(1, ["test_id"]) is True


def test_delete_auth0_user_failure(mock_idp_management_client, gdpr_data_delete):
    mock_idp_management_client.get_user.side_effect = IdentityClientError(500, "Error")
    with pytest.raises(GDPRBackUpDataException):
        gdpr_data_delete._delete_auth0_user(1, ["test_id"])


@pytest.mark.parametrize(
    argnames="user_id,gdpr_back_up_data",
    argvalues=[
        (
            2,
            serialize_data(
                [
                    {
                        "table": "user_auth",
                        "foreign_key": {"column": "user_id", "value": 2},
                        "data": {
                            "id": 34948,
                            "user_id": 2,
                            "external_id": "auth0|653aa9f843c04abc2fef665b",
                            "refresh_token": None,
                        },
                    }
                ]
            ),
        ),
    ],
)
def test_delete(
    gdpr_data_delete,
    db,
    mock_idp_management_client,
    factories,
    user_id,
    gdpr_back_up_data,
):
    with patch.object(gdpr_data_delete, "_validate_user_id") as mock_validate:
        factories.GDPRDeletionBackupFactory.create(
            user_id=user_id, data=gdpr_back_up_data
        )
        gdpr_data_delete.delete(2)
        mock_validate.assert_called_once_with(2)
