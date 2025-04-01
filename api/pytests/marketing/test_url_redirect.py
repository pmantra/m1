import pytest as pytest

from models.marketing import (
    INACTIVE_ORG_REDIRECT_NOFORM_URL,
    INACTIVE_ORG_REDIRECT_URL,
    CapturePageType,
)


def test_unknown_redirect(client):
    res = client.get("/join/blahblahblah")

    assert res.status_code == 404


def test_redirect(client, factories):
    url_redirect_path = factories.URLRedirectPathFactory.create(path="maternity-signup")
    url_redirect = factories.URLRedirectFactory.create(
        path="coolpage",
        dest_url_redirect_path=url_redirect_path,
        dest_url_args={"blah": "stuff", "test": "things", "empty": ""},
    )

    expected_location = (
        "https://mavenclinic.com/maven-enrollment/maternity"
        "?blah=stuff"
        "&test=things"
    )
    res = client.get(f"/join/{url_redirect.path}")

    assert res.status_code == 302
    assert res.location == expected_location

    # trailing slash...
    res = client.get(f"/join/{url_redirect.path}/")

    assert res.status_code == 302
    assert res.location == expected_location


def test_redirect_no_args(client, factories):
    url_redirect_path = factories.URLRedirectPathFactory.create(path="maternity-signup")
    url_redirect = factories.URLRedirectFactory.create(
        path="coolpage",
        dest_url_redirect_path=url_redirect_path,
    )

    res = client.get(f"/join/{url_redirect.path}")

    assert res.status_code == 302
    assert res.location, "https://mavenclinic.com/maven-enrollment/maternity"


def test_inactive(client, factories):
    url_redirect_path = factories.URLRedirectPathFactory.create(path="maternity-signup")
    url_redirect = factories.URLRedirectFactory.create(
        path="coolpage",
        dest_url_redirect_path=url_redirect_path,
        active=False,
    )

    res = client.get(f"/join/{url_redirect.path}")
    assert res.status_code == 404


@pytest.mark.parametrize(
    argnames="capture_page_type,expected_location",
    argvalues=[
        (CapturePageType.FORM, INACTIVE_ORG_REDIRECT_URL),
        (CapturePageType.NO_FORM, INACTIVE_ORG_REDIRECT_NOFORM_URL),
    ],
)
def test_org_inactive(client, factories, capture_page_type, expected_location):
    org = factories.OrganizationFactory.create(name="Maven")
    url_redirect_path = factories.URLRedirectPathFactory.create(path="maternity-signup")
    url_redirect = factories.URLRedirectFactory.create(
        path="coolpage",
        dest_url_redirect_path=url_redirect_path,
        dest_url_args={"blah": "stuff", "test": "things", "empty": ""},
        organization=org,
    )
    org.capture_page_type = capture_page_type
    org.is_active = False

    res = client.get(f"/join/{url_redirect.path}")

    assert res.status_code == 302
    assert res.location == expected_location


def test_org_active(client, factories):
    org = factories.OrganizationFactory.create(name="Maven")
    url_redirect_path = factories.URLRedirectPathFactory.create(path="maternity-signup")
    url_redirect = factories.URLRedirectFactory.create(
        path="coolpage",
        dest_url_redirect_path=url_redirect_path,
        dest_url_args={"blah": "stuff", "test": "things", "empty": ""},
        organization=org,
    )
    expected_location = (
        "https://mavenclinic.com/maven-enrollment/maternity"
        f"?organization_id={org.id}"
        "&blah=stuff"
        "&test=things"
    )
    res = client.get(f"/join/{url_redirect.path}")

    assert res.status_code == 302
    assert res.location == expected_location


def test_alt_verification_auto_verify_param(client, factories):
    org = factories.OrganizationFactory.create(name="Maven")
    url_redirect_path = factories.URLRedirectPathFactory.create(
        path="maven-maternity-signup"
    )
    url_redirect = factories.URLRedirectFactory.create(
        path="coolpage",
        dest_url_redirect_path=url_redirect_path,
        dest_url_args={"blah": "stuff", "test": "things", "empty": ""},
        organization=org,
    )

    res = client.get(f"/join/{url_redirect.path}")

    expected_location = (
        "https://mavenclinic.com/maven-enrollment/maternitymp"
        f"?organization_id={org.id}"
        "&blah=stuff"
        "&test=things"
    )

    assert res.status_code == 302
    assert res.location == expected_location

    org.alternate_verification = True

    res = client.get(f"/join/{url_redirect.path}")

    assert res.status_code == 302
    assert res.location == expected_location


def test_org_active_new_landing_page_paths(client, factories):
    org = factories.OrganizationFactory.create(name="Maven")

    url_redirect_path = factories.URLRedirectPathFactory.create(path="microsoft")
    url_redirect = factories.URLRedirectFactory.create(
        path="coolpage",
        dest_url_redirect_path=url_redirect_path,
        dest_url_args={"blah": "stuff", "test": "things", "empty": ""},
        organization=org,
    )

    res = client.get(f"/join/{url_redirect.path}")
    expected_location = (
        "https://mavenclinic.com/maven-enrollment/microsoft"
        f"?organization_id={org.id}"
        "&blah=stuff&test=things"
    )

    assert res.status_code == 302
    assert res.location == expected_location
