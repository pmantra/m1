from unittest import mock

from learn.models.bookmarks import MemberSavedResource
from learn.pytests import factories as learn_factories
from pytests import factories


@mock.patch("learn.services.contentful.LibraryContentfulClient")
@mock.patch("learn.utils.resource_utils.ReadTimeService")
def test_get_saved_resources(_, __, client, api_helpers):
    user = factories.EnterpriseUserFactory(tracks__name="fertility")
    resource1 = factories.ResourceFactory(webflow_url=None)
    resource2 = factories.ResourceFactory(webflow_url=None)
    resource3 = factories.ResourceFactory(webflow_url=None)

    learn_factories.MemberSavedResourceFactory(
        resource_id=resource1.id, member_id=user.id
    )
    learn_factories.MemberSavedResourceFactory(
        resource_id=resource3.id, member_id=user.id
    )

    response = client.get(
        "/api/v1/library/bookmarks", headers=api_helpers.json_headers(user)
    )

    assert response.status_code == 200

    saved_resources = response.json["saved_resources"]
    saved_resource_ids = [
        int(saved_resource["id"]) for saved_resource in saved_resources
    ]

    assert len(saved_resources) == 2
    assert resource1.id in saved_resource_ids
    assert resource2.id not in saved_resource_ids
    assert resource3.id in saved_resource_ids


def test_create_bookmark(client, api_helpers, db):
    user = factories.EnterpriseUserFactory(tracks__name="fertility")
    resource1 = factories.ResourceFactory(webflow_url=None)

    response = client.post(
        f"/api/v1/library/bookmarks/{resource1.slug}",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 200
    db_record = db.session.query(MemberSavedResource).one_or_none()
    assert db_record.resource_id == resource1.id
    assert db_record.member_id == user.id


def test_create_bookmark_already_created(client, api_helpers):
    user = factories.EnterpriseUserFactory(tracks__name="fertility")
    resource1 = factories.ResourceFactory(webflow_url=None)

    client.post(
        f"/api/v1/library/bookmarks/{resource1.slug}",
        headers=api_helpers.json_headers(user),
    )
    response = client.post(
        f"/api/v1/library/bookmarks/{resource1.slug}",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 200


def test_create_bookmark_article_not_found(client, api_helpers):
    user = factories.EnterpriseUserFactory(tracks__name="fertility")

    response = client.post(
        "/api/v1/library/bookmarks/made-up-slug", headers=api_helpers.json_headers(user)
    )

    assert response.status_code == 404


def test_delete_bookmark(client, api_helpers, db):
    user = factories.EnterpriseUserFactory(tracks__name="fertility")
    resource1 = factories.ResourceFactory(webflow_url=None)

    learn_factories.MemberSavedResourceFactory(
        resource_id=resource1.id, member_id=user.id
    )

    response = client.delete(
        f"/api/v1/library/bookmarks/{resource1.slug}",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 200
    db_record = db.session.query(MemberSavedResource).one_or_none()
    assert db_record is None


def test_delete_bookmark_doesnt_exist(client, api_helpers):
    user = factories.EnterpriseUserFactory(tracks__name="fertility")
    resource1 = factories.ResourceFactory(webflow_url=None)

    response = client.delete(
        f"/api/v1/library/bookmarks/{resource1.slug}",
        headers=api_helpers.json_headers(user),
    )

    assert response.status_code == 200


def test_delete_bookmark_resource_doesnt_exist(client, api_helpers):
    user = factories.EnterpriseUserFactory(tracks__name="fertility")

    response = client.delete(
        "/api/v1/library/bookmarks/made-up-slug", headers=api_helpers.json_headers(user)
    )

    assert response.status_code == 404


def test_marketplace_not_allowed(client, api_helpers):
    user = factories.MemberFactory()

    response = client.delete(
        "/api/v1/library/bookmarks/anything", headers=api_helpers.json_headers(user)
    )

    assert response.status_code == 403
