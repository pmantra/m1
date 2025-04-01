from unittest import mock

import pytest

from views.enterprise import _get_org_info


@pytest.mark.parametrize(
    argnames="organizationFromSearchPage,externallySourcedOrganization,expected",
    argvalues=[
        ("Org 1", None, (1, "Org 1")),
        (1, None, (1, "Org 1")),
        (None, "Org 1", (1, "Org 1")),
        (None, "1", (1, "Org 1")),
        (None, None, (None, None)),
    ],
)
def test_get_org_data_success(
    factories, organizationFromSearchPage, externallySourcedOrganization, expected
):
    org = factories.OrganizationFactory(name="Org 1", id=1)

    with mock.patch(
        "eligibility.repository.OrganizationRepository.get_by_organization_id",
        return_value=org,
    ), mock.patch(
        "eligibility.repository.OrganizationRepository.get_organization_by_name",
        return_value=org,
    ):
        results = _get_org_info(
            {
                "organizationFromSearchPage": organizationFromSearchPage,
                "externallySourcedOrganization": externallySourcedOrganization,
            },
        )

        assert results == expected


@pytest.mark.parametrize(
    argnames="organizationFromSearchPage,externallySourcedOrganization,expected",
    argvalues=[
        ("Org 1", None, (None, "Org 1")),
        (1, None, (None, 1)),
        (None, "Org 1", (None, "Org 1")),
        (None, "1", (None, "1")),
        (None, None, (None, None)),
    ],
)
def test_get_org_data_failure(
    factories, organizationFromSearchPage, externallySourcedOrganization, expected
):
    with mock.patch(
        "eligibility.repository.OrganizationRepository.get_by_organization_id",
        return_value=None,
    ), mock.patch(
        "eligibility.repository.OrganizationRepository.get_organization_by_name",
        return_value=None,
    ):
        results = _get_org_info(
            {
                "organizationFromSearchPage": organizationFromSearchPage,
                "externallySourcedOrganization": externallySourcedOrganization,
            },
        )

        assert results == expected
