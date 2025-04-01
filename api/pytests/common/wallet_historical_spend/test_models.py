import datetime

import pytest as pytest

from common.wallet_historical_spend import Adjustment, LedgerEntry
from wallet.models.constants import WalletState
from wallet.pytests.factories import ReimbursementWalletFactory


@pytest.fixture
def mock_ledger():
    return LedgerEntry(
        id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        configuration_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        reimbursement_organization_settings_id="12324452543",
        employee_id="321",
        first_name="John",
        last_name="Doe",
        date_of_birth="1990-01-01",
        calculated_spend=90071,
        calculated_cycles=4,
        historical_spend=90072,
        historical_cycles_used=3,
        category="fertility",
        balance_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        file_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        most_recent_auth_date=datetime.date(2024, 12, 4),
        created_at=datetime.datetime(2024, 12, 4),
        service_date="2024-12-04",
        adjustment_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
        dependent_first_name="Jane",
        dependent_last_name="Doe",
        dependent_date_of_birth="1990-02-01",
        dependent_id="dep_123",
        subscriber_id="sub_123",
    )


@pytest.fixture
def mock_wallet(enterprise_user):
    return ReimbursementWalletFactory.create(
        state=WalletState.QUALIFIED, member=enterprise_user
    )


def test_ledger_entry_create_ledger_entries_from_dict():
    entries = LedgerEntry.create_ledger_entries_from_dict(
        [
            {
                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "configuration_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "employee_id": "321",
                "reimbursement_organization_settings_id": "12324452543",
                "first_name": "Jane",
                "last_name": "Doe",
                "date_of_birth": "2024-12-04",
                "category": "fertility",
                "balance_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "file_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "service_date": "2024-12-04",
                "most_recent_auth_date": "2024-12-04",
                "created_at": "2024-12-04T06:36:47.592",
                "adjustment_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "calculated_spend": 9007199254740991,
                "calculated_cycles": 9007199254740991,
                "historical_spend": 90072,
                "historical_cycles_used": 3,
            }
        ]
    )

    assert entries[0].employee_id == "321"
    assert isinstance(entries[0].most_recent_auth_date, datetime.date)
    assert entries[0].dependent_id is None


def test_ledger_entry_create_ledger_entries_from_dict_missing_required_fields():
    entries = LedgerEntry.create_ledger_entries_from_dict(
        [
            {
                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "configuration_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "reimbursement_organization_settings_id": "12324452543",
                "first_name": "Jane",
                "last_name": "Doe",
                "date_of_birth": "2024-12-04",
                "category": "fertility",
                "balance_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "file_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "service_date": "2024-12-04",
                "most_recent_auth_date": "2024-12-04",
                "created_at": "2024-12-04T06:36:47.592",
                "adjustment_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "calculated_spend": 9007199254740991,
                "calculated_cycles": 9007199254740991,
                "historical_spend": 90072,
                "historical_cycles_used": 3,
            }
        ]
    )
    assert entries == []


def test_ledger_entry_create_ledger_entries_from_dict_invalid_date():
    entries = LedgerEntry.create_ledger_entries_from_dict(
        [
            {
                "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "configuration_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "employee_id": "321",
                "reimbursement_organization_settings_id": "12324452543",
                "first_name": "Jane",
                "last_name": "Doe",
                "date_of_birth": "2024-12-04",
                "category": "fertility",
                "balance_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "file_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "service_date": "2024-12-04",
                "most_recent_auth_date": "24-12-04",
                "created_at": "2024-12-04T06:36:47.592",
                "adjustment_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "calculated_spend": 9007199254740991,
                "calculated_cycles": 9007199254740991,
                "historical_spend": 90072,
                "historical_cycles_used": 3,
            }
        ]
    )
    assert entries == []


@pytest.mark.parametrize(
    "is_currency",
    [
        True,
        False,
    ],
)
def test_create_adjustment_dict(mock_ledger, mock_wallet, is_currency):
    # Given
    reimbursement_request_id = "test_reimbursement_id"
    # When
    result = Adjustment.create_adjustment_dict(
        entry=mock_ledger,
        wallet=mock_wallet,
        is_currency=is_currency,
        reimbursement_request_id=reimbursement_request_id,
        value=3,
    )
    # Then
    assert result["balance_id"] == mock_ledger.balance_id
    assert result["wallet_id"] == str(mock_wallet.id)
    assert result["user_id"] == str(mock_wallet.user_id)
    assert result["value"] == 3
    assert result["is_currency"] == is_currency
    assert result["reimbursement_request_id"] == reimbursement_request_id


def test_to_dict_method():
    adjustment = Adjustment(
        balance_id="balance123",
        wallet_id="wallet123",
        user_id="user123",
        value=100,
        is_currency=True,
        reimbursement_request_id="reimbursement123",
    )
    result = adjustment.to_dict()
    # Assertions
    assert result == {
        "balance_id": "balance123",
        "wallet_id": "wallet123",
        "user_id": "user123",
        "value": 100,
        "is_currency": True,
        "reimbursement_request_id": "reimbursement123",
    }


def test_create_adjustment_dict_missing_parameters(mock_ledger, mock_wallet):
    with pytest.raises(TypeError):
        # Missing reimbursement_request_id
        Adjustment.create_adjustment_dict(
            entry=mock_ledger,
            wallet=mock_wallet,
            is_currency=True,
        )
