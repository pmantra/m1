import json

import pytest

from data_admin.views import apply_specs
from eligibility.pytests.factories import VerificationFactory
from models.tracks import TrackName

FIXTURES_TO_TEST = [
    # Each file named in an array here will be created in sequence, allowing testing of fixtures with dependencies
    # In cases where a fixture needs specific mocks (e.g. it hits an external service), consider a separate test
    ["wallet/fertility_clinic.json"],
    [
        "create_practitioner/create_admin.json",
        "wallet/reimbursement_calculator_data.json",
    ],
]


@pytest.fixture
def json_fixtures(request, load_fixture):
    filenames = request.param
    fixtures = []
    for filename in filenames:
        json_fixture = load_fixture(filename)
        fixtures.append(json_fixture)
    return fixtures


@pytest.fixture(scope="function")
def mock_organization(factories):
    organization = factories.OrganizationFactory.create(
        name="Wayne Enterprises LAP", allowed_tracks=[TrackName.FERTILITY]
    )

    return organization


@pytest.fixture(scope="function")
def mock_tracks(factories, mock_organization):
    track = factories.ClientTrackFactory.create(
        organization=mock_organization,
        track=TrackName.FERTILITY,
    )
    return [track]


@pytest.fixture(scope="function")
def qualified_wallet_fixture(mock_organization):
    """
    These fixture specs are necessary to define in Python so we can
    inject the organization_name into mocked e9y responses
    """
    fixture_spec = [
        {
            "type": "user",
            "organization_name": mock_organization.name,
            "track": "fertility",
            "phase": "week-1",
            "password": "simpleisawesome1*",
            "email": "qualified+wallet+user@mavenclinic.com",
            "date_of_birth": "1992-05-05",
            "company_email": "qualified+wallet+user@mavenclinic.com",
            "work_state": "NY",
            "country": "US",
            "create_member_record": True,
        },
        {
            "type": "reimbursement_organization_settings",
            "started_at": "1 days ago",
            "organization": mock_organization.name,
            "survey_url": "survey.example.com",
            "categories": [
                {
                    "type": "reimbursement_category",
                    "organization": mock_organization.name,
                    "label": "Fertility, Egg Freezing, Adoption & Surrogacy",
                }
            ],
        },
        {
            "type": "reimbursement_wallet",
            "organization": mock_organization.name,
            "member": "qualified+wallet+user@mavenclinic.com",
        },
    ]
    return fixture_spec


@pytest.fixture(scope="function")
def mock_e9y_member_and_verification(
    mock_enterprise_verification_service, mock_organization, mock_tracks, session
):
    member_record_json = json.dumps(
        {"unique_corp_id": "123", "dependent_id": "456", "id": "789"}
    )
    mock_verification = VerificationFactory.create(
        user_id=1, organization_id=mock_organization.id
    )
    mock_enterprise_verification_service.create_test_eligibility_member_records.return_value = [
        member_record_json
    ]

    mock_enterprise_verification_service.get_verification_for_user_and_org.return_value = (
        mock_verification
    )

    mock_enterprise_verification_service.get_eligible_features_for_user_and_org.return_value = [
        t.id for t in mock_tracks
    ]


@pytest.mark.parametrize("json_fixtures", FIXTURES_TO_TEST, indirect=True)
def test_fixture(json_fixtures, data_admin_app):
    with data_admin_app.test_request_context():
        for fixture in json_fixtures:
            created, errors = apply_specs(fixture)
            assert created


class TestOrgDependentFixtures:
    @staticmethod
    def test_qualified_wallet_fixture(
        data_admin_app,
        mock_e9y_member_and_verification,
        qualified_wallet_fixture,
        user_dependencies,
    ):
        with data_admin_app.test_request_context():
            created, errors = apply_specs(qualified_wallet_fixture)
        assert len(created) == 3
