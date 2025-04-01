from types import SimpleNamespace

import pytest

from views.schemas.FHIR.wallet import WalletInfoSchema


@pytest.mark.parametrize(
    argnames="input,expected",
    argvalues=[
        (
            SimpleNamespace(
                state=SimpleNamespace(value="Test"),
                reimbursement_organization_settings=SimpleNamespace(
                    is_active=False,
                ),
            ),
            {
                "offered_by_org": False,
                "member_status": "Test",
            },
        ),
        (
            SimpleNamespace(
                reimbursement_organization_settings=SimpleNamespace(is_active=True)
            ),
            {
                "offered_by_org": True,
                "member_status": None,
            },
        ),
        (
            SimpleNamespace(
                state=SimpleNamespace(value="Test"),
                reimbursement_organization_settings=[SimpleNamespace(is_active=True)],
            ),
            {
                "offered_by_org": True,
                "member_status": "Test",
            },
        ),
        (
            SimpleNamespace(
                reimbursement_organization_settings=[
                    SimpleNamespace(is_active=False),
                    SimpleNamespace(is_active=False),
                    SimpleNamespace(is_active=False),
                ]
            ),
            {
                "offered_by_org": False,
                "member_status": None,
            },
        ),
        (
            SimpleNamespace(
                reimbursement_organization_settings=[
                    SimpleNamespace(is_active=False),
                    SimpleNamespace(is_active=False),
                    SimpleNamespace(is_active=True),
                ]
            ),
            {
                "offered_by_org": True,
                "member_status": None,
            },
        ),
    ],
    ids=[
        "wallet_not_active",
        "wallet_active",
        "settings_with_one_entry",
        "settings_with_multiple_entries_all_false",
        "settings_with_multiple_entries_mixed",
    ],
)
def test_schema(input, expected):
    schema = WalletInfoSchema()

    result = schema.dump(input)

    assert result == expected
